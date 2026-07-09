from __future__ import annotations

import sqlite3
from pathlib import Path

from .models import Department, OrgUnit, PersonIndex, QueueItem, PaginationTarget, PeoplePageItem


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

            CREATE TABLE IF NOT EXISTS pagination_orgs (
              org_dn TEXT PRIMARY KEY,
              department_dn TEXT NOT NULL,
              department_name TEXT NOT NULL,
              org_name TEXT NOT NULL,
              org_path TEXT NOT NULL,
              source_url TEXT NOT NULL,
              base_db_path TEXT NOT NULL,
              base_people_count INTEGER NOT NULL,
              status TEXT NOT NULL DEFAULT 'pending',
              pages_fetched INTEGER NOT NULL DEFAULT 0,
              people_observed INTEGER NOT NULL DEFAULT 0,
              people_inserted INTEGER NOT NULL DEFAULT 0,
              people_deduped INTEGER NOT NULL DEFAULT 0,
              last_page_url TEXT,
              started_at TEXT,
              heartbeat_at TEXT,
              finished_at TEXT,
              terminal_reason TEXT,
              last_error TEXT
            );

            CREATE TABLE IF NOT EXISTS people_page_queue (
              page_url TEXT PRIMARY KEY,
              org_dn TEXT NOT NULL,
              page_index INTEGER NOT NULL,
              status TEXT NOT NULL DEFAULT 'pending',
              attempts INTEGER NOT NULL DEFAULT 0,
              discovered_from TEXT,
              last_error TEXT,
              first_seen TEXT NOT NULL,
              completed_at TEXT,
              FOREIGN KEY (org_dn) REFERENCES pagination_orgs(org_dn)
            );

            CREATE INDEX IF NOT EXISTS idx_people_page_queue_status ON people_page_queue (status, org_dn, page_index);
            CREATE INDEX IF NOT EXISTS idx_pagination_orgs_status ON pagination_orgs (status);
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

    def seed_pagination_target(self, target: PaginationTarget, seen_at: str) -> None:
        self.db.execute(
            """
            INSERT INTO pagination_orgs (
                org_dn, department_dn, department_name, org_name, org_path, source_url,
                base_db_path, base_people_count, status, started_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)
            ON CONFLICT(org_dn) DO NOTHING
            """,
            (
                target.org.dn,
                target.org.department_dn,
                target.department_name,
                target.org.name,
                target.org.org_path,
                target.org.source_url,
                target.base_db_path,
                target.base_people_count,
                seen_at,
            ),
        )

    def enqueue_people_page(self, org_dn: str, page_url: str, page_index: int, discovered_from: str | None, seen_at: str) -> None:
        self.db.execute(
            """
            INSERT INTO people_page_queue (
                page_url, org_dn, page_index, status, discovered_from, first_seen
            )
            VALUES (?, ?, ?, 'pending', ?, ?)
            ON CONFLICT(page_url) DO NOTHING
            """,
            (page_url, org_dn, page_index, discovered_from, seen_at),
        )

    def next_pending_people_page(self, org_dn: str | None = None) -> PeoplePageItem | None:
        if org_dn:
            row = self.db.execute(
                """
                SELECT org_dn, page_url, page_index
                FROM people_page_queue
                WHERE status = 'pending' AND org_dn = ?
                ORDER BY page_index ASC
                LIMIT 1
                """,
                (org_dn,),
            ).fetchone()
        else:
            row = self.db.execute(
                """
                SELECT org_dn, page_url, page_index
                FROM people_page_queue
                WHERE status = 'pending'
                ORDER BY org_dn, page_index ASC
                LIMIT 1
                """
            ).fetchone()

        if row is None:
            return None
        return PeoplePageItem(
            org_dn=row["org_dn"],
            page_url=row["page_url"],
            page_index=row["page_index"],
        )

    def complete_people_page(
        self,
        page_url: str,
        next_url: str | None,
        people_observed: int,
        people_inserted: int,
        people_deduped: int,
        completed_at: str,
    ) -> None:
        row = self.db.execute(
            "SELECT org_dn, page_index, status FROM people_page_queue WHERE page_url = ?",
            (page_url,),
        ).fetchone()
        if not row:
            return

        if row["status"] != "pending":
            return

        org_dn = row["org_dn"]
        page_index = row["page_index"]

        self.db.execute(
            """
            UPDATE people_page_queue
            SET status = 'done', completed_at = ?
            WHERE page_url = ?
            """,
            (completed_at, page_url),
        )

        if next_url:
            self.enqueue_people_page(
                org_dn=org_dn,
                page_url=next_url,
                page_index=page_index + 1,
                discovered_from=page_url,
                seen_at=completed_at,
            )

        self.db.execute(
            """
            UPDATE pagination_orgs
            SET pages_fetched = pages_fetched + 1,
                people_observed = people_observed + ?,
                people_inserted = people_inserted + ?,
                people_deduped = people_deduped + ?,
                last_page_url = ?,
                heartbeat_at = ?,
                status = 'running'
            WHERE org_dn = ?
            """,
            (
                people_observed,
                people_inserted,
                people_deduped,
                page_url,
                completed_at,
                org_dn,
            ),
        )

    def mark_pagination_org_success(self, org_dn: str, reason: str, finished_at: str) -> None:
        self.db.execute(
            """
            UPDATE pagination_orgs
            SET status = 'finished',
                terminal_reason = ?,
                finished_at = ?,
                heartbeat_at = ?
            WHERE org_dn = ?
            """,
            (reason, finished_at, finished_at, org_dn),
        )

    def mark_pagination_org_error(self, org_dn: str, error: str, finished_at: str) -> None:
        self.db.execute(
            """
            UPDATE pagination_orgs
            SET status = 'failed',
                last_error = ?,
                finished_at = ?,
                heartbeat_at = ?
            WHERE org_dn = ?
            """,
            (error, finished_at, finished_at, org_dn),
        )

    def pagination_progress(self) -> dict[str, int | float]:
        row = self.db.execute(
            """
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN status = 'finished' THEN 1 ELSE 0 END) as finished,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed
            FROM pagination_orgs
            """
        ).fetchone()

        total = row["total"] or 0
        finished = row["finished"] or 0
        failed = row["failed"] or 0
        terminal = finished + failed
        percent = (terminal / total * 100.0) if total > 0 else 0.0

        return {
            "total_orgs": total,
            "completed_orgs": finished,
            "failed_orgs": failed,
            "terminal_orgs": terminal,
            "percent": percent,
        }

    def pagination_metrics(self) -> dict[str, int]:
        row_orgs = self.db.execute(
            """
            SELECT
                COALESCE(SUM(pages_fetched), 0) as pages_fetched,
                COALESCE(SUM(people_inserted), 0) as people_inserted,
                COALESCE(SUM(people_deduped), 0) as people_deduped
            FROM pagination_orgs
            """
        ).fetchone()

        row_pending = self.db.execute(
            "SELECT COUNT(*) FROM people_page_queue WHERE status = 'pending'"
        ).fetchone()

        active_row = self.db.execute(
            """
            SELECT org_dn
            FROM pagination_orgs
            WHERE status = 'running'
            ORDER BY heartbeat_at DESC
            LIMIT 1
            """
        ).fetchone()
        active_org = active_row["org_dn"] if active_row else None

        return {
            "pages_fetched": row_orgs["pages_fetched"],
            "known_pending_pages": row_pending[0],
            "new_people": row_orgs["people_inserted"],
            "deduped_people": row_orgs["people_deduped"],
            "active_org": active_org,
        }

    def commit(self) -> None:
        self.db.commit()
