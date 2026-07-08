from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(frozen=True)
class SnapshotStatus:
    departments: int
    org_units: int
    people: int
    errors: int
    request_count: int
    queue: dict[str, int]
    run_status: str | None


def read_snapshot_status(db_path: Path | str) -> SnapshotStatus:
    resolved = Path(db_path).resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"Database not found: {resolved}")

    con = sqlite3.connect(f"file:{resolved}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    queue = {row["status"]: row["count"] for row in con.execute("SELECT status, COUNT(*) AS count FROM crawl_queue GROUP BY status")}
    run = con.execute("SELECT request_count, status FROM crawl_runs ORDER BY started_at DESC LIMIT 1").fetchone()

    return SnapshotStatus(
        departments=_count(con, "departments"),
        org_units=_count(con, "org_units"),
        people=_count(con, "people_index"),
        errors=_count(con, "crawl_errors"),
        request_count=int(run["request_count"]) if run else 0,
        queue=queue,
        run_status=str(run["status"]) if run else None,
    )


def format_status(status: SnapshotStatus) -> str:
    queue = " ".join(f"{name}={count}" for name, count in sorted(status.queue.items())) or "queue=empty"
    return (
        f"status={status.run_status or 'unknown'} requests={status.request_count} "
        f"departments={status.departments} orgs={status.org_units} people={status.people} "
        f"errors={status.errors} {queue}"
    )


def format_progress_line(
    *,
    event: str,
    org_path: str,
    depth: int,
    request_count: int,
    org_count: int,
    people_count: int,
    queue_done: int,
    queue_pending: int,
    error_count: int,
) -> str:
    stamp = datetime.now(UTC).isoformat(timespec="seconds")
    return (
        f"[{stamp}] {event} depth={depth} requests={request_count} "
        f"orgs={org_count} people={people_count} done={queue_done} "
        f"pending={queue_pending} errors={error_count} org=\"{org_path}\""
    )


def _count(con: sqlite3.Connection, table: str) -> int:
    return int(con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
