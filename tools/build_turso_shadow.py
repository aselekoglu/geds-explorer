"""Build a loss-aware Turso shadow bundle from the latest GEDS snapshot.

The bundle intentionally contains the latest public projection plus the
chronological diff tables and crawl-quality metadata. It does not copy the
old canonical current projection into Turso, and it never mutates Neon or the
canonical master.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
from datetime import UTC, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MASTER_DB = ROOT / "outputs" / "master" / "geds-master.sqlite"
CRAWL_DB = ROOT / "outputs" / "geds-snapshot-2026-08-02-full-156" / "geds.sqlite"
PROJECTION_ROOT = ROOT / "outputs" / "automation"


def read_manifest(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def latest_snapshot_id() -> str:
    with sqlite3.connect(MASTER_DB) as con:
        return str(
            con.execute(
                "SELECT snapshot_id FROM canonical_snapshots ORDER BY as_of_at DESC LIMIT 1"
            ).fetchone()[0]
        )


def find_projection(snapshot_id: str) -> tuple[Path, dict]:
    candidates: list[tuple[Path, dict]] = []
    for manifest_path in PROJECTION_ROOT.glob("public-partial-*/manifest.json"):
        manifest = read_manifest(manifest_path)
        if str(manifest.get("snapshot_id")) == snapshot_id:
            candidates.append((manifest_path.parent, manifest))
    if not candidates:
        raise SystemExit(f"No projection found for snapshot {snapshot_id}")
    return max(candidates, key=lambda item: item[0].stat().st_mtime)


def copy_projection(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise SystemExit(f"Refusing to overwrite existing bundle: {target}")
    source_con = sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True)
    try:
        target_con = sqlite3.connect(target)
        try:
            source_con.backup(target_con)
        finally:
            target_con.close()
    finally:
        source_con.close()


def create_history_tables(con: sqlite3.Connection) -> None:
    con.executescript(
        """
        CREATE TABLE IF NOT EXISTS change_events (
          id INTEGER PRIMARY KEY,
          snapshot_id TEXT NOT NULL,
          entity_type TEXT NOT NULL,
          entity_key TEXT NOT NULL,
          normalized_name TEXT NOT NULL DEFAULT '',
          event_type TEXT NOT NULL,
          occurred_at TEXT NOT NULL,
          certainty TEXT NOT NULL,
          before_json TEXT,
          after_json TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_turso_change_events_entity_time
          ON change_events(entity_type, entity_key, occurred_at);
        CREATE INDEX IF NOT EXISTS idx_turso_change_events_snapshot_type
          ON change_events(snapshot_id, event_type);
        CREATE TABLE IF NOT EXISTS person_change_events (
          snapshot_id TEXT NOT NULL,
          person_key TEXT NOT NULL,
          event_type TEXT NOT NULL,
          occurred_at TEXT NOT NULL,
          details_json TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_turso_person_events_person_time
          ON person_change_events(person_key, occurred_at);
        CREATE TABLE IF NOT EXISTS crawl_run_metadata (
          run_id TEXT PRIMARY KEY,
          status TEXT NOT NULL,
          finished_at TEXT,
          crawl_size_bytes INTEGER NOT NULL,
          departments_count INTEGER NOT NULL,
          organizations_count INTEGER NOT NULL,
          people_count INTEGER NOT NULL,
          queue_done INTEGER NOT NULL,
          queue_error INTEGER NOT NULL,
          crawl_errors INTEGER NOT NULL,
          quality_status TEXT NOT NULL,
          fallback_org_count INTEGER NOT NULL,
          cycle_count INTEGER NOT NULL,
          warning_json TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS crawl_error_records (
          run_id TEXT NOT NULL,
          error_kind TEXT NOT NULL,
          entity_key TEXT,
          message TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_turso_crawl_errors_run
          ON crawl_error_records(run_id, error_kind);
        CREATE TABLE IF NOT EXISTS turso_shadow_manifest (
          singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
          generated_at TEXT NOT NULL,
          snapshot_id TEXT NOT NULL,
          parent_snapshot_id TEXT,
          projection_manifest_json TEXT NOT NULL,
          identity_policy_json TEXT NOT NULL,
          source_projection_path TEXT NOT NULL
        );
        """
    )


def populate_history(con: sqlite3.Connection, snapshot_id: str, projection_dir: Path, projection_manifest: dict) -> dict:
    con.execute("ATTACH DATABASE ? AS master_source", (str(MASTER_DB.resolve()),))
    con.execute("ATTACH DATABASE ? AS crawl_source", (str(CRAWL_DB.resolve()),))
    try:
        con.execute(
            """INSERT INTO change_events
               SELECT id,snapshot_id,entity_type,entity_key,normalized_name,event_type,
                      occurred_at,certainty,before_json,after_json
                 FROM master_source.change_events
                ORDER BY id"""
        )
        con.execute(
            """INSERT INTO person_change_events
               SELECT snapshot_id,person_key,event_type,occurred_at,details_json
                 FROM master_source.person_change_events
                ORDER BY occurred_at,person_key,event_type"""
        )
        snapshot = con.execute(
            """SELECT snapshot_id,parent_snapshot_id,quality_status,
                      fallback_org_count,cycle_count,quality_warnings_json
                 FROM master_source.canonical_snapshots WHERE snapshot_id=?""",
            (snapshot_id,),
        ).fetchone()
        if snapshot is None:
            raise SystemExit(f"Master does not contain snapshot {snapshot_id}")
        run = con.execute(
            """SELECT id,status,finished_at FROM crawl_source.crawl_runs
                ORDER BY started_at DESC LIMIT 1"""
        ).fetchone()
        queue = {
            str(row[0]): int(row[1])
            for row in con.execute(
                "SELECT status,COUNT(*) FROM crawl_source.crawl_queue GROUP BY status"
            )
        }
        crawl_errors = int(
            con.execute("SELECT COUNT(*) FROM crawl_source.crawl_errors").fetchone()[0]
        )
        raw_counts = {
            "departments": int(
                con.execute("SELECT COUNT(*) FROM crawl_source.departments").fetchone()[0]
            ),
            "organizations": int(
                con.execute("SELECT COUNT(*) FROM crawl_source.org_units").fetchone()[0]
            ),
            "people": int(
                con.execute("SELECT COUNT(*) FROM crawl_source.people_index").fetchone()[0]
            ),
        }
        warnings = json.loads(str(snapshot[5]))
        con.execute(
            """INSERT INTO crawl_run_metadata VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                str(run[0]),
                str(run[1]),
                run[2],
                sum(item.stat().st_size for item in CRAWL_DB.parent.rglob("*") if item.is_file()),
                raw_counts["departments"],
                raw_counts["organizations"],
                raw_counts["people"],
                queue.get("done", 0),
                queue.get("error", 0),
                crawl_errors,
                str(snapshot[2]),
                int(snapshot[3]),
                int(snapshot[4]),
                json.dumps(warnings, ensure_ascii=False, sort_keys=True),
            ),
        )
        for dn in con.execute(
            "SELECT dn FROM crawl_source.crawl_queue WHERE status='error' ORDER BY dn"
        ):
            con.execute(
                "INSERT INTO crawl_error_records VALUES (?,?,?,?)",
                (str(run[0]), "queue_error", str(dn[0]), None),
            )
        for row in con.execute(
            "SELECT error_type,error_message FROM crawl_source.crawl_errors ORDER BY id"
        ):
            con.execute(
                "INSERT INTO crawl_error_records VALUES (?,?,?,?)",
                (str(run[0]), "crawl_error", None, f"{row[0]}: {row[1]}"),
            )
        con.execute(
            "INSERT INTO turso_shadow_manifest VALUES (1,?,?,?,?,?,?)",
            (
                datetime.now(UTC).isoformat(),
                snapshot_id,
                con.execute(
                    "SELECT parent_snapshot_id FROM master_source.canonical_snapshots WHERE snapshot_id=?",
                    (snapshot_id,),
                ).fetchone()[0],
                json.dumps(projection_manifest, ensure_ascii=False, sort_keys=True),
                json.dumps(
                    {
                        "primary_identity": "source_url",
                        "secondary_identity": "normalized_name",
                        "role_event": "role_changed",
                        "role_event_payload": "before.title -> after.title",
                        "partial_absence": "uncertain missing_candidate; no confirmed departure",
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                str(projection_dir),
            ),
        )
        return {
            "run_id": str(run[0]),
            "raw_counts": raw_counts,
            "queue": queue,
            "crawl_errors": crawl_errors,
            "warnings": warnings,
        }
    finally:
        con.execute("DETACH DATABASE crawl_source")
        con.execute("DETACH DATABASE master_source")


def validate(con: sqlite3.Connection, snapshot_id: str, expected: dict) -> dict:
    checks = {
        "integrity": str(con.execute("PRAGMA integrity_check").fetchone()[0]),
        "snapshot_id": str(con.execute("SELECT snapshot_id FROM public_meta WHERE singleton=1").fetchone()[0]),
        "departments": int(con.execute("SELECT COUNT(*) FROM departments_current").fetchone()[0]),
        "organizations": int(con.execute("SELECT COUNT(*) FROM organizations_current").fetchone()[0]),
        "people": int(con.execute("SELECT COUNT(*) FROM people_current WHERE presence_status='present'").fetchone()[0]),
        "career_entities": int(con.execute("SELECT COUNT(*) FROM career_entities").fetchone()[0]),
        "change_events": int(con.execute("SELECT COUNT(*) FROM change_events").fetchone()[0]),
        "person_change_events": int(con.execute("SELECT COUNT(*) FROM person_change_events").fetchone()[0]),
        "source_url_duplicates": int(con.execute("SELECT COUNT(*) FROM (SELECT source_url FROM people_current GROUP BY source_url HAVING COUNT(*) > 1)").fetchone()[0]),
    }
    if checks["integrity"] != "ok":
        raise SystemExit(f"SQLite integrity check failed: {checks['integrity']}")
    if checks["snapshot_id"] != snapshot_id:
        raise SystemExit("public projection snapshot binding failed")
    for key in ("departments", "organizations", "people", "career_entities"):
        if checks[key] != int(expected["counts"][key]):
            raise SystemExit(f"{key} count mismatch: {checks[key]} != {expected['counts'][key]}")
    if checks["source_url_duplicates"]:
        raise SystemExit("source_url identity uniqueness failed")
    return checks


def main() -> int:
    snapshot_id = latest_snapshot_id()
    projection_dir, projection_manifest = find_projection(snapshot_id)
    source_db = projection_dir / "geds-public.sqlite"
    if not source_db.is_file():
        raise SystemExit(f"Projection database missing: {source_db}")
    output_dir = PROJECTION_ROOT / f"turso-shadow-{snapshot_id}"
    output_db = output_dir / "geds-shadow.sqlite"
    copy_projection(source_db, output_db)
    with sqlite3.connect(output_db) as con:
        create_history_tables(con)
        crawl_summary = populate_history(con, snapshot_id, projection_dir, projection_manifest)
        con.commit()
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        checks = validate(con, snapshot_id, projection_manifest)
        con.commit()
        journal_mode = str(con.execute("PRAGMA journal_mode").fetchone()[0])
        page_size = int(con.execute("PRAGMA page_size").fetchone()[0])
        auto_vacuum = int(con.execute("PRAGMA auto_vacuum").fetchone()[0])
    if journal_mode.lower() != "wal" or page_size != 4096 or auto_vacuum != 0:
        raise SystemExit(
            f"Turso file requirements failed: journal={journal_mode} page_size={page_size} auto_vacuum={auto_vacuum}"
        )
    digest = hashlib.sha256(output_db.read_bytes()).hexdigest()
    result = {
        "bundle": str(output_db),
        "bundle_bytes": output_db.stat().st_size,
        "bundle_sha256": digest,
        "snapshot_id": snapshot_id,
        "projection_manifest": projection_manifest,
        "crawl": crawl_summary,
        "checks": checks,
        "turso_requirements": {"journal_mode": journal_mode, "page_size": page_size, "auto_vacuum": auto_vacuum},
        "neon_touched": False,
    }
    (output_dir / "manifest.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
