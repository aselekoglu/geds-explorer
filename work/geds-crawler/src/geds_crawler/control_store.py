from __future__ import annotations

import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

from .models import Department


class ControlStore:
    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)
        self.con: sqlite3.Connection | None = None

    def __enter__(self) -> "ControlStore":
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.con = sqlite3.connect(self.db_path)
        self.con.row_factory = sqlite3.Row
        # Enable foreign keys
        self.con.execute("PRAGMA foreign_keys = ON")
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self.con is not None:
            self.con.close()
            self.con = None

    def commit(self) -> None:
        self.db.commit()

    @property
    def db(self) -> sqlite3.Connection:
        if self.con is None:
            raise RuntimeError("ControlStore must be used as a context manager")
        return self.con

    def init_schema(self) -> None:
        # Set journal mode to WAL
        self.db.execute("PRAGMA journal_mode=WAL")
        
        self.db.executescript(
            """
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY
            );
            
            CREATE TABLE IF NOT EXISTS department_catalog (
                dn TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                source_url TEXT NOT NULL,
                last_seen TEXT
            );

            CREATE TABLE IF NOT EXISTS crawl_jobs (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                rate_limit_seconds REAL NOT NULL,
                traffic_policy TEXT NOT NULL,
                output_dir TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS job_departments (
                job_id TEXT NOT NULL,
                department_dn TEXT NOT NULL,
                PRIMARY KEY (job_id, department_dn),
                FOREIGN KEY (job_id) REFERENCES crawl_jobs (id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS crawl_runs (
                id TEXT PRIMARY KEY,
                job_id TEXT,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                status TEXT NOT NULL,
                request_count INTEGER NOT NULL DEFAULT 0,
                pid INTEGER,
                stop_requested INTEGER NOT NULL DEFAULT 0,
                output_dir TEXT NOT NULL,
                FOREIGN KEY (job_id) REFERENCES crawl_jobs (id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS run_departments (
                run_id TEXT NOT NULL,
                department_dn TEXT NOT NULL,
                PRIMARY KEY (run_id, department_dn),
                FOREIGN KEY (run_id) REFERENCES crawl_runs (id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS schedules (
                id TEXT PRIMARY KEY,
                job_id TEXT NOT NULL,
                expression TEXT NOT NULL,
                timezone TEXT NOT NULL DEFAULT 'America/Toronto',
                overlap_policy TEXT NOT NULL DEFAULT 'skip',
                enabled INTEGER NOT NULL DEFAULT 1,
                next_run_at TEXT,
                FOREIGN KEY (job_id) REFERENCES crawl_jobs (id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS controller_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS rate_gate (
                key TEXT PRIMARY KEY,
                value TEXT
            );
            """
        )
        
        # Initialize schema version if empty
        row = self.db.execute("SELECT version FROM schema_version").fetchone()
        if row is None:
            self.db.execute("INSERT INTO schema_version (version) VALUES (1)")
            
        self.db.commit()

    def create_job(
        self,
        name: str,
        department_dns: set[str],
        rate_limit_seconds: float,
        traffic_policy: str,
        output_dir: str,
    ) -> str:
        job_id = str(uuid.uuid4())
        created_at = datetime.now(UTC).isoformat()
        
        self.db.execute(
            """
            INSERT INTO crawl_jobs (id, name, created_at, rate_limit_seconds, traffic_policy, output_dir, enabled)
            VALUES (?, ?, ?, ?, ?, ?, 1)
            """,
            (job_id, name, created_at, rate_limit_seconds, traffic_policy, output_dir),
        )
        
        for dn in department_dns:
            self.db.execute(
                "INSERT INTO job_departments (job_id, department_dn) VALUES (?, ?)",
                (job_id, dn),
            )
            
        self.db.commit()
        return job_id

    def create_run(self, job_id: str, status: str = "queued") -> str:
        run_id = str(uuid.uuid4())
        started_at = datetime.now(UTC).isoformat()
        
        # Retrieve output_dir from job
        job_row = self.db.execute("SELECT output_dir FROM crawl_jobs WHERE id=?", (job_id,)).fetchone()
        if job_row is None:
            raise ValueError(f"Job not found: {job_id}")
            
        output_dir = job_row["output_dir"]
        
        self.db.execute(
            """
            INSERT INTO crawl_runs (id, job_id, started_at, status, output_dir)
            VALUES (?, ?, ?, ?, ?)
            """,
            (run_id, job_id, started_at, status, output_dir),
        )
        
        # Copy job departments to run departments
        self.db.execute(
            """
            INSERT INTO run_departments (run_id, department_dn)
            SELECT ?, department_dn FROM job_departments WHERE job_id=?
            """,
            (run_id, job_id),
        )
        
        self.db.commit()
        return run_id

    def list_runs(self) -> list[dict]:
        rows = self.db.execute(
            """
            SELECT r.*, j.name AS job_name
            FROM crawl_runs r
            LEFT JOIN crawl_jobs j ON j.id = r.job_id
            ORDER BY r.started_at DESC
            """
        ).fetchall()
        return [dict(row) for row in rows]

    def request_stop(self, run_id: str) -> None:
        self.db.execute(
            "UPDATE crawl_runs SET stop_requested = 1, status = 'stopping' WHERE id = ?",
            (run_id,),
        )
        self.db.commit()

    def upsert_catalog(self, departments: list[Department]) -> None:
        now = datetime.now(UTC).isoformat()
        for dept in departments:
            self.db.execute(
                """
                INSERT INTO department_catalog (dn, name, source_url, last_seen)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(dn) DO UPDATE SET
                    name=excluded.name,
                    source_url=excluded.source_url,
                    last_seen=excluded.last_seen
                """,
                (dept.dn, dept.name, dept.source_url, now),
            )
        self.db.commit()

    def get_all_remaining_dns(self) -> set[str]:
        rows = self.db.execute(
            """
            SELECT dn FROM department_catalog
            WHERE dn NOT IN (
                SELECT jd.department_dn
                FROM job_departments jd
                JOIN crawl_jobs j ON j.id = jd.job_id
                WHERE j.enabled = 1
            )
            """
        ).fetchall()
        return {row["dn"] for row in rows}

    def coverage(self) -> dict[str, dict[str, str | None]]:
        # Get all departments in the catalog
        cat_rows = self.db.execute("SELECT dn FROM department_catalog").fetchall()
        dns = {row["dn"] for row in cat_rows}
        
        # Initialize map
        status_map = {
            dn: {
                "status": "unassigned",
                "job_name": None,
                "last_crawled_at": None
            } for dn in dns
        }
        
        # 1. Map job names to departments
        job_dn_map = {}
        job_rows = self.db.execute(
            """
            SELECT jd.department_dn, j.name as job_name, j.enabled
            FROM job_departments jd
            JOIN crawl_jobs j ON j.id = jd.job_id
            """
        ).fetchall()
        for row in job_rows:
            dn = row["department_dn"]
            if dn not in job_dn_map:
                job_dn_map[dn] = []
            job_dn_map[dn].append((row["job_name"], row["enabled"]))
            
        # 2. Get active runs (running or queued)
        run_rows = self.db.execute(
            """
            SELECT rd.department_dn, r.status, r.id, j.name as job_name
            FROM run_departments rd
            JOIN crawl_runs r ON r.id = rd.run_id
            LEFT JOIN crawl_jobs j ON j.id = r.job_id
            WHERE r.status IN ('running', 'queued', 'stopping')
            """
        ).fetchall()
        
        active_runs_map = {}
        for row in run_rows:
            dn = row["department_dn"]
            if dn not in active_runs_map:
                active_runs_map[dn] = []
            active_runs_map[dn].append((row["status"], row["job_name"]))
            
        # 3. Get last completed runs
        last_run_rows = self.db.execute(
            """
            SELECT rd.department_dn, r.status, r.finished_at, r.started_at, j.name as job_name
            FROM run_departments rd
            JOIN crawl_runs r ON r.id = rd.run_id
            LEFT JOIN crawl_jobs j ON j.id = r.job_id
            WHERE r.status IN ('finished', 'failed', 'stopped')
            ORDER BY r.finished_at DESC
            """
        ).fetchall()
        latest_completed = {}
        for row in last_run_rows:
            dn = row["department_dn"]
            if dn not in latest_completed:
                latest_completed[dn] = row
                
        # 4. Get scheduled jobs
        sched_rows = self.db.execute(
            """
            SELECT jd.department_dn
            FROM job_departments jd
            JOIN schedules s ON s.job_id = jd.job_id
            WHERE s.enabled = 1
            """
        ).fetchall()
        scheduled_dns = {row["department_dn"] for row in sched_rows}

        # 5. Load unmanaged crawl data if it exists
        unmanaged_dns = set()
        unmanaged_status = "idle"
        unmanaged_date = None
        fb = (self.db_path.parent.parent / "runs" / "2026-07-08" / "unmanaged-crawl" / "geds.sqlite").resolve()
        if not fb.is_file():
            fb = (self.db_path.parent.parent / "geds-snapshot-2026-07-08" / "geds.sqlite").resolve()
        if fb.is_file():
            try:
                with sqlite3.connect(fb) as conn:
                    u_depts = conn.execute("SELECT dn FROM departments").fetchall()
                    unmanaged_dns = {r[0] for r in u_depts}
                    u_run = conn.execute(
                        "SELECT status, started_at, finished_at FROM crawl_runs ORDER BY started_at DESC LIMIT 1"
                    ).fetchone()
                    if u_run:
                        unmanaged_status = u_run[0]
                        unmanaged_date = u_run[2] or u_run[1]
                        if unmanaged_date:
                            unmanaged_date = unmanaged_date.split("T")[0]
            except Exception:
                pass

        # Calculate status for each DN
        for dn in dns:
            # Check unmanaged first if in catalog
            if dn in unmanaged_dns:
                status_map[dn]["job_name"] = "Unmanaged Crawl"
                status_map[dn]["last_crawled_at"] = unmanaged_date
                if unmanaged_status in ("running", "stopping"):
                    status_map[dn]["status"] = "running"
                elif unmanaged_status == "finished":
                    status_map[dn]["status"] = "covered-current"
                else:
                    status_map[dn]["status"] = "failed"
                # Active managed runs override unmanaged
                if dn in active_runs_map:
                    active_info = active_runs_map[dn][0]
                    status_map[dn]["status"] = active_info[0]
                    status_map[dn]["job_name"] = active_info[1] or "Unmanaged Crawl"
                continue

            # Overlap check
            jobs = job_dn_map.get(dn, [])
            enabled_jobs_count = sum(1 for j in jobs if j[1] == 1)
            if enabled_jobs_count > 1:
                status_map[dn]["status"] = "overlap"
                status_map[dn]["job_name"] = ", ".join(j[0] for j in jobs if j[1] == 1)
                continue
                
            # If active runs exist
            if dn in active_runs_map:
                active_info = active_runs_map[dn][0]
                status_map[dn]["status"] = active_info[0]
                status_map[dn]["job_name"] = active_info[1]
                continue
                
            # Check latest completed run
            if dn in latest_completed:
                last_run = latest_completed[dn]
                status_map[dn]["job_name"] = last_run["job_name"]
                crawl_date = last_run["finished_at"] or last_run["started_at"]
                if crawl_date:
                    status_map[dn]["last_crawled_at"] = crawl_date.split("T")[0]
                
                if last_run["status"] == "finished":
                    status_map[dn]["status"] = "covered-current"
                    continue
                elif last_run["status"] in ("failed", "stopped"):
                    status_map[dn]["status"] = "failed"
                    continue
                    
            # If assigned to enabled job, check if scheduled or just assigned
            if enabled_jobs_count == 1:
                status_map[dn]["status"] = "scheduled"
                status_map[dn]["job_name"] = [j[0] for j in jobs if j[1] == 1][0]
                continue
                
        return status_map

