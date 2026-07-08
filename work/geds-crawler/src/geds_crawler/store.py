from __future__ import annotations

import sqlite3
from pathlib import Path

from .models import Department, OrgUnit, PersonIndex, QueueItem


class SnapshotStore:
    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)
        self.con: sqlite3.Connection | None = None

    def __enter__(self) -> "SnapshotStore":
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.con = sqlite3.connect(self.db_path)
        self.con.row_factory = sqlite3.Row
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self.con is not None:
            self.con.close()
            self.con = None

    @property
    def db(self) -> sqlite3.Connection:
        if self.con is None:
            raise RuntimeError("SnapshotStore must be used as a context manager")
        return self.con

    def init_schema(self) -> None:
        self.db.executescript(
            """
            PRAGMA journal_mode=WAL;

            CREATE TABLE IF NOT EXISTS crawl_runs (
              id TEXT PRIMARY KEY,
              started_at TEXT NOT NULL,
              finished_at TEXT,
              request_count INTEGER NOT NULL DEFAULT 0,
              status TEXT NOT NULL,
              heartbeat_at TEXT,
              current_org_dn TEXT,
              current_department_dn TEXT,
              stop_reason TEXT,
              rate_limit_seconds REAL NOT NULL DEFAULT 1.0
            );

            CREATE TABLE IF NOT EXISTS departments (
              dn TEXT PRIMARY KEY,
              name TEXT NOT NULL,
              source_url TEXT NOT NULL,
              first_seen TEXT NOT NULL,
              last_seen TEXT NOT NULL,
              crawl_run_id TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS org_units (
              dn TEXT PRIMARY KEY,
              name TEXT NOT NULL,
              parent_dn TEXT,
              department_dn TEXT NOT NULL,
              depth INTEGER NOT NULL,
              org_path TEXT NOT NULL,
              source_url TEXT NOT NULL,
              first_seen TEXT NOT NULL,
              last_seen TEXT NOT NULL,
              crawl_run_id TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS people_index (
              source_url TEXT PRIMARY KEY,
              display_name TEXT NOT NULL,
              title TEXT,
              org_dn TEXT NOT NULL,
              department_dn TEXT NOT NULL,
              department_name TEXT NOT NULL,
              org_unit TEXT NOT NULL,
              org_path TEXT NOT NULL,
              first_seen TEXT NOT NULL,
              last_seen TEXT NOT NULL,
              crawl_run_id TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS crawl_queue (
              dn TEXT PRIMARY KEY,
              url TEXT NOT NULL,
              department_dn TEXT NOT NULL,
              department_name TEXT NOT NULL,
              org_name TEXT NOT NULL,
              org_path TEXT NOT NULL,
              parent_dn TEXT,
              depth INTEGER NOT NULL,
              status TEXT NOT NULL,
              attempts INTEGER NOT NULL DEFAULT 0,
              last_error TEXT
            );

            CREATE TABLE IF NOT EXISTS crawl_errors (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              url TEXT NOT NULL,
              error TEXT NOT NULL,
              attempts INTEGER NOT NULL,
              created_at TEXT NOT NULL,
              crawl_run_id TEXT NOT NULL
            );
            """
        )
        self.db.commit()

    def upsert_department(self, department: Department, crawl_run_id: str, seen_at: str) -> None:
        self.db.execute(
            """
            INSERT INTO departments (dn, name, source_url, first_seen, last_seen, crawl_run_id)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(dn) DO UPDATE SET
              name=excluded.name,
              source_url=excluded.source_url,
              last_seen=excluded.last_seen,
              crawl_run_id=excluded.crawl_run_id
            """,
            (department.dn, department.name, department.source_url, seen_at, seen_at, crawl_run_id),
        )

    def upsert_org_unit(self, org: OrgUnit, crawl_run_id: str, seen_at: str) -> None:
        self.db.execute(
            """
            INSERT INTO org_units
              (dn, name, parent_dn, department_dn, depth, org_path, source_url, first_seen, last_seen, crawl_run_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(dn) DO UPDATE SET
              name=excluded.name,
              parent_dn=excluded.parent_dn,
              department_dn=excluded.department_dn,
              depth=excluded.depth,
              org_path=excluded.org_path,
              source_url=excluded.source_url,
              last_seen=excluded.last_seen,
              crawl_run_id=excluded.crawl_run_id
            """,
            (
                org.dn,
                org.name,
                org.parent_dn,
                org.department_dn,
                org.depth,
                org.org_path,
                org.source_url,
                seen_at,
                seen_at,
                crawl_run_id,
            ),
        )

    def upsert_person(self, person: PersonIndex, crawl_run_id: str, seen_at: str) -> None:
        self.db.execute(
            """
            INSERT INTO people_index
              (source_url, display_name, title, org_dn, department_dn, department_name, org_unit, org_path,
               first_seen, last_seen, crawl_run_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_url) DO UPDATE SET
              display_name=excluded.display_name,
              title=excluded.title,
              org_dn=excluded.org_dn,
              department_dn=excluded.department_dn,
              department_name=excluded.department_name,
              org_unit=excluded.org_unit,
              org_path=excluded.org_path,
              last_seen=excluded.last_seen,
              crawl_run_id=excluded.crawl_run_id
            """,
            (
                person.source_url,
                person.display_name,
                person.title,
                person.org_dn,
                person.department_dn,
                person.department_name,
                person.org_unit,
                person.org_path,
                seen_at,
                seen_at,
                crawl_run_id,
            ),
        )

    def enqueue_org(self, org: OrgUnit, department_name: str) -> None:
        self.db.execute(
            """
            INSERT INTO crawl_queue
              (dn, url, department_dn, department_name, org_name, org_path, parent_dn, depth, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending')
            ON CONFLICT(dn) DO NOTHING
            """,
            (
                org.dn,
                org.source_url,
                org.department_dn,
                department_name,
                org.name,
                org.org_path,
                org.parent_dn,
                org.depth,
            ),
        )

    def next_pending_org(self) -> QueueItem | None:
        row = self.db.execute(
            """
            SELECT dn, url, department_dn, department_name, org_name, org_path, parent_dn, depth
            FROM crawl_queue
            WHERE status = 'pending'
            ORDER BY depth, org_path
            LIMIT 1
            """
        ).fetchone()
        if row is None:
            return None

        return QueueItem(
            org=OrgUnit(
                name=row["org_name"],
                dn=row["dn"],
                parent_dn=row["parent_dn"],
                department_dn=row["department_dn"],
                depth=row["depth"],
                org_path=row["org_path"],
                source_url=row["url"],
            ),
            department_name=row["department_name"],
        )

    def mark_org_done(self, dn: str) -> None:
        self.db.execute("UPDATE crawl_queue SET status = 'done', last_error = NULL WHERE dn = ?", (dn,))

    def mark_org_error(self, dn: str, error: str) -> None:
        self.db.execute(
            "UPDATE crawl_queue SET status = 'error', attempts = attempts + 1, last_error = ? WHERE dn = ?",
            (error, dn),
        )

    def update_run_progress(
        self,
        run_id: str,
        request_count: int,
        status: str,
        heartbeat_at: str | None = None,
        current_org_dn: str | None = None,
        current_department_dn: str | None = None,
        stop_reason: str | None = None,
    ) -> None:
        self.db.execute(
            """
            UPDATE crawl_runs
            SET request_count = ?,
                status = ?,
                heartbeat_at = COALESCE(?, heartbeat_at),
                current_org_dn = COALESCE(?, current_org_dn),
                current_department_dn = COALESCE(?, current_department_dn),
                stop_reason = COALESCE(?, stop_reason)
            WHERE id = ?
            """,
            (
                request_count,
                status,
                heartbeat_at,
                current_org_dn,
                current_department_dn,
                stop_reason,
                run_id,
            ),
        )

    def count_rows(self, table: str) -> int:
        allowed = {"departments", "org_units", "people_index", "crawl_errors"}
        if table not in allowed:
            raise ValueError(f"unsupported table: {table}")
        return int(self.db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])

    def queue_counts(self) -> dict[str, int]:
        return {
            row["status"]: int(row["count"])
            for row in self.db.execute("SELECT status, COUNT(*) AS count FROM crawl_queue GROUP BY status")
        }

    def commit(self) -> None:
        self.db.commit()
