"""Prepare a Turso upload bundle without SQLite FTS5 shadow tables."""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_ID = "cbcd6b63facc3b6eb7e344a81c899ea22531cfca5417eb52d8eb4bfdf7712d38"
SOURCE_DIR = ROOT / "outputs" / "automation" / f"turso-shadow-{SNAPSHOT_ID}-v4"
SOURCE_DB = SOURCE_DIR / "geds-shadow.sqlite"
OUTPUT_DIR = ROOT / "outputs" / "automation" / f"turso-shadow-{SNAPSHOT_ID}-v5"
OUTPUT_DB = OUTPUT_DIR / "geds-shadow.sqlite"


def main() -> int:
    if not SOURCE_DB.exists():
        raise SystemExit(f"Source bundle not found: {SOURCE_DB}")
    if OUTPUT_DIR.exists():
        raise SystemExit(f"Refusing to overwrite existing output: {OUTPUT_DIR}")

    OUTPUT_DIR.mkdir(parents=True)
    shutil.copy2(SOURCE_DB, OUTPUT_DB)

    with sqlite3.connect(OUTPUT_DB) as con:
        fts_exists = con.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='career_entities_fts'"
        ).fetchone()
        if not fts_exists:
            raise SystemExit("Expected career_entities_fts table was not found")

        con.execute("DROP TABLE career_entities_fts")
        con.commit()
        con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        con.execute("VACUUM")
        con.execute("PRAGMA journal_mode=WAL")
        con.commit()
        con.execute("PRAGMA wal_checkpoint(TRUNCATE)")

        counts = {
            table: int(con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            for table in (
                "departments_current",
                "organizations_current",
                "people_current",
                "career_entities",
                "change_events",
                "person_change_events",
            )
        }
        checks = {
            "integrity": str(con.execute("PRAGMA integrity_check").fetchone()[0]),
            "source_url_duplicates": int(
                con.execute(
                    "SELECT COUNT(*) FROM (SELECT source_url FROM people_current "
                    "GROUP BY source_url HAVING COUNT(*) > 1)"
                ).fetchone()[0]
            ),
            "fts5_objects": int(
                con.execute(
                    "SELECT COUNT(*) FROM sqlite_master WHERE name LIKE 'career_entities_fts%'"
                ).fetchone()[0]
            ),
            "journal_mode": str(con.execute("PRAGMA journal_mode").fetchone()[0]),
            "page_size": int(con.execute("PRAGMA page_size").fetchone()[0]),
            "auto_vacuum": int(con.execute("PRAGMA auto_vacuum").fetchone()[0]),
            "encoding": str(con.execute("PRAGMA encoding").fetchone()[0]),
        }

    if checks["integrity"] != "ok":
        raise SystemExit(f"SQLite integrity failed: {checks['integrity']}")
    if checks["fts5_objects"] != 0:
        raise SystemExit(f"FTS5 objects remain: {checks['fts5_objects']}")
    if checks["journal_mode"].lower() != "wal" or checks["page_size"] != 4096:
        raise SystemExit(f"Turso requirements failed: {checks}")

    source_manifest = json.loads((SOURCE_DIR / "manifest.json").read_text(encoding="utf-8"))
    result = {
        "bundle": str(OUTPUT_DB),
        "bundle_bytes": OUTPUT_DB.stat().st_size,
        "bundle_sha256": hashlib.sha256(OUTPUT_DB.read_bytes()).hexdigest(),
        "snapshot_id": SNAPSHOT_ID,
        "source_bundle": str(SOURCE_DB),
        "removed_for_turso_compatibility": [
            "career_entities_fts and SQLite FTS5 shadow tables"
        ],
        "counts": counts,
        "checks": checks,
        "neon_touched": False,
        "source_manifest_sha256": hashlib.sha256(
            (SOURCE_DIR / "manifest.json").read_bytes()
        ).hexdigest(),
        "identity_policy": source_manifest.get("projection_manifest", {}).get(
            "identity_policy"
        ),
    }
    (OUTPUT_DIR / "manifest.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
