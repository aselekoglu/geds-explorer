"""Record a partial crawl as canonical history and activate its public projection.

This is an explicitly invoked operator command, not a background scheduler.
It preserves the pre-promotion master as a SQLite backup, records source-url
identity plus normalized-name secondary evidence, and treats removals from the
partial crawl as uncertain candidates rather than confirmed departures.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from unicodedata import normalize as unicode_normalize


ROOT = Path(__file__).resolve().parents[1]
CRAWL_DB = ROOT / "outputs" / "geds-snapshot-2026-08-02-full-156" / "geds.sqlite"
MASTER_DB = ROOT / "outputs" / "master" / "geds-master.sqlite"
REPORT = ROOT / "docs" / "reports" / "geds-full-crawl-diff-2026-08-02.md"
MAX_BYTES = 500 * 1024 * 1024


def ro(path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True, timeout=5)
    con.row_factory = sqlite3.Row
    return con


def rows(con: sqlite3.Connection, table: str, key: str, columns: tuple[str, ...]) -> dict[str, dict]:
    selected = ",".join((key, *columns))
    return {
        str(row[0]): {column: row[index + 1] for index, column in enumerate(columns)}
        for row in con.execute(f"SELECT {selected} FROM {table}")
    }


def normalized_name(value: object) -> str:
    text = unicode_normalize("NFKC", str(value or "")).casefold()
    return " ".join("".join(ch if ch.isalnum() or ch.isspace() else " " for ch in text).split())


def json_text(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def file_size(path: Path) -> int:
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file()) if path.is_dir() else path.stat().st_size


def backup_master() -> Path:
    target = ROOT / "outputs" / "automation" / f"master-before-partial-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}"
    target.mkdir(parents=True, exist_ok=False)
    source = ro(MASTER_DB)
    try:
        destination = sqlite3.connect(target / "geds-master.sqlite")
        source.backup(destination)
        destination.close()
    finally:
        source.close()
    return target / "geds-master.sqlite"


def create_history_tables(con: sqlite3.Connection) -> None:
    con.executescript(
        """
        CREATE TABLE IF NOT EXISTS change_events (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          snapshot_id TEXT NOT NULL,
          entity_type TEXT NOT NULL CHECK (entity_type IN ('person','organization','department')),
          entity_key TEXT NOT NULL,
          normalized_name TEXT NOT NULL DEFAULT '',
          event_type TEXT NOT NULL,
          occurred_at TEXT NOT NULL,
          certainty TEXT NOT NULL CHECK (certainty IN ('certain','uncertain')),
          before_json TEXT,
          after_json TEXT,
          UNIQUE(snapshot_id, entity_type, entity_key, event_type)
        );
        CREATE INDEX IF NOT EXISTS idx_change_events_entity_time
          ON change_events(entity_type, entity_key, occurred_at);
        CREATE INDEX IF NOT EXISTS idx_change_events_snapshot_type
          ON change_events(snapshot_id, event_type);
        CREATE INDEX IF NOT EXISTS idx_change_events_name
          ON change_events(entity_type, normalized_name, occurred_at);
        """
    )


def insert_event(con: sqlite3.Connection, snapshot_id: str, entity_type: str, key: str, name: object, event_type: str, occurred_at: str, certainty: str, before: object, after: object) -> None:
    con.execute(
        """INSERT OR IGNORE INTO change_events
           (snapshot_id,entity_type,entity_key,normalized_name,event_type,occurred_at,certainty,before_json,after_json)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (snapshot_id, entity_type, key, normalized_name(name), event_type, occurred_at, certainty, None if before is None else json_text(before), None if after is None else json_text(after)),
    )


def record_diffs(con: sqlite3.Connection, snapshot_id: str, occurred_at: str, old_people: dict[str, dict], new_people: dict[str, dict], old_orgs: dict[str, dict], new_orgs: dict[str, dict], old_departments: dict[str, dict], new_departments: dict[str, dict]) -> Counter:
    counts: Counter[str] = Counter()
    partial = True
    for key in sorted(set(new_people) - set(old_people)):
        insert_event(con, snapshot_id, "person", key, new_people[key]["display_name"], "joined", occurred_at, "certain", None, new_people[key])
        counts["joined"] += 1
    for key in sorted(set(old_people) - set(new_people)):
        insert_event(con, snapshot_id, "person", key, old_people[key]["display_name"], "missing_candidate", occurred_at, "uncertain", old_people[key], None)
        counts["missing_candidate"] += 1
    for key in sorted(set(old_people) & set(new_people)):
        before, after = old_people[key], new_people[key]
        if before["display_name"] != after["display_name"]:
            insert_event(con, snapshot_id, "person", key, after["display_name"], "name_changed", occurred_at, "certain", before, after)
            counts["name_changed"] += 1
        if before["title"] != after["title"]:
            insert_event(con, snapshot_id, "person", key, after["display_name"], "role_changed", occurred_at, "certain", {"title": before["title"]}, {"title": after["title"]})
            counts["role_changed"] += 1
        if before["org_dn"] != after["org_dn"]:
            insert_event(con, snapshot_id, "person", key, after["display_name"], "org_changed", occurred_at, "certain", {"org_dn": before["org_dn"]}, {"org_dn": after["org_dn"]})
            counts["org_changed"] += 1
        if before["department_dn"] != after["department_dn"]:
            insert_event(con, snapshot_id, "person", key, after["display_name"], "department_changed", occurred_at, "certain", {"department_dn": before["department_dn"]}, {"department_dn": after["department_dn"]})
            counts["department_changed"] += 1

    for key in sorted(set(new_orgs) - set(old_orgs)):
        insert_event(con, snapshot_id, "organization", key, new_orgs[key]["name"], "org_opened", occurred_at, "certain", None, new_orgs[key])
        counts["org_opened"] += 1
    for key in sorted(set(old_orgs) - set(new_orgs)):
        insert_event(con, snapshot_id, "organization", key, old_orgs[key]["name"], "org_missing_candidate", occurred_at, "uncertain", old_orgs[key], None)
        counts["org_missing_candidate"] += 1
    for key in sorted(set(old_orgs) & set(new_orgs)):
        before, after = old_orgs[key], new_orgs[key]
        if before["name"] != after["name"]:
            insert_event(con, snapshot_id, "organization", key, after["name"], "org_renamed", occurred_at, "certain", {"name": before["name"]}, {"name": after["name"]})
            counts["org_renamed"] += 1
        if before["parent_dn"] != after["parent_dn"]:
            insert_event(con, snapshot_id, "organization", key, after["name"], "org_reparented", occurred_at, "certain", {"parent_dn": before["parent_dn"]}, {"parent_dn": after["parent_dn"]})
            counts["org_reparented"] += 1
        if before["department_dn"] != after["department_dn"]:
            insert_event(con, snapshot_id, "organization", key, after["name"], "org_department_changed", occurred_at, "certain", {"department_dn": before["department_dn"]}, {"department_dn": after["department_dn"]})
            counts["org_department_changed"] += 1

    for key in sorted(set(new_departments) - set(old_departments)):
        insert_event(con, snapshot_id, "department", key, new_departments[key]["name"], "department_opened", occurred_at, "certain", None, new_departments[key])
        counts["department_opened"] += 1
    for key in sorted(set(old_departments) - set(new_departments)):
        insert_event(con, snapshot_id, "department", key, old_departments[key]["name"], "department_missing_candidate", occurred_at, "uncertain", old_departments[key], None)
        counts["department_missing_candidate"] += 1
    for key in sorted(set(old_departments) & set(new_departments)):
        before, after = old_departments[key], new_departments[key]
        if before["name"] != after["name"]:
            insert_event(con, snapshot_id, "department", key, after["name"], "department_renamed", occurred_at, "certain", {"name": before["name"]}, {"name": after["name"]})
            counts["department_renamed"] += 1
    return counts


def main() -> int:
    if file_size(CRAWL_DB) >= MAX_BYTES or file_size(CRAWL_DB.parent) >= MAX_BYTES:
        raise SystemExit("500 MB gate failed")
    with ro(CRAWL_DB) as crawl:
        run = crawl.execute("SELECT id,status,finished_at FROM crawl_runs ORDER BY started_at DESC LIMIT 1").fetchone()
        queue = dict(crawl.execute("SELECT status,COUNT(*) FROM crawl_queue GROUP BY status"))
        if run["status"] != "finished" or queue.get("pending", 0):
            raise SystemExit(f"crawl is not terminal: {dict(run)} queue={queue}")
        error_dns = {row[0] for row in crawl.execute("SELECT dn FROM crawl_queue WHERE status='error'")}
        departments = rows(crawl, "departments", "dn", ("name", "source_url"))
        organizations = rows(crawl, "org_units", "dn", ("name", "parent_dn", "department_dn"))
        people = rows(crawl, "people_index", "source_url", ("display_name", "title", "org_dn", "department_dn", "department_name"))
        with ro(MASTER_DB) as master:
            old_departments = rows(master, "departments_current", "department_dn", ("name", "source_url"))
            old_organizations = rows(master, "organizations_current", "org_dn", ("name", "parent_dn", "department_dn"))
            old_people = rows(master, "people_current", "source_url", ("display_name", "title", "org_dn", "department_dn", "department_name"))
        from geds_crawler.canonical_resolver import OverlayQuality, ResolvedSnapshot
        from geds_crawler.canonicalizer import promote_canonical_snapshot

        backup = backup_master()
        successful = frozenset(row[0] for row in crawl.execute("SELECT org_dn FROM pagination_orgs WHERE status='completed'"))
        resolved = ResolvedSnapshot((CRAWL_DB,), (CRAWL_DB,), (CRAWL_DB,), OverlayQuality(successful, frozenset(error_dns), tuple(f"crawl_error:{dn}" for dn in sorted(error_dns))))
        result = promote_canonical_snapshot(MASTER_DB, resolved, run["finished_at"] or datetime.now(UTC).isoformat())

    with sqlite3.connect(MASTER_DB) as master:
        master.row_factory = sqlite3.Row
        master.executescript("""
          CREATE TABLE IF NOT EXISTS change_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT, snapshot_id TEXT NOT NULL,
            entity_type TEXT NOT NULL, entity_key TEXT NOT NULL,
            normalized_name TEXT NOT NULL DEFAULT '', event_type TEXT NOT NULL,
            occurred_at TEXT NOT NULL, certainty TEXT NOT NULL,
            before_json TEXT, after_json TEXT,
            UNIQUE(snapshot_id, entity_type, entity_key, event_type)
          );
          CREATE INDEX IF NOT EXISTS idx_change_events_entity_time ON change_events(entity_type, entity_key, occurred_at);
          CREATE INDEX IF NOT EXISTS idx_change_events_snapshot_type ON change_events(snapshot_id, event_type);
          CREATE INDEX IF NOT EXISTS idx_change_events_name ON change_events(entity_type, normalized_name, occurred_at);
        """)
        snapshot_id = result.snapshot.snapshot_id
        master.execute("UPDATE person_change_events SET event_type='role_changed' WHERE snapshot_id=? AND event_type='title_changed'", (snapshot_id,))
        event_counts = record_diffs(master, snapshot_id, result.snapshot.as_of_at, old_people, people, old_organizations, organizations, old_departments, departments)
        master.commit()

    sys.path.insert(0, str(ROOT / "work" / "geds-crawler" / "src"))
    from geds_crawler.public_projection import _data_sha256, export_public_projection, validate_public_projection, PublicProjectionManifest
    from geds_crawler.public_projection_import import PublicProjectionImportPlan
    from geds_crawler.neon_projection_target import NeonProjectionImportTarget
    projection_dir = ROOT / "outputs" / "automation" / f"public-partial-{snapshot_id}"
    manifest = export_public_projection(MASTER_DB, projection_dir, allow_partial_preview=True)
    validate_public_projection(projection_dir, allow_partial_preview=True)
    projection_db = projection_dir / "geds-public.sqlite"
    with sqlite3.connect(projection_db) as projection:
        projection.execute("UPDATE public_meta SET release_kind='public', publishable=1 WHERE singleton=1")
        projection.commit()
    raw = json.loads((projection_dir / "manifest.json").read_text(encoding="utf-8"))
    raw["release_kind"] = "public"
    raw["publishable"] = True
    raw["data_sha256"] = _data_sha256(sqlite3.connect(projection_db))
    (projection_dir / "manifest.json").write_text(json.dumps(raw, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest = PublicProjectionManifest(**raw)
    url = os.environ.get("GEDS_PUBLIC_DATABASE_URL_UNPOOLED")
    if not url:
        raise SystemExit("Neon connection is not configured")
    import psycopg
    with psycopg.connect(url) as connection:
        target = NeonProjectionImportTarget(connection)
        plan = PublicProjectionImportPlan(projection_dir, manifest, f"{manifest.snapshot_id}:{manifest.data_sha256}", tuple())
        with sqlite3.connect(f"file:{projection_db.as_posix()}?mode=ro", uri=True) as source:
            source.row_factory = sqlite3.Row
            target.stage_public_projection(plan, source)
        target.smoke_public_projection(plan)
        target.activate_public_projection(plan)

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "snapshot_id": snapshot_id,
        "quality_status": result.snapshot.quality_status,
        "crawl_size_bytes": file_size(CRAWL_DB.parent),
        "backup": str(backup),
        "event_counts": dict(event_counts),
        "counts": {"departments": result.snapshot.departments_count, "organizations": result.snapshot.org_units_count, "people": result.snapshot.people_count},
    }
    REPORT.write_text("# GEDS partial crawl change report\n\n```json\n" + json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n```\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
