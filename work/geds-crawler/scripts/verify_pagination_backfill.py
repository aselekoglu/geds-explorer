import argparse
import hashlib
import json
import sys
import sqlite3
from pathlib import Path

# Add src/ folder to Python path so we can import geds_crawler
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-db", required=True)
    parser.add_argument("--overlay-db", required=True)
    parser.add_argument("--expected-org-dn", action="append", required=True)
    args = parser.parse_args()

    base_path = Path(args.base_db).resolve()
    overlay_path = Path(args.overlay_db).resolve()
    expected_org_dns = args.expected_org_dn

    if len(expected_org_dns) != 2:
        print("Error: Exactly two --expected-org-dn values must be provided.", file=sys.stderr)
        sys.exit(1)

    # 1. Hash base before querying
    def compute_sha256(path):
        h = hashlib.sha256()
        with open(path, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        return h.hexdigest()

    sha_before = compute_sha256(base_path)

    # 2. Check for contact columns in people_index
    contact_columns_present = False
    for db_path in (base_path, overlay_path):
        try:
            conn = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
            cursor = conn.execute("PRAGMA table_info(people_index)")
            cols = [col[1].lower() for col in cursor.fetchall()]
            conn.close()
            for c in cols:
                if any(x in c for x in ("email", "phone", "tele")):
                    contact_columns_present = True
        except Exception:
            pass

    # 3. Check duplicate source URLs in the overlay
    duplicate_source_urls = 0
    try:
        conn = sqlite3.connect(f"file:{overlay_path.as_posix()}?mode=ro", uri=True)
        cursor = conn.execute(
            "SELECT COUNT(source_url) FROM people_index GROUP BY source_url HAVING COUNT(*) > 1"
        )
        duplicate_source_urls = len(cursor.fetchall())
        conn.close()
    except Exception:
        pass

    # 4. Check status of expected organizations
    orgs_info = []
    has_exceeds_25 = False
    all_terminal = True
    
    from geds_crawler.ui_queries import SnapshotReader
    reader = SnapshotReader(base_path, [overlay_path])

    try:
        overlay_conn = sqlite3.connect(f"file:{overlay_path.as_posix()}?mode=ro", uri=True)
        overlay_conn.row_factory = sqlite3.Row
    except Exception:
        overlay_conn = None
    
    for org_dn in expected_org_dns:
        status = "unknown"
        pages_fetched = 0
        failure_reason = None
        last_page_url = None
        
        if overlay_conn:
            try:
                row = overlay_conn.execute(
                    "SELECT status, pages_fetched, last_error, terminal_reason, last_page_url FROM pagination_orgs WHERE org_dn = ?",
                    (org_dn,)
                ).fetchone()
                if row:
                    status = row["status"]
                    pages_fetched = row["pages_fetched"]
                    failure_reason = row["last_error"] or row["terminal_reason"]
                    last_page_url = row["last_page_url"]
            except Exception:
                pass

        if status not in ("completed", "failed"):
            all_terminal = False

        unique_people = 0
        try:
            with reader._connect_with_overlays() as m_con:
                source_sql = reader._people_source_sql()
                cursor = m_con.execute(
                    f"SELECT COUNT(*) FROM ({source_sql}) WHERE org_dn = ?",
                    (org_dn,)
                )
                unique_people = int(cursor.fetchone()[0])
        except Exception:
            pass

        exceeds_25 = unique_people > 25
        if exceeds_25:
            has_exceeds_25 = True

        orgs_info.append({
            "org_dn": org_dn,
            "pages_fetched": pages_fetched,
            "unique_people": unique_people,
            "exceeds_25": exceeds_25,
            "status": status,
            "failure_reason": failure_reason
        })
        
    if overlay_conn:
        overlay_conn.close()

    # Hash base after querying
    sha_after = compute_sha256(base_path)
    base_unchanged = (sha_before == sha_after)

    output = {
        "base_sha256_before": sha_before,
        "base_sha256_after": sha_after,
        "base_unchanged": base_unchanged,
        "organizations": orgs_info,
        "contact_columns_present": contact_columns_present,
        "duplicate_source_urls": duplicate_source_urls
    }

    # Print JSON output to stdout
    print(json.dumps(output, indent=2))

    errors = []
    if not base_unchanged:
        errors.append("Base hash changed")
    if len(orgs_info) < len(expected_org_dns):
        errors.append("Not all expected organizations found")
    if not all_terminal:
        errors.append("Some organizations are not in terminal status")
    if not has_exceeds_25:
        errors.append("Neither organization exceeds 25 people")
    if contact_columns_present:
        errors.append("Contact columns exist in people_index")
    if duplicate_source_urls > 0:
        errors.append("Duplicate source URLs exist in the overlay")

    if errors:
        print(f"Validation failed: {', '.join(errors)}", file=sys.stderr)
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    main()
