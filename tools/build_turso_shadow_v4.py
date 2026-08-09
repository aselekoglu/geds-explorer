"""Build a Turso-ready shadow SQLite bundle without attached databases."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import build_turso_shadow as base  # noqa: E402


def dict_rows(con: sqlite3.Connection, sql: str, params: tuple = ()) -> list[dict]:
    cursor = con.execute(sql, params)
    names = [item[0] for item in cursor.description]
    return [dict(zip(names, row)) for row in cursor.fetchall()]


def build_history(con: sqlite3.Connection, snapshot_id: str, projection_dir: Path, manifest: dict) -> dict:
    with sqlite3.connect(base.MASTER_DB) as source:
        events = dict_rows(
            source,
            """SELECT id,snapshot_id,entity_type,entity_key,normalized_name,event_type,
                      occurred_at,certainty,before_json,after_json
                 FROM change_events ORDER BY id""",
        )
        person_events = dict_rows(
            source,
            """SELECT snapshot_id,person_key,event_type,occurred_at,details_json
                 FROM person_change_events ORDER BY occurred_at,person_key,event_type""",
        )
        snapshot = dict_rows(
            source,
            """SELECT snapshot_id,parent_snapshot_id,quality_status,
                      fallback_org_count,cycle_count,quality_warnings_json
                 FROM canonical_snapshots WHERE snapshot_id=?""",
            (snapshot_id,),
        )[0]

    with sqlite3.connect(base.CRAWL_DB) as source:
        run = dict_rows(
            source,
            "SELECT id,status,finished_at FROM crawl_runs ORDER BY started_at DESC LIMIT 1",
        )[0]
        queue = {
            str(row[0]): int(row[1])
            for row in source.execute(
                "SELECT status,COUNT(*) FROM crawl_queue GROUP BY status"
            ).fetchall()
        }
        crawl_errors = int(source.execute("SELECT COUNT(*) FROM crawl_errors").fetchone()[0])
        raw_counts = {
            "departments": int(source.execute("SELECT COUNT(*) FROM departments").fetchone()[0]),
            "organizations": int(source.execute("SELECT COUNT(*) FROM org_units").fetchone()[0]),
            "people": int(source.execute("SELECT COUNT(*) FROM people_index").fetchone()[0]),
        }
        queue_errors = source.execute(
            "SELECT dn FROM crawl_queue WHERE status='error' ORDER BY dn"
        ).fetchall()
        crawl_error_rows = source.execute(
            "SELECT url,error FROM crawl_errors ORDER BY id"
        ).fetchall()

    con.executemany(
        "INSERT INTO change_events VALUES (?,?,?,?,?,?,?,?,?,?)",
        [
            (
                row["id"], row["snapshot_id"], row["entity_type"], row["entity_key"],
                row["normalized_name"], row["event_type"], row["occurred_at"],
                row["certainty"], row["before_json"], row["after_json"],
            )
            for row in events
        ],
    )
    con.executemany(
        "INSERT INTO person_change_events VALUES (?,?,?,?,?)",
        [
            (row["snapshot_id"], row["person_key"], row["event_type"], row["occurred_at"], row["details_json"])
            for row in person_events
        ],
    )
    run_id = str(run["id"])
    con.execute(
        """INSERT INTO crawl_run_metadata VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            run_id,
            str(run["status"]),
            run["finished_at"],
            sum(item.stat().st_size for item in base.CRAWL_DB.parent.rglob("*") if item.is_file()),
            raw_counts["departments"], raw_counts["organizations"], raw_counts["people"],
            queue.get("done", 0), queue.get("error", 0), crawl_errors,
            str(snapshot["quality_status"]), int(snapshot["fallback_org_count"]),
            int(snapshot["cycle_count"]), str(snapshot["quality_warnings_json"]),
        ),
    )
    con.executemany(
        "INSERT INTO crawl_error_records VALUES (?,?,?,?)",
        [(run_id, "queue_error", str(row[0]), None) for row in queue_errors]
        + [(run_id, "crawl_error", str(row[0]), str(row[1])) for row in crawl_error_rows],
    )
    con.execute(
        "INSERT INTO turso_shadow_manifest VALUES (1,?,?,?,?,?,?)",
        (
            datetime.now(UTC).isoformat(), snapshot_id, snapshot["parent_snapshot_id"],
            json.dumps(manifest, ensure_ascii=False, sort_keys=True),
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
    return {"run_id": run_id, "raw_counts": raw_counts, "queue": queue, "crawl_errors": crawl_errors}


def main() -> int:
    snapshot_id = base.latest_snapshot_id()
    projection_dir, manifest = base.find_projection(snapshot_id)
    source_db = projection_dir / "geds-public.sqlite"
    output_dir = base.PROJECTION_ROOT / f"turso-shadow-{snapshot_id}-v4"
    output_db = output_dir / "geds-shadow.sqlite"
    base.copy_projection(source_db, output_db)
    with sqlite3.connect(output_db) as con:
        base.create_history_tables(con)
        crawl = build_history(con, snapshot_id, projection_dir, manifest)
        con.commit()
        con.execute("PRAGMA journal_mode=WAL")
        con.commit()
        con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        checks = base.validate(con, snapshot_id, manifest)
        con.commit()
        journal_mode = str(con.execute("PRAGMA journal_mode").fetchone()[0])
        page_size = int(con.execute("PRAGMA page_size").fetchone()[0])
        auto_vacuum = int(con.execute("PRAGMA auto_vacuum").fetchone()[0])
    if journal_mode.lower() != "wal" or page_size != 4096 or auto_vacuum != 0:
        raise SystemExit(f"Turso file requirements failed: {journal_mode=} {page_size=} {auto_vacuum=}")
    result = {
        "bundle": str(output_db),
        "bundle_bytes": output_db.stat().st_size,
        "bundle_sha256": hashlib.sha256(output_db.read_bytes()).hexdigest(),
        "snapshot_id": snapshot_id,
        "projection_manifest": manifest,
        "crawl": crawl,
        "checks": checks,
        "turso_requirements": {"journal_mode": journal_mode, "page_size": page_size, "auto_vacuum": auto_vacuum},
        "neon_touched": False,
    }
    output_dir.joinpath("manifest.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
