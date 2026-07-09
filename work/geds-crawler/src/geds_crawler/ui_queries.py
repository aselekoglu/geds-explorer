from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Sequence


class SnapshotReader:
    def __init__(self, db_path: Path | str, overlay_db_paths: Sequence[Path | str] = ()):
        self.db_path = Path(db_path).resolve()
        if not self.db_path.is_file():
            raise FileNotFoundError(f"Database not found: {self.db_path}")
        self.overlay_db_paths = [Path(p).resolve() for p in overlay_db_paths]
        for p in self.overlay_db_paths:
            if not p.is_file():
                raise FileNotFoundError(f"Overlay database not found: {p}")

    def _connect_with_overlays(self) -> sqlite3.Connection:
        con = sqlite3.connect(":memory:")
        con.row_factory = sqlite3.Row
        con.execute("ATTACH DATABASE ? AS base", (str(self.db_path),))
        for idx, path in enumerate(self.overlay_db_paths):
            con.execute(f"ATTACH DATABASE ? AS overlay_{idx}", (str(path),))
        return con

    def _people_source_sql(self) -> str:
        parts = [
            "SELECT 0 AS precedence, display_name, title, department_name, org_unit, org_path, source_url, last_seen, org_dn, department_dn FROM base.people_index"
        ]
        for idx in range(len(self.overlay_db_paths)):
            parts.append(
                f"SELECT {idx + 1} AS precedence, display_name, title, department_name, org_unit, org_path, source_url, last_seen, org_dn, department_dn FROM overlay_{idx}.people_index"
            )
        union_sql = "\n  UNION ALL\n  ".join(parts)
        
        return f"""
        WITH all_people AS (
          {union_sql}
        ),
        ranked AS (
          SELECT display_name, title, department_name, org_unit, org_path, source_url, last_seen, org_dn, department_dn,
                 ROW_NUMBER() OVER (
                   PARTITION BY source_url ORDER BY precedence DESC, last_seen DESC
                 ) AS rn
          FROM all_people
        )
        SELECT display_name, title, department_name, org_unit, org_path, source_url, org_dn, department_dn
        FROM ranked
        WHERE rn = 1
        """

    def status(self) -> dict[str, Any]:
        with self._connect() as con:
            crawl_kind = "full"
            try:
                run = con.execute(
                    "SELECT request_count, status, crawl_kind FROM crawl_runs ORDER BY started_at DESC LIMIT 1"
                ).fetchone()
                if run:
                    crawl_kind = run["crawl_kind"] or "full"
            except sqlite3.OperationalError:
                run = con.execute(
                    "SELECT request_count, status FROM crawl_runs ORDER BY started_at DESC LIMIT 1"
                ).fetchone()
            
            # Read status/request_count from latest overlay if present
            if self.overlay_db_paths:
                try:
                    # open read-only
                    with sqlite3.connect(f"file:{self.overlay_db_paths[-1].as_posix()}?mode=ro", uri=True) as o_con:
                        o_con.row_factory = sqlite3.Row
                        o_run = o_con.execute(
                            "SELECT request_count, status, crawl_kind FROM crawl_runs ORDER BY started_at DESC LIMIT 1"
                        ).fetchone()
                        if o_run:
                            run = o_run
                            if "crawl_kind" in o_run.keys():
                                crawl_kind = o_run["crawl_kind"] or "full"
                except Exception:
                    pass

            queue = {
                str(row["status"]): int(row["count"])
                for row in con.execute(
                    "SELECT status, COUNT(*) AS count FROM crawl_queue GROUP BY status"
                )
            }

            if crawl_kind == "pagination_backfill" and self.overlay_db_paths:
                try:
                    with sqlite3.connect(f"file:{self.overlay_db_paths[-1].as_posix()}?mode=ro", uri=True) as o_con:
                        o_con.row_factory = sqlite3.Row
                        o_queue = {"done": 0, "pending": 0, "error": 0}
                        rows = o_con.execute(
                            "SELECT status, COUNT(*) AS count FROM pagination_orgs GROUP BY status"
                        ).fetchall()
                        for row in rows:
                            status_val = row["status"]
                            count_val = int(row["count"])
                            if status_val == "completed":
                                o_queue["done"] += count_val
                            elif status_val == "failed":
                                o_queue["error"] += count_val
                            else:
                                o_queue["pending"] += count_val
                        queue = o_queue
                except Exception:
                    pass
            elif self.overlay_db_paths:
                try:
                    with sqlite3.connect(f"file:{self.overlay_db_paths[-1].as_posix()}?mode=ro", uri=True) as o_con:
                        o_con.row_factory = sqlite3.Row
                        o_queue = {
                            str(row["status"]): int(row["count"])
                            for row in o_con.execute(
                                "SELECT status, COUNT(*) AS count FROM crawl_queue GROUP BY status"
                            )
                        }
                        if o_queue:
                            queue = o_queue
                except Exception:
                    pass

            done = queue.get("done", 0)
            pending = queue.get("pending", 0)
            failed = queue.get("error", 0)
            total = done + pending + failed
            completion = round((done + failed) * 100 / total, 1) if total else 0.0
            
            if self.overlay_db_paths:
                with self._connect_with_overlays() as m_con:
                    source_sql = self._people_source_sql()
                    people_count = int(m_con.execute(f"SELECT COUNT(*) FROM ({source_sql})").fetchone()[0])
            else:
                people_count = self._count(con, "people_index")

            errors = self._count(con, "crawl_errors")
            if self.overlay_db_paths:
                try:
                    with sqlite3.connect(f"file:{self.overlay_db_paths[-1].as_posix()}?mode=ro", uri=True) as o_con:
                        errors = int(o_con.execute("SELECT COUNT(*) FROM crawl_errors").fetchone()[0])
                except Exception:
                    pass

            return {
                "run_status": str(run["status"]) if run else None,
                "request_count": int(run["request_count"]) if run else 0,
                "departments": self._count(con, "departments"),
                "org_units": self._count(con, "org_units"),
                "people": people_count,
                "errors": errors,
                "queue": queue,
                "completion_percent": completion,
            }

    def departments(self) -> list[str]:
        with self._connect() as con:
            return [
                str(row["name"])
                for row in con.execute("SELECT name FROM departments ORDER BY name COLLATE NOCASE")
            ]

    def orgs(
        self,
        *,
        query: str = "",
        department: str = "",
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        clauses: list[str] = []
        params: list[Any] = []
        if query:
            pattern = self._like(query)
            clauses.append("(o.name LIKE ? ESCAPE '\\' OR o.org_path LIKE ? ESCAPE '\\')")
            params.extend((pattern, pattern))
        if department:
            clauses.append("d.name = ?")
            params.append(department)
        return self._page(
            """
            SELECT o.name, d.name AS department_name, o.depth, o.org_path, o.source_url
            FROM org_units o
            JOIN departments d ON d.dn = o.department_dn
            """,
            clauses,
            params,
            "o.org_path COLLATE NOCASE",
            limit,
            offset,
        )

    def people(
        self,
        *,
        query: str = "",
        department: str = "",
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        clauses: list[str] = []
        params: list[Any] = []
        if query:
            pattern = self._like(query)
            clauses.append(
                "("
                "display_name LIKE ? ESCAPE '\\' OR "
                "title LIKE ? ESCAPE '\\' OR "
                "org_unit LIKE ? ESCAPE '\\' OR "
                "org_path LIKE ? ESCAPE '\\'"
                ")"
            )
            params.extend((pattern, pattern, pattern, pattern))
        if department:
            clauses.append("department_name = ?")
            params.append(department)

        source_sql = self._people_source_sql()
        bounded_limit = min(max(int(limit), 1), 100)
        bounded_offset = max(int(offset), 0)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""

        with self._connect_with_overlays() as con:
            total = int(
                con.execute(
                    f"SELECT COUNT(*) FROM ({source_sql}){where}",
                    params,
                ).fetchone()[0]
            )
            rows = con.execute(
                f"SELECT display_name, title, department_name, org_unit, org_path, source_url FROM ({source_sql}){where} ORDER BY display_name COLLATE NOCASE, org_path COLLATE NOCASE LIMIT ? OFFSET ?",
                [*params, bounded_limit, bounded_offset],
            ).fetchall()

        return {
            "items": [dict(row) for row in rows],
            "total": total,
            "limit": bounded_limit,
            "offset": bounded_offset,
        }

    def queue(
        self,
        *,
        query: str = "",
        department: str = "",
        status: str = "",
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        clauses: list[str] = []
        params: list[Any] = []
        if query:
            pattern = self._like(query)
            clauses.append("(org_name LIKE ? ESCAPE '\\' OR org_path LIKE ? ESCAPE '\\')")
            params.extend((pattern, pattern))
        if department:
            clauses.append("department_name = ?")
            params.append(department)
        if status:
            clauses.append("status = ?")
            params.append(status)
        return self._page(
            """
            SELECT org_name, department_name, depth, status, attempts, org_path, url AS source_url, last_error
            FROM crawl_queue
            """,
            clauses,
            params,
            """
            CASE status WHEN 'error' THEN 0 WHEN 'pending' THEN 1 ELSE 2 END,
            depth,
            org_path COLLATE NOCASE
            """,
            limit,
            offset,
        )

    def errors(
        self,
        *,
        query: str = "",
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        clauses: list[str] = []
        params: list[Any] = []
        if query:
            pattern = self._like(query)
            clauses.append("(error LIKE ? ESCAPE '\\' OR url LIKE ? ESCAPE '\\')")
            params.extend((pattern, pattern))
        return self._page(
            """
            SELECT url AS source_url, error, attempts, created_at
            FROM crawl_errors
            """,
            clauses,
            params,
            "created_at DESC, source_url",
            limit,
            offset,
        )

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(f"file:{self.db_path.as_posix()}?mode=ro", uri=True, timeout=2)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA query_only=ON")
        con.execute("PRAGMA busy_timeout=2000")
        return con

    def _page(
        self,
        select_sql: str,
        clauses: list[str],
        params: list[Any],
        order_by: str,
        limit: int,
        offset: int,
    ) -> dict[str, Any]:
        bounded_limit = min(max(int(limit), 1), 100)
        bounded_offset = max(int(offset), 0)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._connect() as con:
            total = int(
                con.execute(
                    f"SELECT COUNT(*) FROM ({select_sql}{where})",
                    params,
                ).fetchone()[0]
            )
            rows = con.execute(
                f"{select_sql}{where} ORDER BY {order_by} LIMIT ? OFFSET ?",
                [*params, bounded_limit, bounded_offset],
            ).fetchall()
        return {
            "items": [dict(row) for row in rows],
            "total": total,
            "limit": bounded_limit,
            "offset": bounded_offset,
        }

    @staticmethod
    def _count(con: sqlite3.Connection, table: str) -> int:
        return int(con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])

    @staticmethod
    def _like(value: str) -> str:
        escaped = value.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        return f"%{escaped}%"
