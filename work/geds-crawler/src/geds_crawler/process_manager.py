from __future__ import annotations

import os
import subprocess
import sys
import sqlite3
from datetime import UTC, datetime
from pathlib import Path


class ProcessManager:
    def __init__(self, control_db_path: Path | str):
        self.control_db_path = Path(control_db_path).resolve()

    def _resolve_output_dir(self, output_dir: str | Path) -> Path:
        path = Path(output_dir)
        if path.is_absolute():
            return path
        return self.control_db_path.parents[2] / path

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.control_db_path)
        con.row_factory = sqlite3.Row
        return con

    def start_run(self, run_id: str, stop_file: Path | None = None, cmd_args: list[str] | None = None) -> int:
        with self._connect() as con:
            run_row = con.execute(
                """
                SELECT r.id, r.output_dir, j.rate_limit_seconds, j.enabled, r.crawl_kind, r.source_db_path
                FROM crawl_runs r
                LEFT JOIN crawl_jobs j ON j.id = r.job_id
                WHERE r.id = ?
                """,
                (run_id,),
            ).fetchone()
            if not run_row:
                raise ValueError(f"Run not found: {run_id}")
                
            output_dir = self._resolve_output_dir(run_row["output_dir"])
            rate_limit = run_row["rate_limit_seconds"] or 1.0
            crawl_kind = run_row["crawl_kind"] or "full"
            
            # Fetch departments
            dept_rows = con.execute(
                "SELECT department_dn FROM run_departments WHERE run_id = ?",
                (run_id,),
            ).fetchall()
            dept_dns = [row["department_dn"] for row in dept_rows]
            
        output_dir.mkdir(parents=True, exist_ok=True)
        if stop_file is None:
            stop_file = output_dir / "stop_signal"
            
        # If stop file exists from a previous run, clear it
        if stop_file.exists():
            try:
                stop_file.unlink()
            except Exception:
                pass

        # Build execution command
        if cmd_args is None:
            cmd = [
                sys.executable,
                "-m",
                "geds_crawler.worker_cli",
                "--run-id",
                run_id,
                "--output-dir",
                str(output_dir),
                "--rate-limit",
                str(rate_limit),
                "--stop-file",
                str(stop_file),
                "--crawl-kind",
                crawl_kind,
                "--control-db",
                str(self.control_db_path),
            ]
            if crawl_kind == "full":
                if dept_dns:
                    cmd.append("--department-dns")
                    cmd.extend(dept_dns)
        else:
            cmd = cmd_args

        # Redirect stdout/stderr to logs
        stdout_log = open(output_dir / "worker.stdout.log", "w", encoding="utf-8")
        stderr_log = open(output_dir / "worker.stderr.log", "w", encoding="utf-8")

        kwargs = {
            "stdout": stdout_log,
            "stderr": stderr_log,
            "text": True,
            "close_fds": True,
            "env": {
                **os.environ,
                "PYTHONIOENCODING": "utf-8",
                "PYTHONUTF8": "1",
            },
        }
        if os.name == "nt":
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP

        proc = subprocess.Popen(cmd, **kwargs)
        
        # Close file handles in parent
        stdout_log.close()
        stderr_log.close()
        
        # Save PID to control DB and update status to running
        with self._connect() as con:
            con.execute(
                "UPDATE crawl_runs SET pid = ?, status = 'running', stop_requested = 0 WHERE id = ?",
                (proc.pid, run_id),
            )
            con.commit()
            
        return proc.pid

    def try_start_run(self, run_id: str, global_budget_rps: float = 1.0, acknowledged: bool = False) -> str:
        with self._connect() as con:
            row = con.execute(
                """
                SELECT r.status, j.traffic_policy, j.rate_limit_seconds
                FROM crawl_runs r
                JOIN crawl_jobs j ON j.id = r.job_id
                WHERE r.id = ?
                """,
                (run_id,),
            ).fetchone()
        if row is None:
            raise ValueError(f"Run not found: {run_id}")
        if row["status"] != "queued":
            return row["status"]

        policy = row["traffic_policy"]
        if policy == "queue":
            from .traffic import calculate_configured_rps, can_start

            rate_limit = float(row["rate_limit_seconds"] or 1.0)
            projected_rps = calculate_configured_rps(self.control_db_path)
            if rate_limit > 0:
                projected_rps += 1.0 / rate_limit
            decision = can_start(projected_rps, budget_rps=global_budget_rps, acknowledged=acknowledged)
            if decision == "block":
                return "queued"

        self.start_run(run_id)
        return "running"

    def start_queued_runs(self, global_budget_rps: float = 1.0) -> None:
        with self._connect() as con:
            rows = con.execute(
                """
                SELECT r.id
                FROM crawl_runs r
                JOIN crawl_jobs j ON j.id = r.job_id
                WHERE r.status = 'queued' AND j.enabled = 1
                ORDER BY r.started_at ASC
                """
            ).fetchall()

        for row in rows:
            status = self.try_start_run(row["id"], global_budget_rps=global_budget_rps)
            if status == "queued":
                break

    def stop_run(self, run_id: str, force: bool = False) -> None:
        with self._connect() as con:
            run_row = con.execute(
                "SELECT id, pid, output_dir, status FROM crawl_runs WHERE id = ?",
                (run_id,),
            ).fetchone()
            if not run_row:
                return
                
            pid = run_row["pid"]
            output_dir = Path(run_row["output_dir"])
            
        if not force:
            # Set stop_requested and status = 'stopping'
            with self._connect() as con:
                con.execute(
                    "UPDATE crawl_runs SET stop_requested = 1, status = 'stopping' WHERE id = ?",
                    (run_id,),
                )
                con.commit()
                
            # Write stop file to signal cooperative stop
            stop_file = output_dir / "stop_signal"
            try:
                stop_file.write_text("stop", encoding="utf-8")
            except Exception:
                pass
        else:
            # Force kill process
            if pid:
                try:
                    import signal
                    # On Windows, SIGTERM is supported by os.kill
                    os.kill(pid, signal.SIGTERM)
                except OSError:
                    pass
            with self._connect() as con:
                con.execute(
                    "UPDATE crawl_runs SET status = 'stopped' WHERE id = ?",
                    (run_id,),
                )
                con.commit()

    def reconcile(self) -> None:
        # Check all runs that are supposed to be active
        with self._connect() as con:
            active_runs = con.execute(
                "SELECT id, pid, output_dir, status FROM crawl_runs WHERE status IN ('running', 'stopping')"
            ).fetchall()
            
        for run in active_runs:
            run_id = run["id"]
            pid = run["pid"]
            output_dir = self._resolve_output_dir(run["output_dir"])
            staging_db = output_dir / "geds.sqlite"
            
            # Check if OS process is running
            running = self._is_pid_running(pid)
            
            if not running:
                # Subprocess finished. Read staging DB to find final status
                final_status = "failed"
                req_count = 0
                heartbeat_at = None
                if staging_db.exists():
                    try:
                        # Query staging DB directly
                        with sqlite3.connect(staging_db) as stage_conn:
                            stage_conn.row_factory = sqlite3.Row
                            row = stage_conn.execute(
                                "SELECT status, request_count, heartbeat_at FROM crawl_runs WHERE id = ?",
                                (run_id,),
                            ).fetchone()
                            if row:
                                final_status = row["status"]
                                req_count = row["request_count"]
                                heartbeat_at = row["heartbeat_at"]
                    except Exception:
                        pass

                # On Windows, the recorded launcher PID can disagree with the
                # long-lived worker process. A fresh worker heartbeat is
                # authoritative evidence that the run is still alive.
                if final_status == "running" and heartbeat_at:
                    try:
                        heartbeat = datetime.fromisoformat(
                            heartbeat_at.replace("Z", "+00:00")
                        )
                        if (datetime.now(UTC) - heartbeat).total_seconds() <= 30:
                            with self._connect() as con:
                                con.execute(
                                    """
                                    UPDATE crawl_runs
                                    SET status = 'running', request_count = ?, finished_at = NULL
                                    WHERE id = ?
                                    """,
                                    (req_count, run_id),
                                )
                                con.commit()
                            continue
                    except (TypeError, ValueError):
                        pass
                
                # Check status mappings
                # DB states like 'finished' map to completed/finished, 'stopped' maps to stopped.
                # If it crashed, it's failed.
                db_status = "failed"
                if final_status == "finished":
                    db_status = "finished"
                elif final_status == "stopped":
                    db_status = "stopped"
                    
                now_iso = datetime.now(UTC).isoformat()
                # Also read finished_at from staging DB if available
                staging_finished = None
                if staging_db.exists():
                    try:
                        with sqlite3.connect(staging_db) as stage_conn2:
                            stage_conn2.row_factory = sqlite3.Row
                            frow = stage_conn2.execute(
                                "SELECT finished_at FROM crawl_runs WHERE id = ?", (run_id,)
                            ).fetchone()
                            if frow and frow["finished_at"]:
                                staging_finished = frow["finished_at"]
                    except Exception:
                        pass
                finished_ts = staging_finished or now_iso
                with self._connect() as con:
                    con.execute(
                        "UPDATE crawl_runs SET status = ?, request_count = ?, finished_at = ? WHERE id = ?",
                        (db_status, req_count, finished_ts, run_id),
                    )
                    con.commit()
            else:
                # Subprocess is running. Check heartbeat from staging DB
                if staging_db.exists():
                    try:
                        with sqlite3.connect(staging_db) as stage_conn:
                            stage_conn.row_factory = sqlite3.Row
                            row = stage_conn.execute(
                                "SELECT heartbeat_at, request_count FROM crawl_runs WHERE id = ?",
                                (run_id,),
                            ).fetchone()
                            if row and row["heartbeat_at"]:
                                hb_str = row["heartbeat_at"]
                                # Parse ISO timestamp
                                # SQLite text timestamps might be with or without Z, or +00:00.
                                # Let's handle it robustly.
                                try:
                                    hb_time = datetime.fromisoformat(hb_str.replace("Z", "+00:00"))
                                    now_time = datetime.now(UTC)
                                    delta = (now_time - hb_time).total_seconds()
                                    if delta > 30:
                                        # Stale heartbeat! Kill worker
                                        self.stop_run(run_id, force=True)
                                        with self._connect() as con:
                                            con.execute(
                                                "UPDATE crawl_runs SET status = 'failed' WHERE id = ?",
                                                (run_id,),
                                            )
                                            con.commit()
                                except Exception:
                                    pass
                    except Exception:
                        pass

    @staticmethod
    def _is_pid_running(pid: int | None) -> bool:
        if pid is None:
            return False
        if os.name == "nt":
            import ctypes

            process_query_limited_information = 0x1000
            still_active = 259
            handle = ctypes.windll.kernel32.OpenProcess(
                process_query_limited_information, False, pid
            )
            if not handle:
                return False
            try:
                exit_code = ctypes.c_ulong()
                if not ctypes.windll.kernel32.GetExitCodeProcess(
                    handle, ctypes.byref(exit_code)
                ):
                    return False
                return exit_code.value == still_active
            finally:
                ctypes.windll.kernel32.CloseHandle(handle)
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False
