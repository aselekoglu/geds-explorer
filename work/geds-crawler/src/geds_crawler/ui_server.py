from __future__ import annotations

import json
import sqlite3
import time
import uuid
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .ui_queries import SnapshotReader


def create_server(
    db_path: Path | str,
    host: str = "0.0.0.0",
    port: int = 8765,
) -> ThreadingHTTPServer:
    db_path = Path(db_path).resolve()
    if not db_path.is_file():
        raise FileNotFoundError(f"Database not found: {db_path}")
    
    # Detect if control plane or legacy snapshot
    is_control_plane = False
    try:
        # Use URI connection with mode=ro or check existence first to avoid side effects
        with sqlite3.connect(db_path) as conn:
            res = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='crawl_jobs'").fetchone()
            if res is not None:
                is_control_plane = True
    except Exception:
        pass

    # Start background control plane loop if active
    if is_control_plane:
        def run_control_loop():
            from .process_manager import ProcessManager
            from .traffic import distribute_shared_rate
            pm = ProcessManager(db_path)
            while True:
                try:
                    pm.reconcile()
                    pm.start_queued_runs()
                    distribute_shared_rate(db_path)
                except Exception:
                    pass
                time.sleep(3)
                
        import threading
        t = threading.Thread(target=run_control_loop, daemon=True)
        t.start()

    reader = SnapshotReader(db_path)

    class SnapshotHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/":
                html = DASHBOARD_HTML.replace(
                    "const IS_CONTROL_PLANE = false;",
                    f"const IS_CONTROL_PLANE = {'true' if is_control_plane else 'false'};"
                )
                self._send(HTTPStatus.OK, html.encode("utf-8"), "text/html; charset=utf-8")
                return
            if parsed.path == "/favicon.ico":
                self._send(HTTPStatus.NO_CONTENT, b"", "image/x-icon")
                return
                
            try:
                payload = self._api_payload(parsed.path, parse_qs(parsed.query))
            except ValueError as exc:
                self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
                return
            except sqlite3.OperationalError as exc:
                self._json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": f"Snapshot temporarily unavailable: {exc}"})
                return
                
            if payload is None:
                self._json(HTTPStatus.NOT_FOUND, {"error": "Not found"})
                return
            self._json(HTTPStatus.OK, payload)

        def do_POST(self) -> None:
            if not is_control_plane:
                self._json(HTTPStatus.NOT_IMPLEMENTED, {"error": "Control plane not enabled"})
                return
                
            parsed = urlparse(self.path)
            path_parts = parsed.path.strip("/").split("/")
            
            try:
                if parsed.path == "/api/control/jobs":
                    data = self._read_json()
                    name = data.get("name")
                    dept_dns = set(data.get("department_dns", []))
                    rate_limit = float(data.get("rate_limit_seconds", 1.0))
                    policy = data.get("traffic_policy", "queue")
                    out_dir = data.get("output_dir", "")
                    crawl_kind = data.get("crawl_kind", "full")
                    source_db_path = data.get("source_db_path")
                    
                    if not name or not out_dir:
                        self._json(HTTPStatus.BAD_REQUEST, {"error": "Missing parameters"})
                        return
                    if crawl_kind == "full" and not dept_dns:
                        self._json(HTTPStatus.BAD_REQUEST, {"error": "Missing department_dns for full crawl"})
                        return
                    if crawl_kind == "pagination_backfill" and not source_db_path:
                        self._json(HTTPStatus.BAD_REQUEST, {"error": "Missing source_db_path for pagination_backfill"})
                        return
                        
                    from .control_store import ControlStore
                    with ControlStore(db_path) as store:
                        job_id = store.create_job(
                            name, dept_dns, rate_limit, policy, out_dir,
                            crawl_kind=crawl_kind, source_db_path=source_db_path
                        )
                        
                        estimated_targets = 0
                        if crawl_kind == "pagination_backfill":
                            import sqlite3
                            try:
                                abs_source = Path(source_db_path).resolve()
                                source_conn = sqlite3.connect(f"file:{abs_source}?mode=ro", uri=True)
                                cursor = source_conn.execute(
                                    """
                                    SELECT COUNT(DISTINCT o.dn)
                                    FROM org_units o
                                    LEFT JOIN people_index p ON p.org_dn = o.dn
                                    GROUP BY o.dn
                                    HAVING COUNT(p.source_url) = 25
                                    """
                                )
                                estimated_targets = len(cursor.fetchall())
                                source_conn.close()
                            except Exception:
                                pass
                        else:
                            estimated_targets = len(dept_dns)
                            
                    self._json(
                        HTTPStatus.OK,
                        {
                            "job_id": job_id,
                            "crawl_kind": crawl_kind,
                            "estimated_targets": estimated_targets,
                        }
                    )
                    return
                    
                elif parsed.path == "/api/control/runs":
                    data = self._read_json()
                    job_id = data.get("job_id")
                    if not job_id:
                        self._json(HTTPStatus.BAD_REQUEST, {"error": "Missing job_id"})
                        return
                    from .control_store import ControlStore
                    with ControlStore(db_path) as store:
                        run_id = store.create_run(job_id, status="queued")
                        
                    from .process_manager import ProcessManager
                    pm = ProcessManager(db_path)
                    status = pm.try_start_run(run_id)
                    self._json(HTTPStatus.OK, {"run_id": run_id, "status": status})
                    return
                    
                elif len(path_parts) == 5 and path_parts[0] == "api" and path_parts[1] == "control" and path_parts[2] == "runs" and path_parts[4] == "stop":
                    run_id = path_parts[3]
                    from .process_manager import ProcessManager
                    pm = ProcessManager(db_path)
                    pm.stop_run(run_id, force=False)
                    self._json(HTTPStatus.OK, {"status": "stopping"})
                    return
                    
                elif len(path_parts) == 5 and path_parts[0] == "api" and path_parts[1] == "control" and path_parts[2] == "runs" and path_parts[4] == "resume":
                    run_id = path_parts[3]
                    from .process_manager import ProcessManager
                    pm = ProcessManager(db_path)
                    pm.start_run(run_id)
                    self._json(HTTPStatus.OK, {"status": "running"})
                    return
                    
                elif parsed.path == "/api/control/schedules":
                    data = self._read_json()
                    job_id = data.get("job_id")
                    expr = data.get("expression")
                    timezone = data.get("timezone", "America/Toronto")
                    policy = data.get("overlap_policy", "skip")
                    
                    if not job_id or not expr:
                        self._json(HTTPStatus.BAD_REQUEST, {"error": "Missing parameters"})
                        return
                        
                    from .scheduler import validate_cron
                    validate_cron(expr)
                    
                    sched_id = str(uuid.uuid4())
                    from .control_store import ControlStore
                    with ControlStore(db_path) as store:
                        store.db.execute(
                            """
                            INSERT INTO schedules (id, job_id, expression, timezone, overlap_policy, enabled)
                            VALUES (?, ?, ?, ?, ?, 1)
                            """,
                            (sched_id, job_id, expr, timezone, policy)
                        )
                        store.commit()
                    self._json(HTTPStatus.OK, {"schedule_id": sched_id})
                    return
                    
            except Exception as exc:
                self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})
                return
                
            self._json(HTTPStatus.NOT_FOUND, {"error": "Not found"})

        def do_DELETE(self) -> None:
            if not is_control_plane:
                self._json(HTTPStatus.NOT_IMPLEMENTED, {"error": "Control plane not enabled"})
                return
                
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)
            
            try:
                if parsed.path == "/api/control/schedules":
                    sched_id = query.get("id", [""])[0]
                    if not sched_id:
                        self._json(HTTPStatus.BAD_REQUEST, {"error": "Missing schedule id"})
                        return
                    from .control_store import ControlStore
                    with ControlStore(db_path) as store:
                        store.db.execute("DELETE FROM schedules WHERE id=?", (sched_id,))
                        store.commit()
                    self._json(HTTPStatus.OK, {"status": "deleted"})
                    return
            except Exception as exc:
                self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})
                return
                
            self._json(HTTPStatus.NOT_FOUND, {"error": "Not found"})

        def _read_json(self) -> dict:
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length == 0:
                return {}
            body = self.rfile.read(content_length)
            return json.loads(body.decode("utf-8"))

        def _api_payload(self, path: str, query: dict[str, list[str]]):
            path_parts = path.strip("/").split("/")
            
            # Control plane GET endpoints
            if is_control_plane:
                # GET /api/control/runs/<run_id>/pagination-orgs
                if len(path_parts) == 5 and path_parts[0] == "api" and path_parts[1] == "control" and path_parts[2] == "runs" and path_parts[4] == "pagination-orgs":
                    run_id = path_parts[3]
                    status_filter = query.get("status", [""])[0]
                    limit = int(query.get("limit", [50])[0])
                    offset = int(query.get("offset", [0])[0])
                    
                    from .control_queries import ControlQueries
                    queries = ControlQueries(db_path)
                    try:
                        res = queries.list_run_pagination_orgs(
                            run_id=run_id,
                            status=status_filter,
                            limit=limit,
                            offset=offset,
                        )
                        return res
                    except ValueError as e:
                        if "Run not found" in str(e):
                            return None
                        raise e

                if path == "/api/control/overview":
                    with sqlite3.connect(db_path) as conn:
                        conn.row_factory = sqlite3.Row
                        active_workers = int(conn.execute(
                            "SELECT COUNT(*) FROM crawl_runs WHERE status IN ('running', 'stopping')"
                        ).fetchone()[0])
                        
                        from .traffic import calculate_configured_rps
                        configured_rps = calculate_configured_rps(db_path)
                        
                        schedules = conn.execute(
                            """
                            SELECT s.*, j.name AS job_name
                            FROM schedules s
                            JOIN crawl_jobs j ON j.id = s.job_id
                            WHERE s.enabled = 1
                            ORDER BY s.next_run_at ASC
                            """
                        ).fetchall()
                        schedules_list = [dict(row) for row in schedules]
                        
                        total_depts = int(conn.execute("SELECT COUNT(*) FROM department_catalog").fetchone()[0])
                        
                    return {
                        "active_workers": active_workers,
                        "configured_rps": configured_rps,
                        "measured_rps": 0.0,
                        "next_schedules": schedules_list,
                        "total_departments": total_depts,
                    }
                    
                elif path == "/api/control/jobs":
                    with sqlite3.connect(db_path) as conn:
                        conn.row_factory = sqlite3.Row
                        rows = conn.execute("SELECT * FROM crawl_jobs").fetchall()
                        return [dict(row) for row in rows]
                        
                elif path == "/api/control/catalog":
                    with sqlite3.connect(db_path) as conn:
                        conn.row_factory = sqlite3.Row
                        rows = conn.execute("SELECT dn, name, source_url FROM department_catalog ORDER BY name").fetchall()
                        return [dict(row) for row in rows]
                        
                elif path == "/api/control/coverage":
                    from .control_store import ControlStore
                    with ControlStore(db_path) as store:
                        return store.coverage()

                elif path == "/api/control/estimates":
                    # Scan all staging DBs for per-department stats
                    estimates = {}  # { dept_dn: { org_units, people, db_size_bytes } }
                    scan_dbs = []
                    # Collect staging DB paths from completed runs
                    try:
                        with sqlite3.connect(db_path) as conn:
                            rows = conn.execute("SELECT output_dir FROM crawl_runs WHERE status='finished'").fetchall()
                            for r in rows:
                                out_dir = Path(r[0])
                                for name in ("geds.sqlite", "staging.sqlite"):
                                    p = out_dir / name
                                    if p.is_file():
                                        scan_dbs.append(p)
                                        break
                    except Exception:
                        pass
                    # Also scan unmanaged crawl
                    fb = (db_path.parent.parent / "runs" / "2026-07-08" / "unmanaged-crawl" / "geds.sqlite").resolve()
                    if not fb.is_file():
                        fb = (db_path.parent.parent / "geds-snapshot-2026-07-08" / "geds.sqlite").resolve()
                    if fb.is_file():
                        scan_dbs.append(fb)

                    for sdb in scan_dbs:
                        try:
                            with sqlite3.connect(sdb) as sconn:
                                sconn.row_factory = sqlite3.Row
                                # Per-department org unit count
                                org_rows = sconn.execute(
                                    "SELECT department_dn, COUNT(*) as cnt FROM org_units GROUP BY department_dn"
                                ).fetchall()
                                for r in org_rows:
                                    dn = r["department_dn"]
                                    if dn not in estimates or r["cnt"] > estimates[dn].get("org_units", 0):
                                        if dn not in estimates:
                                            estimates[dn] = {"org_units": 0, "people": 0, "db_size_bytes": 0}
                                        estimates[dn]["org_units"] = r["cnt"]
                                # Per-department people count
                                ppl_rows = sconn.execute(
                                    "SELECT department_dn, COUNT(*) as cnt FROM people_index GROUP BY department_dn"
                                ).fetchall()
                                for r in ppl_rows:
                                    dn = r["department_dn"]
                                    if dn not in estimates:
                                        estimates[dn] = {"org_units": 0, "people": 0, "db_size_bytes": 0}
                                    if r["cnt"] > estimates[dn].get("people", 0):
                                        estimates[dn]["people"] = r["cnt"]
                        except Exception:
                            pass

                    # Calculate rough per-department DB size estimates based on people count
                    # Using ratio from unmanaged crawl: ~59MB for 43545 people ≈ 1.4KB/person
                    for dn in estimates:
                        estimates[dn]["db_size_bytes"] = int(estimates[dn]["people"] * 1400)

                    return estimates
                        
                elif path == "/api/control/schedules":
                    with sqlite3.connect(db_path) as conn:
                        conn.row_factory = sqlite3.Row
                        rows = conn.execute(
                            """
                            SELECT s.*, j.name AS job_name
                            FROM schedules s
                            JOIN crawl_jobs j ON j.id = s.job_id
                            """
                        ).fetchall()
                        return [dict(row) for row in rows]
                        
                elif path == "/api/control/runs":
                    from .control_store import ControlStore
                    from .control_queries import ControlQueries
                    queries = ControlQueries(db_path)
                    with ControlStore(db_path) as store:
                        runs = store.list_runs()
                        
                    enriched_runs = []
                    for run in runs:
                        rate_limit = 1.0
                        with sqlite3.connect(db_path) as conn:
                            conn.row_factory = sqlite3.Row
                            job_row = conn.execute("SELECT rate_limit_seconds FROM crawl_jobs WHERE id = ?", (run.get("job_id"),)).fetchone()
                            if job_row:
                                rate_limit = job_row["rate_limit_seconds"]
                        enriched_runs.append(queries.enrich_run(run, rate_limit))
                    
                    fb = (db_path.parent.parent / "runs" / "2026-07-08" / "unmanaged-crawl" / "geds.sqlite").resolve()
                    if not fb.is_file():
                        fb = (db_path.parent.parent / "geds-snapshot-2026-07-08" / "geds.sqlite").resolve()
                        
                    if fb.is_file():
                        try:
                            with sqlite3.connect(fb) as conn:
                                conn.row_factory = sqlite3.Row
                                cursor = conn.execute("PRAGMA table_info(crawl_runs)")
                                cols = [c[1] for c in cursor.fetchall()]
                                
                                select_cols = ["id", "started_at", "status", "request_count"]
                                if "heartbeat_at" in cols:
                                    select_cols.append("heartbeat_at")
                                if "current_org_dn" in cols:
                                    select_cols.append("current_org_dn")
                                if "current_department_dn" in cols:
                                    select_cols.append("current_department_dn")
                                    
                                sql = f"SELECT {', '.join(select_cols)} FROM crawl_runs ORDER BY started_at DESC LIMIT 1"
                                row = conn.execute(sql).fetchone()
                                if row:
                                    run_id = row["id"]
                                    if not any(r["id"] == run_id for r in enriched_runs):
                                        enriched_runs.append({
                                            "id": run_id,
                                            "job_id": None,
                                            "job_name": "Unmanaged Crawl",
                                            "started_at": row["started_at"],
                                            "status": row["status"],
                                            "request_count": row["request_count"],
                                            "pid": None,
                                            "heartbeat_at": row["heartbeat_at"] if "heartbeat_at" in row.keys() else None,
                                            "current_org_dn": row["current_org_dn"] if "current_org_dn" in row.keys() else None,
                                            "current_department_dn": row["current_department_dn"] if "current_department_dn" in row.keys() else None,
                                        })
                        except Exception:
                            pass
                    return enriched_runs

            # Resolve the selected staging database based on the query parameter 'run_id'
            selected_run_id = query.get("run_id", [""])[0]
            
            snap_dbs = []
            self.overlay_db_paths = []
            
            if is_control_plane:
                if selected_run_id == "unmanaged":
                    fb = (db_path.parent.parent / "runs" / "2026-07-08" / "unmanaged-crawl" / "geds.sqlite").resolve()
                    if not fb.is_file():
                        fb = (db_path.parent.parent / "geds-snapshot-2026-07-08" / "geds.sqlite").resolve()
                    if fb.is_file():
                        snap_dbs = [fb]
                elif selected_run_id and selected_run_id != "all":
                    try:
                        with sqlite3.connect(db_path) as conn:
                            conn.row_factory = sqlite3.Row
                            row = conn.execute(
                                "SELECT output_dir, crawl_kind, source_db_path FROM crawl_runs WHERE id = ?",
                                (selected_run_id,)
                            ).fetchone()
                            if row:
                                if row["crawl_kind"] == "pagination_backfill":
                                    primary_db = Path(row["source_db_path"]).resolve()
                                    out_dir = Path(row["output_dir"])
                                    for name in ("geds.sqlite", "staging.sqlite"):
                                        p = out_dir / name
                                        if p.is_file():
                                            self.overlay_db_paths = [p]
                                            break
                                    snap_dbs = [primary_db]
                                else:
                                    out_dir = Path(row["output_dir"])
                                    for name in ("geds.sqlite", "staging.sqlite"):
                                        p = out_dir / name
                                        if p.is_file():
                                            snap_dbs = [p]
                                            break
                    except Exception:
                        pass
                else:
                    # "all" or empty: base is unmanaged snapshot DB, overlays are all finished/stopped backfill runs
                    fb = (db_path.parent.parent / "runs" / "2026-07-08" / "unmanaged-crawl" / "geds.sqlite").resolve()
                    if not fb.is_file():
                        fb = (db_path.parent.parent / "geds-snapshot-2026-07-08" / "geds.sqlite").resolve()
                    
                    if fb.is_file():
                        snap_dbs = [fb]
                    else:
                        snap_dbs = [db_path]

                    try:
                        with sqlite3.connect(db_path) as conn:
                            conn.row_factory = sqlite3.Row
                            rows = conn.execute(
                                """
                                SELECT output_dir FROM crawl_runs
                                WHERE crawl_kind = 'pagination_backfill' AND status IN ('finished', 'stopped')
                                """
                            ).fetchall()
                            for r in rows:
                                out_dir = Path(r["output_dir"])
                                for name in ("geds.sqlite", "staging.sqlite"):
                                    p = out_dir / name
                                    if p.is_file():
                                        self.overlay_db_paths.append(p)
                                        break
                    except Exception:
                        pass
            else:
                snap_dbs = [db_path]

            if not snap_dbs:
                if path == "/api/status":
                    return {
                        "run_status": "idle",
                        "request_count": 0,
                        "departments": 0,
                        "org_units": 0,
                        "people": 0,
                        "errors": 0,
                        "queue": {"done": 0, "pending": 0, "error": 0},
                        "completion_percent": 0.0,
                    }
                elif path == "/api/departments":
                    return []
                else:
                    return {"total": 0, "limit": 50, "offset": 0, "items": []}

            # Aggregate stats for overview status
            if path == "/api/status":
                aggregated = {
                    "run_status": "idle",
                    "request_count": 0,
                    "departments": 0,
                    "org_units": 0,
                    "people": 0,
                    "errors": 0,
                    "queue": {"done": 0, "pending": 0, "error": 0},
                    "completion_percent": 0.0,
                    "crawl_kind": "full",
                    "eta": None,
                    "measured_rps": None,
                }
                has_active = False
                total_done = 0
                total_pending = 0
                total_failed = 0
                
                for db in snap_dbs:
                    try:
                        rdr = SnapshotReader(db, self.overlay_db_paths)
                        s = rdr.status()
                        aggregated["request_count"] += s["request_count"]
                        aggregated["departments"] += s["departments"]
                        aggregated["org_units"] += s["org_units"]
                        aggregated["people"] += s["people"]
                        aggregated["errors"] += s["errors"]
                        
                        done = s["queue"].get("done", 0)
                        pending = s["queue"].get("pending", 0)
                        failed = s["queue"].get("error", 0)
                        total_done += done
                        total_pending += pending
                        total_failed += failed
                        
                        if s["run_status"] in ("running", "stopping"):
                            has_active = True
                    except Exception:
                        pass
                        
                aggregated["run_status"] = "running" if has_active else "idle"
                aggregated["queue"]["done"] = total_done
                aggregated["queue"]["pending"] = total_pending
                aggregated["queue"]["error"] = total_failed
                
                total_queue = total_done + total_pending + total_failed
                if total_queue > 0:
                    aggregated["completion_percent"] = round((total_done + total_failed) * 100 / total_queue, 1)

                if is_control_plane and selected_run_id and selected_run_id not in ("all", "unmanaged"):
                    try:
                        from .control_queries import ControlQueries
                        queries = ControlQueries(db_path)
                        with sqlite3.connect(db_path) as conn:
                            conn.row_factory = sqlite3.Row
                            run_row = conn.execute(
                                "SELECT id, job_id, output_dir, crawl_kind, source_db_path, started_at, status FROM crawl_runs WHERE id = ?",
                                (selected_run_id,)
                            ).fetchone()
                            if run_row:
                                rate_limit = 1.0
                                job_row = conn.execute("SELECT rate_limit_seconds FROM crawl_jobs WHERE id = ?", (run_row["job_id"],)).fetchone()
                                if job_row:
                                    rate_limit = job_row["rate_limit_seconds"]

                                enriched = queries.enrich_run(dict(run_row), rate_limit)
                                aggregated["crawl_kind"] = enriched.get("crawl_kind", "full")
                                aggregated["eta"] = enriched.get("eta")
                                aggregated["measured_rps"] = enriched.get("measured_rps")

                                if enriched.get("crawl_kind") == "pagination_backfill":
                                    prog = enriched.get("progress", {})
                                    aggregated["completion_percent"] = prog.get("percent", 0.0)
                                    aggregated["queue"]["done"] = prog.get("completed_orgs", 0)
                                    aggregated["queue"]["pending"] = prog.get("total_orgs", 0) - prog.get("terminal_orgs", 0)
                                    aggregated["queue"]["error"] = prog.get("failed_orgs", 0)

                                    pag_m = enriched.get("pagination_metrics", {})
                                    aggregated["request_count"] = pag_m.get("pages_fetched", 0)
                                    aggregated["people"] = pag_m.get("new_people", 0)
                                    # Use total failures/errors in backfill as errors count
                                    aggregated["errors"] = prog.get("failed_orgs", 0)
                    except Exception:
                        pass
                
                return aggregated

            # For tables, query the primary/first DB in the list
            try:
                primary_db = snap_dbs[0]
                req_reader = SnapshotReader(primary_db, getattr(self, "overlay_db_paths", []))
                if path == "/api/departments":
                    return req_reader.departments()

                common = {
                    "query": _text(query, "q"),
                    "limit": _integer(query, "limit", 50),
                    "offset": _integer(query, "offset", 0),
                }
                if path == "/api/orgs":
                    return req_reader.orgs(department=_text(query, "department"), **common)
                if path == "/api/people":
                    return req_reader.people(department=_text(query, "department"), **common)
                if path == "/api/queue":
                    return req_reader.queue(
                        department=_text(query, "department"),
                        status=_text(query, "status"),
                        **common,
                    )
                if path == "/api/errors":
                    return req_reader.errors(**common)
            except (FileNotFoundError, sqlite3.OperationalError):
                if path == "/api/departments":
                    return []
                else:
                    return {"total": 0, "limit": 50, "offset": 0, "items": []}
            return None

        def _json(self, status: HTTPStatus, payload) -> None:
            # Inject unauthenticated control vulnerability warning for mutations (POST/PUT/DELETE)
            if self.command in ("POST", "PUT", "DELETE") and isinstance(payload, dict):
                payload["warning"] = "Development only: unauthenticated crawl control. Do not expose this service to an untrusted LAN or the public internet."
                
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Warning", "Development only: unauthenticated crawl control. Do not expose this service to an untrusted LAN or the public internet.")
            self.end_headers()
            self.wfile.write(body)

        def _send(self, status: HTTPStatus, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args) -> None:
            return

    return ThreadingHTTPServer((host, port), SnapshotHandler)


def _text(query: dict[str, list[str]], name: str) -> str:
    return query.get(name, [""])[0].strip()


def _integer(query: dict[str, list[str]], name: str, default: int) -> int:
    value = _text(query, name)
    if not value:
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
DASHBOARD_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>GEDS Crawl Control Plane</title>
  <style>
    :root {
      color-scheme: light;
      --ink: #18212b;
      --muted: #647180;
      --line: #d9dfe5;
      --soft: #f4f6f8;
      --panel: #ffffff;
      --nav: #172a3a;
      --accent: #087f5b;
      --accent-soft: #dff4ed;
      --danger: #b42318;
      --danger-soft: #fde8e8;
      --warning: #b54708;
      --warning-soft: #fff3cd;
      font-family: Inter, "Segoe UI", Arial, sans-serif;
    }
    * { box-sizing: border-box; }
    body { margin: 0; color: var(--ink); background: var(--soft); font-size: 14px; }
    button, input, select { font: inherit; }
    .warning-banner {
      background: var(--warning-soft); color: var(--warning);
      padding: 10px 24px; text-align: center; font-weight: bold;
      border-bottom: 1px solid var(--line);
    }
    header {
      min-height: 58px; padding: 0 24px; background: var(--nav); color: white;
      display: flex; align-items: center; justify-content: space-between; gap: 16px;
    }
    .brand { display: flex; align-items: baseline; gap: 12px; min-width: 0; }
    h1 { font-size: 18px; margin: 0; letter-spacing: 0; white-space: nowrap; }
    .run-state { color: #c8d7e2; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .refresh-meta { display: flex; align-items: center; gap: 10px; white-space: nowrap; }
    .header-button {
      color: white; background: transparent; border: 1px solid #6f8392; border-radius: 4px;
      padding: 7px 11px; cursor: pointer;
    }
    main { width: min(1600px, 100%); margin: 0 auto; padding: 18px 24px 28px; }
    
    /* Sekme Yapısı */
    .nav-tabs {
      display: flex; gap: 8px; border-bottom: 1px solid var(--line);
      margin-bottom: 18px; overflow-x: auto;
    }
    .nav-tab {
      border: 0; border-bottom: 3px solid transparent;
      padding: 12px 18px; background: transparent; color: var(--muted);
      cursor: pointer; font-weight: 500;
    }
    .nav-tab.active {
      color: var(--ink); border-bottom-color: var(--accent); font-weight: bold;
    }

    :root {
      --bg: #08111f;
      --bg-deep: #050a13;
      --surface: #111c2d;
      --surface-2: #172437;
      --surface-3: #203149;
      --line: rgba(148, 163, 184, 0.22);
      --text: #e5edf8;
      --muted: #94a3b8;
      --accent: #34d399;
      --accent-strong: #10b981;
      --warning: #f59e0b;
      --warning-soft: rgba(245, 158, 11, 0.14);
      --danger: #f87171;
      --danger-soft: rgba(248, 113, 113, 0.14);
      --info: #60a5fa;
      --info-soft: rgba(96, 165, 250, 0.14);
      --shadow: 0 22px 70px rgba(0, 0, 0, 0.32);
      --radius-lg: 18px;
      --radius-md: 12px;
      --radius-sm: 8px;
    }

    body {
      min-height: 100vh;
      background: radial-gradient(circle at top left, rgba(16, 185, 129, 0.12), transparent 32rem), var(--bg-deep);
      color: var(--text);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    :focus-visible {
      outline: 3px solid rgba(52, 211, 153, 0.92);
      outline-offset: 3px;
      border-radius: 8px;
    }
    .security-strip {
      display: flex;
      gap: 10px;
      align-items: center;
      padding: 10px 18px;
      background: rgba(245, 158, 11, 0.12);
      border-bottom: 1px solid rgba(245, 158, 11, 0.22);
      color: #fde68a;
      font-size: 13px;
    }
    .status-dot {
      width: 10px;
      height: 10px;
      border-radius: 999px;
      flex: 0 0 auto;
    }
    .status-warning { background: var(--warning); box-shadow: 0 0 0 4px var(--warning-soft); }
    .app-shell {
      display: grid;
      grid-template-columns: 260px minmax(0, 1fr);
      min-height: calc(100vh - 42px);
    }
    .sidebar {
      border-right: 1px solid var(--line);
      background: rgba(8, 17, 31, 0.92);
      padding: 22px 16px;
      position: sticky;
      top: 0;
      height: calc(100vh - 42px);
    }
    .brand-block { display: flex; align-items: center; gap: 12px; margin-bottom: 28px; }
    .brand-mark {
      width: 38px;
      height: 38px;
      display: grid;
      place-items: center;
      border-radius: 12px;
      background: linear-gradient(135deg, var(--accent), #22d3ee);
      color: #04111f;
      font-weight: 800;
    }
    .brand-title { font-weight: 800; letter-spacing: 0.08em; }
    .brand-subtitle { color: var(--muted); font-size: 12px; margin-top: 2px; }
    .rail-nav { display: grid; gap: 6px; }
    .rail-group-label {
      color: var(--muted);
      font-size: 11px;
      letter-spacing: 0.14em;
      text-transform: uppercase;
      margin: 18px 10px 6px;
    }
    .rail-item {
      width: 100%;
      border: 1px solid transparent;
      background: transparent;
      color: var(--muted);
      border-radius: 12px;
      padding: 10px 12px;
      text-align: left;
      display: flex;
      justify-content: space-between;
      align-items: center;
      cursor: pointer;
    }
    .rail-item:hover, .rail-item.active {
      color: var(--text);
      background: rgba(148, 163, 184, 0.10);
      border-color: var(--line);
    }
    .rail-count {
      min-width: 22px;
      height: 22px;
      border-radius: 999px;
      display: grid;
      place-items: center;
      background: var(--warning-soft);
      color: #fbbf24;
      font-size: 12px;
    }
    .main-stage { min-width: 0; padding: 24px; }
    .topbar {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 18px;
      margin-bottom: 22px;
    }
    .eyebrow {
      margin: 0 0 4px;
      color: var(--accent);
      text-transform: uppercase;
      letter-spacing: 0.16em;
      font-size: 11px;
      font-weight: 700;
    }
    h1 { margin: 0; font-size: clamp(28px, 4vw, 40px); }
    .page-description { margin: 6px 0 0; color: var(--muted); max-width: 680px; }
    .topbar-actions { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; justify-content: flex-end; }
    .connection-pill {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 8px 12px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: rgba(17, 28, 45, 0.82);
      color: var(--text);
      font-size: 13px;
    }
    .workspace-panel { display: none; }
    .workspace-panel.active { display: block; }
    .panel-card {
      background: rgba(17, 28, 45, 0.86);
      border: 1px solid var(--line);
      border-radius: var(--radius-lg);
      box-shadow: var(--shadow);
      padding: 18px;
    }
    .panel-title { margin: 0 0 6px; font-size: 16px; }
    .panel-subtitle { margin: 0 0 16px; color: var(--muted); font-size: 13px; }
    .status-label {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      border-radius: 999px;
      padding: 4px 9px;
      font-size: 12px;
      font-weight: 700;
      text-transform: capitalize;
    }
    .status-label.healthy, .status-label.running { color: #86efac; background: rgba(34, 197, 94, 0.13); }
    .status-label.attention, .status-label.stale { color: #fbbf24; background: var(--warning-soft); }
    .status-label.failed, .status-label.blocked { color: #fca5a5; background: var(--danger-soft); }
    .status-label.info, .status-label.scheduled { color: #93c5fd; background: var(--info-soft); }
    .icon-button { display: none; }
    .workspace-header-row {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 16px;
      margin-bottom: 16px;
    }
    .section-title { margin: 0; font-size: 22px; }
    .drawer-backdrop {
      position: fixed;
      inset: 0;
      background: rgba(0, 0, 0, 0.52);
      z-index: 50;
    }
    .drawer {
      position: fixed;
      top: 0;
      right: 0;
      width: min(760px, 100vw);
      height: 100vh;
      overflow: auto;
      background: var(--surface);
      border-left: 1px solid var(--line);
      box-shadow: var(--shadow);
      z-index: 60;
      padding: 22px;
    }
    .drawer-header, .drawer-footer {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 16px;
    }
    .drawer-body { display: grid; gap: 18px; margin-top: 18px; }
    .drawer-footer {
      position: sticky;
      bottom: 0;
      justify-content: flex-end;
      padding-top: 18px;
      background: linear-gradient(180deg, rgba(17, 28, 45, 0), var(--surface) 28%);
    }
    .flow-steps {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 8px;
      padding: 0;
      margin: 18px 0;
      list-style: none;
    }
    .flow-steps li {
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 8px 10px;
      color: var(--muted);
      font-size: 12px;
      text-align: center;
    }
    .drawer-note {
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 14px;
      background: rgba(8, 17, 31, 0.5);
      color: var(--muted);
    }
    .command-grid {
      display: grid;
      grid-template-columns: minmax(0, 1.2fr) minmax(320px, 0.8fr);
      gap: 16px;
      margin-bottom: 16px;
    }
    .attention-list, .activity-list { display: grid; gap: 10px; }
    .attention-item, .activity-item {
      border: 1px solid var(--line);
      background: rgba(8, 17, 31, 0.58);
      border-radius: 12px;
      padding: 12px;
      display: grid;
      gap: 6px;
    }
    .summary-row {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
      margin: 14px 0;
    }
    .summary-row span {
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 12px;
      color: var(--muted);
    }
    .summary-row strong { display: block; color: var(--text); font-size: 24px; margin-top: 6px; }
    .filter-chips {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      margin: 16px 0;
    }
    .chip {
      border: 1px solid var(--line);
      color: var(--muted);
      background: rgba(17, 28, 45, 0.82);
      border-radius: 999px;
      padding: 8px 12px;
      cursor: pointer;
    }
    .chip.active {
      color: var(--text);
      border-color: rgba(52, 211, 153, 0.55);
      background: rgba(52, 211, 153, 0.14);
    }

    @media (max-width: 760px) {
      .app-shell { grid-template-columns: 1fr; }
      .sidebar {
        position: fixed;
        inset: 42px auto 0 0;
        width: min(82vw, 320px);
        transform: translateX(-105%);
        transition: transform 180ms ease;
        z-index: 40;
      }
      body.nav-open .sidebar { transform: translateX(0); }
      .main-stage { padding: 16px; }
      .topbar { flex-direction: column; }
      .icon-button {
        display: inline-flex;
        border: 1px solid var(--line);
        background: var(--surface);
        color: var(--text);
        border-radius: 10px;
        padding: 8px 10px;
      }
      .topbar-actions { justify-content: flex-start; }
      table.responsive-table thead { display: none; }
      table.responsive-table, table.responsive-table tbody, table.responsive-table tr, table.responsive-table td {
        display: block;
        width: 100%;
      }
      table.responsive-table tr {
        border: 1px solid var(--line);
        border-radius: 12px;
        margin-bottom: 10px;
        padding: 10px;
        background: rgba(17, 28, 45, 0.7);
      }
      table.responsive-table td {
        border: 0;
        padding: 6px 0;
      }
      table.responsive-table td::before {
        content: attr(data-label);
        display: block;
        color: var(--muted);
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: 0.08em;
      }
    }

    /* Metrics Grid */
    .metrics {
      display: grid; grid-template-columns: repeat(4, 1fr);
      background: var(--panel); border: 1px solid var(--line); border-radius: 6px;
      margin-bottom: 18px;
    }
    .metric { padding: 13px 15px; border-right: 1px solid var(--line); min-width: 0; }
    .metric:last-child { border-right: 0; }
    .metric-label { display: block; color: var(--muted); font-size: 11px; text-transform: uppercase; }
    .metric-value { display: block; margin-top: 4px; font-size: 21px; font-weight: 650; }

    .workspace { background: var(--panel); border: 1px solid var(--line); border-radius: 6px; overflow: hidden; }
    .tabs { display: flex; border-bottom: 1px solid var(--line); background: #fafbfc; overflow-x: auto; }
    .tab {
      border: 0; border-right: 1px solid var(--line); border-bottom: 3px solid transparent;
      padding: 12px 18px 9px; background: transparent; color: var(--muted); cursor: pointer;
    }
    .tab.active { color: var(--ink); border-bottom-color: var(--accent); background: white; font-weight: 650; }
    
    .form-section {
      background: var(--panel); border: 1px solid var(--line); border-radius: 6px;
      padding: 18px; margin-bottom: 18px;
    }
    .form-grid {
      display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px;
      margin-bottom: 16px;
    }
    .form-group { display: flex; flex-direction: column; gap: 6px; }
    .form-group label { font-weight: 600; font-size: 12px; color: var(--muted); text-transform: uppercase; }
    
    .btn {
      height: 36px; border: 1px solid #bfc8d1; border-radius: 4px;
      background: white; color: var(--ink); padding: 0 16px; cursor: pointer;
      font-weight: 600; display: inline-flex; align-items: center; justify-content: center;
    }
    .btn-primary {
      background: var(--accent); color: white; border-color: var(--accent);
    }
    .btn-danger {
      background: var(--danger); color: white; border-color: var(--danger);
    }

    .filters {
      display: grid; grid-template-columns: minmax(220px, 2fr) minmax(180px, 1fr) 150px 110px;
      gap: 10px; padding: 12px; border-bottom: 1px solid var(--line);
    }
    input, select {
      width: 100%; height: 36px; border: 1px solid #bfc8d1; border-radius: 4px;
      background: white; color: var(--ink); padding: 0 10px;
    }
    .table-wrap { overflow: auto; min-height: 380px; }
    table { width: 100%; border-collapse: collapse; table-layout: fixed; }
    th {
      position: sticky; top: 0; z-index: 1; text-align: left; background: #eef2f5;
      color: #475563; font-size: 11px; text-transform: uppercase; padding: 9px 11px;
      border-bottom: 1px solid var(--line);
    }
    td {
      padding: 9px 11px; border-bottom: 1px solid #e7ebef; vertical-align: top;
      overflow-wrap: anywhere; line-height: 1.35;
    }
    tbody tr:hover { background: #f7faf9; }
    .muted { color: var(--muted); }
    
    .badge { display: inline-block; padding: 2px 7px; border-radius: 10px; font-size: 11px; font-weight: 650; }
    .badge.done, .badge.running, .badge.covered-current, .badge.completed, .badge.crawling { color: #176b4d; background: var(--accent-soft); }
    .badge.pending, .badge.queued, .badge.scheduled { color: var(--warning); background: #fff0db; }
    .badge.error, .badge.failed, .badge.overlap { color: var(--danger); background: var(--danger-soft); }
    
    .source { color: #176b4d; font-weight: 600; text-decoration: none; }
    .source:hover { text-decoration: underline; }
    .empty { padding: 60px 20px; text-align: center; color: var(--muted); }
    
    .footer {
      min-height: 50px; padding: 9px 12px; display: flex; align-items: center;
      justify-content: space-between; gap: 12px; border-top: 1px solid var(--line);
    }
    .pager { display: flex; align-items: center; gap: 8px; }
    .pager button {
      height: 32px; min-width: 36px; border: 1px solid #bfc8d1; border-radius: 4px;
      background: white; cursor: pointer;
    }
    .pager button:disabled { opacity: .45; cursor: default; }
  </style>
</head>
<body>
  <div class="security-strip" role="status" aria-live="polite">
    <span class="status-dot status-warning" aria-hidden="true"></span>
    <span><strong>Local control plane:</strong> unauthenticated LAN UI. Use only on trusted networks.</span>
  </div>

  <div class="app-shell">
    <aside class="sidebar" id="primary-sidebar">
      <div class="brand-block">
        <span class="brand-mark" aria-hidden="true">G</span>
        <div>
          <div class="brand-title">GEDS</div>
          <div class="brand-subtitle">Control Plane</div>
        </div>
      </div>

      <nav class="rail-nav" aria-label="Primary workspace navigation">
        <div class="rail-group-label">Operate</div>
        <button class="rail-item active" type="button" data-route="#/operate/overview">
          <span>Overview</span>
          <span class="rail-count" id="nav-attention-count">0</span>
        </button>
        <button class="rail-item" type="button" data-route="#/operate/crawlers">Crawlers</button>
        <button class="rail-item" type="button" data-route="#/operate/history">Run History</button>

        <div class="rail-group-label">Plan</div>
        <button class="rail-item" type="button" data-route="#/plan/coverage">Coverage</button>
        <button class="rail-item" type="button" data-route="#/plan/schedules">Schedules</button>

        <div class="rail-group-label">Explore Data</div>
        <button class="rail-item" type="button" data-route="#/explore/snapshot">Snapshot Data</button>
      </nav>
    </aside>

    <main class="main-stage">
      <header class="topbar">
        <button id="mobile-nav-toggle" class="icon-button" type="button" aria-controls="primary-sidebar" aria-expanded="false">Menu</button>
        <div>
          <p class="eyebrow">Prime Radiant</p>
          <h1 id="page-title">Operate</h1>
          <p id="page-description" class="page-description">Live crawler status, attention items, and next actions.</p>
        </div>
        <div class="topbar-actions">
          <span id="run-state" class="connection-pill" role="status" aria-live="polite">Connecting...</span>
          <span id="last-updated" class="muted"></span>
          <button id="refresh" class="btn" type="button">Refresh</button>
        </div>
      </header>

      <section class="workspace-panel active" id="workspace-operate-overview" data-workspace="#/operate/overview">

    <!-- Top progress and estimation section -->
    <div id="top-progress-section" style="display:none; margin-bottom: 18px; padding: 12px 16px; background: white; border: 1px solid #e1e8ed; border-radius: 6px;">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
        <span id="top-progress-text" style="font-weight: 600; font-size: 13px; color: var(--dark);">Crawl Progress</span>
        <span id="top-progress-label" style="font-weight: 600; font-size: 13px; color: var(--muted);">0% complete</span>
      </div>
      <div class="progress" style="margin: 0 0 10px 0;"><div id="top-progress-bar" style="width: 0%;"></div></div>

      <!-- Top Estimation Metadata (ETA & RPS) -->
      <div id="top-estimation-meta" style="display: flex; flex-wrap: wrap; gap: 16px; font-size: 12px; border-top: 1px solid #f0f4f8; padding-top: 8px;">
        <div style="flex: 1; min-width: 140px;">
          <span style="color: var(--muted); text-transform: uppercase; font-size: 10px; font-weight: bold;">Estimated Finish (ETA)</span>
          <span id="top-eta-val" style="display: block; font-weight: 600; margin-top: 2px;">Calculating ETA</span>
        </div>
        <div style="flex: 1; min-width: 100px;">
          <span style="color: var(--muted); text-transform: uppercase; font-size: 10px; font-weight: bold;">Measured Rate</span>
          <span id="top-rps-val" style="display: block; font-weight: 600; margin-top: 2px;">-</span>
        </div>
        <div style="flex: 1; min-width: 160px;">
          <span style="color: var(--muted); text-transform: uppercase; font-size: 10px; font-weight: bold;">Crawl Kind</span>
          <span id="top-kind-val" style="display: block; font-weight: 600; margin-top: 2px; text-transform: capitalize;">Full crawl</span>
        </div>
      </div>
    </div>

    <!-- OVERVIEW TAB -->
    <div class="tab-content" id="tab-overview">
      <section class="metrics">
        <div class="metric"><span class="metric-label">Active Workers</span><strong id="ctrl-m-workers" class="metric-value">0</strong></div>
        <div class="metric"><span class="metric-label">Configured RPS</span><strong id="ctrl-m-conf-rps" class="metric-value">0.0</strong></div>
        <div class="metric"><span class="metric-label">Measured RPS</span><strong id="ctrl-m-meas-rps" class="metric-value">0.0</strong></div>
        <div class="metric"><span class="metric-label">Total Cataloged</span><strong id="ctrl-m-depts" class="metric-value">0</strong></div>
      </section>
      
      <!-- Over-budget warnings -->
      <div id="rps-warning-amber" class="warning-banner" style="display:none; margin-bottom:18px; border-radius:6px;">
        WARNING: Aggregated traffic limit is above 1.0 RPS.
      </div>
      <div id="rps-warning-red" class="warning-banner" style="display:none; margin-bottom:18px; border-radius:6px; background:var(--danger-soft); color:var(--danger); border-color:var(--danger);">
        CRITICAL WARNING: Aggregated traffic limit is above 2.0 RPS!
      </div>
      <div class="command-grid">
        <section class="panel-card">
          <h2 class="panel-title">Attention Queue</h2>
          <p class="panel-subtitle">Problem-first list of stale, failed, missing, or overlapping work.</p>
          <div id="attention-list" class="attention-list">
            <div class="empty">No attention items loaded yet.</div>
          </div>
        </section>
        <section class="panel-card">
          <h2 class="panel-title">Live Activity</h2>
          <p class="panel-subtitle">Active crawler runs, throughput, and progress.</p>
          <div id="live-activity-list" class="activity-list">
            <div class="empty">No active crawler activity loaded yet.</div>
          </div>
        </section>
      </div>
    </div>
      </section>

      <section class="workspace-panel" id="workspace-operate-crawlers" data-workspace="#/operate/crawlers">
        <div class="workspace-header-row">
          <div>
            <h2 class="section-title">Crawlers</h2>
            <p class="panel-subtitle">Monitor active runs and start focused crawler work.</p>
          </div>
          <button id="open-start-crawler" class="btn btn-primary" type="button">Start crawler</button>
        </div>

    <!-- CRAWLERS TAB -->
    <div class="tab-content" id="tab-crawlers">
      <!-- Create Crawler Job -->
      <div class="form-section" id="crawler-create-section">
        <h3>Create New Crawler Job</h3>
        <form id="new-job-form">
          <div class="form-grid">
            <div class="form-group">
              <label for="job-name">Job Name</label>
              <input type="text" id="job-name" required placeholder="e.g. ISED + CRTC">
            </div>
            <div class="form-group">
              <label for="job-crawl-kind">Crawl Kind</label>
              <select id="job-crawl-kind">
                <option value="full">Full crawl</option>
                <option value="pagination_backfill">Pagination backfill</option>
              </select>
            </div>
            <div class="form-group">
              <label for="job-policy">Traffic Policy</label>
              <select id="job-policy">
                <option value="queue">Queue (Safe budget)</option>
                <option value="shared">Shared (Polite rate share)</option>
                <option value="independent">Independent (RPS limit)</option>
              </select>
            </div>
            <div class="form-group">
              <label for="job-rate">Rate Limit (sec per request)</label>
              <input type="number" id="job-rate" value="1.0" min="0.1" step="0.1" required>
            </div>
            <div class="form-group">
              <label for="job-output">Output Directory</label>
              <input type="text" id="job-output" required placeholder="outputs/runs/ised-run">
            </div>
            <div class="form-group" id="source-db-container" style="display:none;">
              <label for="job-source-db">Source Database Path</label>
              <input type="text" id="job-source-db" placeholder="e.g. outputs/geds.sqlite">
            </div>
          </div>
          <div class="form-group" id="dept-selection-container" style="margin-bottom:16px;">
            <label>Select Departments</label>
            <div style="display:flex; gap:8px; margin-bottom:8px; align-items:center; flex-wrap:wrap;">
              <input type="text" id="job-dept-search" placeholder="Search departments..." style="flex:1; min-width:180px; height:32px; font-size:12px;">
              <button type="button" class="btn" onclick="deptSelectUncrawled()" style="height:32px;padding:0 10px;font-size:11px;">Select Uncrawled</button>
              <button type="button" class="btn" onclick="deptSelectOutdated()" style="height:32px;padding:0 10px;font-size:11px;">Select Outdated (&gt;7d)</button>
              <button type="button" class="btn" onclick="deptSelectAll()" style="height:32px;padding:0 10px;font-size:11px;">Select All</button>
              <button type="button" class="btn" onclick="deptClearAll()" style="height:32px;padding:0 10px;font-size:11px;">Clear</button>
            </div>
            <div style="max-height:260px; overflow-y:auto; border:1px solid var(--line); border-radius:6px;" id="dept-selection-wrap">
              <table style="margin:0; font-size:12px;" id="dept-selection-table">
                <thead style="position:sticky;top:0;z-index:1;background:var(--bg);">
                  <tr>
                    <th style="width:32px;text-align:center;cursor:pointer;" id="dept-th-check"><input type="checkbox" id="dept-toggle-all" style="width:auto;height:auto;"></th>
                    <th style="cursor:pointer;" data-sort="name" id="dept-th-name">Department ▾</th>
                    <th style="cursor:pointer;width:140px;" data-sort="age" id="dept-th-age">Last Crawled ▾</th>
                    <th style="cursor:pointer;width:100px;" data-sort="status" id="dept-th-status">Status ▾</th>
                    <th style="width:80px;text-align:right;">Org Units</th>
                    <th style="width:80px;text-align:right;">People</th>
                  </tr>
                </thead>
                <tbody id="dept-selection-body"></tbody>
              </table>
            </div>
          </div>
          <div id="crawl-estimation-panel" style="background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px 16px;margin-bottom:16px;display:flex;gap:24px;flex-wrap:wrap;">
            <div><span style="color:var(--muted);font-size:11px;text-transform:uppercase;">Selected</span><br><strong id="est-selected">0 depts</strong></div>
            <div><span style="color:var(--muted);font-size:11px;text-transform:uppercase;">Est. Requests</span><br><strong id="est-requests">0</strong></div>
            <div><span style="color:var(--muted);font-size:11px;text-transform:uppercase;">Est. Duration</span><br><strong id="est-duration">0s</strong></div>
            <div><span style="color:var(--muted);font-size:11px;text-transform:uppercase;">Est. People</span><br><strong id="est-people">0</strong></div>
            <div><span style="color:var(--muted);font-size:11px;text-transform:uppercase;">Est. DB Size</span><br><strong id="est-size">0 MB</strong></div>
          </div>
          <button type="submit" class="btn btn-primary">Create and Start Job</button>
        </form>
      </div>

      <!-- Active / Past Runs -->
      <div class="workspace">
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Job Name</th>
                <th>Started</th>
                <th>Status</th>
                <th>Requests</th>
                <th>PID</th>
                <th>Last Heartbeat</th>
                <th>Current Org</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody id="runs-table-body"></tbody>
          </table>
        </div>
      </div>
      
      <!-- PAGINATION ORGS DETAILS PANEL -->
      <div id="pagination-orgs-panel" class="form-section" style="display:none; margin-top:24px;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:14px;">
          <h3>Pagination Backfill Details: <span id="pag-panel-run-name">-</span></h3>
          <button type="button" class="btn" onclick="hidePaginationOrgsPanel()">Close Panel</button>
        </div>
        <div class="filters" style="grid-template-columns: 1fr 180px 110px; border-bottom:0; padding:12px 0;">
          <div style="display:flex; align-items:center; gap:8px;">
            <span style="font-weight:bold; color:var(--muted);">Filter Status:</span>
            <select id="pag-filter-status" style="width:160px; height:32px;">
              <option value="">All Statuses</option>
              <option value="pending">Pending</option>
              <option value="crawling">Crawling</option>
              <option value="completed">Completed</option>
              <option value="failed">Failed</option>
            </select>
          </div>
          <div></div>
          <div></div>
        </div>
        <div class="table-wrap" style="min-height:240px; border: 1px solid var(--line); border-radius:6px;">
          <table id="pag-orgs-table">
            <thead>
              <tr>
                <th>Org Path</th>
                <th>Status</th>
                <th>Pages</th>
                <th>New People</th>
                <th>Deduped People</th>
                <th>Last Page URL</th>
                <th>Reason / Error</th>
              </tr>
            </thead>
            <tbody id="pag-orgs-table-body">
              <tr><td colspan="7" class="empty">No data loaded.</td></tr>
            </tbody>
          </table>
        </div>
        <div class="footer" style="border-top:0; padding-left:0; padding-right:0;">
          <span id="pag-result-count" class="muted">No rows loaded</span>
          <div class="pager">
            <button id="pag-previous" type="button">&lt;</button>
            <span id="pag-page-label">Page 1</span>
            <button id="pag-next" type="button">&gt;</button>
          </div>
        </div>
      </div>
    </div>
      </section>

      <section class="workspace-panel" id="workspace-operate-history" data-workspace="#/operate/history">
        <div class="panel-card">
          <h2 class="panel-title">Run History</h2>
          <p class="panel-subtitle">Completed, stopped, failed, and historical crawler runs.</p>
          <div class="table-wrap">
            <table class="responsive-table">
              <thead>
                <tr><th>Run</th><th>Status</th><th>Started</th><th>Finished</th><th>Progress</th><th>Action</th></tr>
              </thead>
              <tbody id="run-history-table-body"><tr><td colspan="6" class="empty">Loading run history...</td></tr></tbody>
            </table>
          </div>
        </div>
      </section>

      <section class="workspace-panel" id="workspace-plan-coverage" data-workspace="#/plan/coverage">

    <!-- COVERAGE TAB -->
    <div class="tab-content" id="tab-coverage">
      <section class="panel-card">
        <div class="workspace-header-row">
          <div>
            <h2 class="panel-title">Coverage</h2>
            <p class="panel-subtitle">Problem-first view of missing, stale, and overlapping department coverage.</p>
          </div>
          <button class="btn" type="button" onclick="refreshCoverage()">Refresh coverage</button>
        </div>
        <div class="summary-row coverage-summary">
          <span>Covered <strong id="plan-covered-count">0</strong></span>
          <span>Missing <strong id="plan-missing-count">0</strong></span>
          <span>Overlap <strong id="plan-overlap-count">0</strong></span>
          <span>Stale <strong id="plan-stale-count">0</strong></span>
        </div>
        <div class="filter-chips" role="toolbar" aria-label="Coverage filters">
          <button class="chip active" type="button" data-coverage-filter="attention">Needs attention</button>
          <button class="chip" type="button" data-coverage-filter="all">All</button>
          <button class="chip" type="button" data-coverage-filter="missing">Missing</button>
          <button class="chip" type="button" data-coverage-filter="overlap">Overlap</button>
          <button class="chip" type="button" data-coverage-filter="stale">Stale</button>
        </div>
        <div class="table-wrap">
          <table class="responsive-table">
            <thead>
              <tr>
                <th>Institution Name</th>
                <th>Job Name</th>
                <th>Last Crawled</th>
                <th>Coverage Status</th>
              </tr>
            </thead>
            <tbody id="coverage-table-body"></tbody>
          </table>
        </div>
      </section>
    </div>
      </section>

      <section class="workspace-panel" id="workspace-plan-schedules" data-workspace="#/plan/schedules">
        <div class="workspace-header-row">
          <div>
            <h2 class="section-title">Schedules</h2>
            <p class="panel-subtitle">Recurring crawler work with next-run context.</p>
          </div>
          <button id="open-new-schedule" class="btn btn-primary" type="button">New schedule</button>
        </div>

    <!-- SCHEDULES TAB -->
    <div class="tab-content" id="tab-schedules">
      <div class="form-section" id="schedule-create-section">
        <h3>Create Persistent Schedule</h3>
        <form id="new-schedule-form">
          <div class="form-grid">
            <div class="form-group">
              <label for="sched-job">Job</label>
              <select id="sched-job" required></select>
            </div>
            <div class="form-group">
              <label for="sched-cron">Cron Expression (or 'hourly', 'daily', 'weekly')</label>
              <input type="text" id="sched-cron" required placeholder="0 0 * * *">
            </div>
            <div class="form-group">
              <label for="sched-policy">Overlap Policy</label>
              <select id="sched-policy">
                <option value="skip">Skip</option>
                <option value="queue">Queue</option>
                <option value="allow">Allow</option>
              </select>
            </div>
          </div>
          <button type="submit" class="btn btn-primary">Create Schedule</button>
        </form>
      </div>

      <div class="workspace">
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Job Name</th>
                <th>Cron / Preset</th>
                <th>Timezone</th>
                <th>Overlap Policy</th>
                <th>Next Run</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody id="schedules-table-body"></tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- LEGACY VIEW (SNAPSHOT DATA) -->
      </section>

      <section class="workspace-panel" id="workspace-explore-snapshot" data-workspace="#/explore/snapshot">

    <div id="overview-select-container" class="panel-card" style="margin-bottom: 18px; display: flex; align-items: center; gap: 12px;" hidden>
      <label for="overview-job-select">Active database view</label>
      <select id="overview-job-select" style="width: auto; min-width: 220px;"></select>
    </div>

    <section class="metrics" id="legacy-metrics-section">
      <div class="metric"><span class="metric-label">Requests</span><strong id="m-requests" class="metric-value">-</strong></div>
      <div class="metric"><span class="metric-label">Departments</span><strong id="m-departments" class="metric-value">-</strong></div>
      <div class="metric"><span class="metric-label">Org units</span><strong id="m-orgs" class="metric-value">-</strong></div>
      <div class="metric"><span class="metric-label">People</span><strong id="m-people" class="metric-value">-</strong></div>
      <div class="metric"><span class="metric-label">Completed</span><strong id="m-done" class="metric-value">-</strong></div>
      <div class="metric"><span class="metric-label">Pending</span><strong id="m-pending" class="metric-value">-</strong></div>
      <div class="metric"><span class="metric-label">Queue errors</span><strong id="m-qerrors" class="metric-value">-</strong></div>
      <div class="metric"><span class="metric-label">Crawl errors</span><strong id="m-errors" class="metric-value">-</strong></div>
    </section>
    <div class="progress-wrap" id="legacy-progress-section" style="display:none;">
      <div class="progress" aria-label="Queue completion"><div id="progress-bar"></div></div>
      <span id="progress-label" class="progress-label">0%</span>
    </div>
    <div id="active-db" class="muted" aria-live="polite">Snapshot database view</div>

    <div class="tab-content" id="tab-legacy">

      <section class="workspace">
        <nav class="tabs" aria-label="Snapshot tables">
          <button class="tab active" data-view="orgs" type="button">Org Units</button>
          <button class="tab" data-view="people" type="button">People</button>
          <button class="tab" data-view="queue" type="button">Queue</button>
          <button class="tab" data-view="errors" type="button">Errors</button>
        </nav>
        <div id="error-banner" class="error-banner" role="alert"></div>
        <div class="filters">
          <input id="search" type="search" placeholder="Search current table" aria-label="Search current table">
          <select id="department" aria-label="Department"><option value="">All departments</option></select>
          <select id="queue-status" aria-label="Queue status" hidden>
            <option value="">All statuses</option>
            <option value="pending">Pending</option>
            <option value="done">Done</option>
            <option value="error">Error</option>
          </select>
          <select id="page-size" aria-label="Rows per page">
            <option value="25">25 rows</option>
            <option value="50" selected>50 rows</option>
            <option value="100">100 rows</option>
          </select>
        </div>
        <div class="table-wrap">
          <table>
            <thead id="table-head"></thead>
            <tbody id="table-body"><tr><td class="empty">Loading snapshot...</td></tr></tbody>
          </table>
        </div>
        <div class="footer">
          <span id="result-count" class="muted">No rows loaded</span>
          <div class="pager">
            <button id="previous" type="button" title="Previous page" aria-label="Previous page">&lt;</button>
            <span id="page-label">Page 1</span>
            <button id="next" type="button" title="Next page" aria-label="Next page">&gt;</button>
          </div>
        </div>
      </section>
    </div>
      </section>
    </main>
  </div>

  <div class="drawer-backdrop" id="start-crawler-backdrop" hidden></div>
  <aside class="drawer" id="start-crawler-drawer" role="dialog" aria-modal="true" aria-labelledby="start-crawler-title" hidden>
    <div class="drawer-header">
      <div>
        <p class="eyebrow">Guided flow</p>
        <h2 id="start-crawler-title">Start crawler</h2>
      </div>
      <button class="btn" type="button" data-close-drawer="start-crawler-drawer">Close</button>
    </div>
    <ol class="flow-steps" aria-label="Crawler setup steps">
      <li>Select target</li>
      <li>Review estimate</li>
      <li>Configure options</li>
      <li>Confirm start</li>
    </ol>
    <div class="drawer-body">
      <div class="drawer-note">
        Select departments, review the estimate, configure options, then create and start the crawler from this guided flow.
      </div>
      <div id="start-crawler-form-mount"></div>
      <div class="drawer-footer">
        <button type="button" class="btn" data-close-drawer="start-crawler-drawer">Cancel</button>
        <button type="button" class="btn btn-primary" onclick="document.getElementById('job-name').focus()">Configure crawler</button>
      </div>
    </div>
  </aside>

  <div class="drawer-backdrop" id="new-schedule-backdrop" hidden></div>
  <aside class="drawer" id="new-schedule-drawer" role="dialog" aria-modal="true" aria-labelledby="new-schedule-title" hidden>
    <div class="drawer-header">
      <div>
        <p class="eyebrow">Guided flow</p>
        <h2 id="new-schedule-title">New schedule</h2>
      </div>
      <button class="btn" type="button" data-close-drawer="new-schedule-drawer">Close</button>
    </div>
    <ol class="flow-steps" aria-label="Schedule setup steps">
      <li>Select target</li>
      <li>Select cadence</li>
      <li>Next run preview</li>
      <li>Advanced cron</li>
    </ol>
    <div class="drawer-body">
      <div class="drawer-note">
        Use the schedule form on this screen to choose the target job, cadence or Advanced cron expression,
        overlap policy, and review server-validated next-run behavior.
      </div>
      <section class="estimate-panel">
        <h3>Next run preview</h3>
        <p id="schedule-next-preview" class="muted">Next run preview updates after cadence selection.</p>
      </section>
      <div id="new-schedule-form-mount"></div>
      <div class="drawer-footer">
        <button type="button" class="btn" data-close-drawer="new-schedule-drawer">Cancel</button>
        <button type="button" class="btn btn-primary" data-close-drawer="new-schedule-drawer" onclick="document.getElementById('sched-job').focus()">Continue to schedule form</button>
      </div>
    </div>
  </aside>

  <script>
    const IS_CONTROL_PLANE = false;

    const views = {
      orgs: {
        columns: [
          ["name", "Org unit"], ["department_name", "Department"], ["depth", "Depth"],
          ["org_path", "Org path"], ["source_url", "Source"]
        ]
      },
      people: {
        columns: [
          ["display_name", "Name"], ["title", "Title"], ["department_name", "Department"],
          ["org_unit", "Org unit"], ["org_path", "Org path"], ["source_url", "Source"]
        ]
      },
      queue: {
        columns: [
          ["org_name", "Org unit"], ["department_name", "Department"], ["depth", "Depth"],
          ["status", "Status"], ["attempts", "Attempts"], ["org_path", "Org path"],
          ["last_error", "Last error"], ["source_url", "Source"]
        ]
      },
      errors: {
        columns: [
          ["created_at", "Time"], ["error", "Error"], ["attempts", "Attempts"], ["source_url", "Source"]
        ]
      }
    };
    
    const state = { view: "orgs", offset: 0, total: 0, loading: false, activeTab: "overview" };
    const pagState = { runId: "", offset: 0, limit: 25, total: 0, status: "" };
    const el = id => document.getElementById(id);

    const routes = {
      "#/operate/overview": {
        title: "Operate",
        description: "Live crawler status, attention items, and next actions.",
        refresh: () => refreshControl()
      },
      "#/operate/crawlers": {
        title: "Crawlers",
        description: "Start crawler work and monitor active runs.",
        refresh: () => Promise.all([refreshJobs(), refreshRuns(), refreshEstimates()])
      },
      "#/operate/history": {
        title: "Run History",
        description: "Review completed, stopped, and failed crawler runs.",
        refresh: () => refreshRuns()
      },
      "#/plan/coverage": {
        title: "Coverage",
        description: "Find missing, stale, or overlapping department coverage.",
        refresh: () => refreshCoverage()
      },
      "#/plan/schedules": {
        title: "Schedules",
        description: "Keep coverage fresh with recurring crawler work.",
        refresh: () => refreshSchedules()
      },
      "#/explore/snapshot": {
        title: "Snapshot Data",
        description: "Inspect active database snapshots, tables, and rows.",
        refresh: () => Promise.all([refresh(), loadDepartments()])
      }
    };

    function currentRoute() {
      return routes[window.location.hash] ? window.location.hash : "#/operate/overview";
    }

    function activateRoute(route) {
      const targetRoute = routes[route] ? route : "#/operate/overview";
      document.querySelectorAll("[data-workspace]").forEach(panel => {
        panel.classList.toggle("active", panel.dataset.workspace === targetRoute);
      });
      document.querySelectorAll("[data-route]").forEach(button => {
        button.classList.toggle("active", button.dataset.route === targetRoute);
      });
      el("page-title").textContent = routes[targetRoute].title;
      el("page-description").textContent = routes[targetRoute].description;
      state.activeTab = targetRoute;
      document.body.classList.remove("nav-open");
      const navToggle = el("mobile-nav-toggle");
      if (navToggle) navToggle.setAttribute("aria-expanded", "false");
    }

    async function refreshCurrentRoute() {
      const route = currentRoute();
      activateRoute(route);
      await routes[route].refresh();
    }

    function setLastUpdated() {
      const node = el("last-updated");
      if (node) node.textContent = `Updated ${new Date().toLocaleTimeString()}`;
    }

    function escapeHtml(value) {
      return String(value ?? "").replace(/[&<>"']/g, char => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
      })[char]);
    }

    function formatNumber(value) {
      return Number(value || 0).toLocaleString();
    }

    // ETA/Heartbeat helpers
    function formatDuration(seconds) {
      if (seconds == null || isNaN(seconds) || seconds < 0) return "";
      if (seconds < 60) return `${Math.round(seconds)}s`;
      if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
      const h = Math.floor(seconds / 3600);
      const m = Math.round((seconds % 3600) / 60);
      return `${h}h ${m}m`;
    }

    function formatDurationRange(lowSeconds, highSeconds) {
      if (lowSeconds == null || highSeconds == null || isNaN(lowSeconds) || isNaN(highSeconds)) return "Calculating ETA";
      const low = formatDuration(lowSeconds);
      const high = formatDuration(highSeconds);
      if (!low || !high) return "Calculating ETA";
      return `${low}–${high}`;
    }

    function formatHeartbeatAge(heartbeatAt) {
      if (!heartbeatAt) return "No heartbeat";
      const seconds = Math.max(0, Math.floor((Date.now() - Date.parse(heartbeatAt)) / 1000));
      if (isNaN(seconds)) return "No heartbeat";
      return `${formatDuration(seconds)} ago`;
    }

    function formatRunEta(eta) {
      if (!eta || eta.expected_seconds == null || isNaN(eta.expected_seconds)) {
        return "Calculating ETA · low confidence";
      }
      const range = formatDurationRange(eta.low_seconds, eta.high_seconds);
      const confidence = eta.confidence || "low";
      return `${range} · ${confidence} confidence`;
    }

    async function getJson(url) {
      const response = await fetch(url, { cache: "no-store" });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
      return payload;
    }
    
    async function postJson(url, data) {
      const response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data)
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
      return payload;
    }

    async function deleteJson(url) {
      const response = await fetch(url, { method: "DELETE" });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
      return payload;
    }

    // --- Control Plane logic ---
    async function loadControlOverview() {
      const data = await getJson("/api/control/overview");
      el("ctrl-m-workers").textContent = data.active_workers;
      el("ctrl-m-conf-rps").textContent = data.configured_rps.toFixed(2);
      el("ctrl-m-meas-rps").textContent = data.measured_rps.toFixed(2);
      el("ctrl-m-depts").textContent = data.total_departments;
      
      // Warn policies
      el("rps-warning-amber").style.display = data.configured_rps > 1.0 ? "block" : "none";
      el("rps-warning-red").style.display = data.configured_rps > 2.0 ? "block" : "none";
      renderAttentionQueue(data);
    }

    // --- Department selection state ---
    let deptRows = []; // [{dn, name, status, last_crawled_at, age_days, org_units, people}]
    let deptSortKey = "age";
    let deptSortAsc = false; // false = descending for age (never crawled first)
    let estimatesData = {};
    const planState = {
      coverageFilter: "attention",
      coverageRows: []
    };

    async function loadControlCatalog() {
      const [depts, cov, est] = await Promise.all([
        getJson("/api/control/catalog"),
        getJson("/api/control/coverage"),
        getJson("/api/control/estimates")
      ]);
      estimatesData = est;
      const now = new Date();
      deptRows = depts.map(dept => {
        const info = cov[dept.dn] || { status: "unassigned", job_name: null, last_crawled_at: null };
        const estInfo = est[dept.dn] || { org_units: 0, people: 0 };
        let ageDays = -1; // -1 = never crawled
        if (info.last_crawled_at) {
          const crawlDate = new Date(info.last_crawled_at);
          ageDays = Math.floor((now - crawlDate) / (1000 * 60 * 60 * 24));
        }
        return {
          dn: dept.dn,
          name: dept.name,
          status: info.status,
          last_crawled_at: info.last_crawled_at,
          age_days: ageDays,
          org_units: estInfo.org_units || 0,
          people: estInfo.people || 0,
        };
      });
      renderDeptTable();
    }

    function renderDeptTable() {
      const search = (el("job-dept-search").value || "").toLowerCase();
      let filtered = deptRows.filter(r => r.name.toLowerCase().includes(search) || r.dn.toLowerCase().includes(search));

      // Sort
      filtered.sort((a, b) => {
        let va, vb;
        if (deptSortKey === "name") { va = a.name.toLowerCase(); vb = b.name.toLowerCase(); }
        else if (deptSortKey === "age") { va = a.age_days; vb = b.age_days; }
        else if (deptSortKey === "status") { va = a.status; vb = b.status; }
        else { va = a.name.toLowerCase(); vb = b.name.toLowerCase(); }

        // For age sort: -1 (never) should be first when descending
        if (deptSortKey === "age") {
          if (va === -1 && vb !== -1) return deptSortAsc ? 1 : -1;
          if (vb === -1 && va !== -1) return deptSortAsc ? -1 : 1;
        }

        if (va < vb) return deptSortAsc ? -1 : 1;
        if (va > vb) return deptSortAsc ? 1 : -1;
        return 0;
      });

      const tbody = el("dept-selection-body");
      // Preserve checked state
      const checked = new Set();
      document.querySelectorAll('input[name="dept-dns"]:checked').forEach(cb => checked.add(cb.value));

      tbody.innerHTML = filtered.map(r => {
        const isChecked = checked.has(r.dn) ? "checked" : "";
        let ageLabel = '<span style="color:#ef4444;font-weight:600;">Never</span>';
        if (r.age_days >= 0) {
          if (r.age_days === 0) ageLabel = '<span style="color:#22c55e;">Today</span>';
          else if (r.age_days <= 7) ageLabel = `<span style="color:#22c55e;">${r.age_days}d ago</span>`;
          else if (r.age_days <= 30) ageLabel = `<span style="color:#eab308;">${r.age_days}d ago</span>`;
          else ageLabel = `<span style="color:#ef4444;">${r.age_days}d ago</span>`;
        }
        return `<tr>
          <td style="text-align:center;"><input type="checkbox" name="dept-dns" value="${escapeHtml(r.dn)}" ${isChecked} style="width:auto;height:auto;" onchange="updateEstimates()"></td>
          <td>${escapeHtml(r.name)}</td>
          <td>${ageLabel}</td>
          <td><span class="badge ${r.status}">${r.status}</span></td>
          <td style="text-align:right;">${r.org_units > 0 ? formatNumber(r.org_units) : '-'}</td>
          <td style="text-align:right;">${r.people > 0 ? formatNumber(r.people) : '-'}</td>
        </tr>`;
      }).join("");

      updateEstimates();
    }

    function updateEstimates() {
      const crawlKind = el("job-crawl-kind").value;
      if (crawlKind === "pagination_backfill") {
        el("est-selected").innerHTML = "Pagination Backfill";
        el("est-requests").innerHTML = "~2,800 to ~11,400 <span style='font-size:10px;color:var(--muted); font-weight:normal;'>(Planning Range)</span>";
        el("est-duration").innerHTML = "1.2h to 5.5h <span style='font-size:10px;color:var(--muted); font-weight:normal;'>(Planning Range)</span>";
        el("est-people").innerHTML = "~30k to ~200k <span style='font-size:10px;color:var(--muted); font-weight:normal;'>(Planning Range)</span>";
        el("est-size").innerHTML = "~220 MB to ~460 MB <span style='font-size:10px;color:var(--muted); font-weight:normal;'>(Planning Range)</span>";
        return;
      }

      const checked = [];
      document.querySelectorAll('input[name="dept-dns"]:checked').forEach(cb => {
        const row = deptRows.find(r => r.dn === cb.value);
        if (row) checked.push(row);
      });
      const totalOrgs = checked.reduce((s, r) => s + (r.org_units || 50), 0); // default 50 if unknown
      const totalPeople = checked.reduce((s, r) => s + r.people, 0);
      const rate = parseFloat(el("job-rate").value) || 1.0;
      const durationSec = totalOrgs * rate;

      el("est-selected").textContent = checked.length + " dept" + (checked.length !== 1 ? "s" : "");
      el("est-requests").textContent = formatNumber(totalOrgs);
      el("est-people").textContent = formatNumber(totalPeople);

      // Format duration nicely
      if (durationSec < 60) el("est-duration").textContent = Math.round(durationSec) + "s";
      else if (durationSec < 3600) el("est-duration").textContent = Math.round(durationSec / 60) + "m";
      else { const h = Math.floor(durationSec / 3600); const m = Math.round((durationSec % 3600) / 60); el("est-duration").textContent = h + "h " + m + "m"; }

      const sizeBytes = totalPeople * 1400;
      if (sizeBytes < 1024 * 1024) el("est-size").textContent = (sizeBytes / 1024).toFixed(0) + " KB";
      else el("est-size").textContent = (sizeBytes / (1024 * 1024)).toFixed(1) + " MB";
    }

    // Bulk actions
    function deptSelectUncrawled() {
      document.querySelectorAll('input[name="dept-dns"]').forEach(cb => {
        const row = deptRows.find(r => r.dn === cb.value);
        if (row && row.age_days === -1) cb.checked = true;
      });
      updateEstimates();
    }
    function deptSelectOutdated() {
      document.querySelectorAll('input[name="dept-dns"]').forEach(cb => {
        const row = deptRows.find(r => r.dn === cb.value);
        if (row && (row.age_days === -1 || row.age_days > 7)) cb.checked = true;
      });
      updateEstimates();
    }
    function deptSelectAll() {
      document.querySelectorAll('input[name="dept-dns"]').forEach(cb => cb.checked = true);
      updateEstimates();
    }
    function deptClearAll() {
      document.querySelectorAll('input[name="dept-dns"]').forEach(cb => cb.checked = false);
      updateEstimates();
    }

    async function loadControlRuns() {
      const runs = await getJson("/api/control/runs");
      const tbody = el("runs-table-body");
      tbody.innerHTML = runs.map(run => {
        let actionBtn = "";
        if (run.status === "running") {
          actionBtn = `<button class="btn btn-danger" onclick="stopRun('${run.id}')" style="height:28px;padding:0 8px;">Stop</button>`;
        } else if (run.status === "stopped" || run.status === "failed") {
          actionBtn = `<button class="btn btn-primary" onclick="resumeRun('${run.id}')" style="height:28px;padding:0 8px;">Resume</button>`;
        }
        
        if (run.crawl_kind === "pagination_backfill") {
          const compFailed = (run.progress.completed_orgs || 0) + (run.progress.failed_orgs || 0);
          const total = run.progress.total_orgs || 1;
          const percent = Math.round(compFailed * 100 / total);
          const compPercent = ((run.progress.completed_orgs || 0) / total * 100).toFixed(1);
          const failPercent = ((run.progress.failed_orgs || 0) / total * 100).toFixed(1);
          const pendingPages = run.pagination_metrics.known_pending_pages ?? run.pagination_metrics["pages_pending"] ?? 0;
          
          return `
            <tr style="cursor: pointer;" onclick="showPaginationOrgsPanel('${run.id}')">
              <td>
                <strong>${escapeHtml(run.job_name || "Unmanaged")}</strong><br>
                <span class="badge done" style="margin-top:4px;">Pagination backfill</span>
              </td>
              <td>
                ${escapeHtml(run.started_at)}<br>
                <small class="muted" id="run-heartbeat-age-${run.id}">${formatHeartbeatAge(run.heartbeat_at)}</small>
              </td>
              <td id="run-progress-${run.id}">
                <span class="badge ${escapeHtml(run.status)}">${escapeHtml(run.status)}</span><br>
                <div class="progress-wrap" style="margin-top: 4px; width: 120px;">
                  <div class="progress" style="height: 6px; display: flex; background: #eef2f5; border-radius: 3px; overflow: hidden;">
                    <div style="background: var(--accent); width: ${compPercent}%;"></div>
                    <div style="background: var(--danger); width: ${failPercent}%;"></div>
                  </div>
                </div>
                <small style="font-size:11px; white-space:nowrap;">
                  ${compFailed} / ${total} orgs (${percent}%)
                </small>
                <div id="run-eta-${run.id}" style="margin-top:2px; font-size:11px; color:var(--muted); white-space:nowrap;">
                  ${formatRunEta(run.eta)}
                </div>
              </td>
              <td>
                Pages: ${formatNumber(run.pagination_metrics.pages_fetched)}<br>
                <span class="muted" style="font-size:11px;">Pending: ${formatNumber(pendingPages)}</span>
              </td>
              <td>
                PID: ${run.pid || "-"}<br>
                <small class="muted">RPS: ${(run.pagination_metrics.measured_rps || 0.0).toFixed(2)} / ${(run.pagination_metrics.configured_rps || 1.0).toFixed(1)}</small>
              </td>
              <td>
                New: ${formatNumber(run.pagination_metrics.new_people)}<br>
                <small class="muted" style="font-size:11px;">Total: ${formatNumber(run.pagination_metrics.total_people)}</small>
              </td>
              <td>
                ${run.status === 'running' ? escapeHtml(run.pagination_metrics.active_org || run.current_org_dn || '-') : (run.eta.finish_time ? 'Finished: ' + run.eta.finish_time : '-')}
              </td>
              <td onclick="event.stopPropagation()">${actionBtn}</td>
            </tr>
          `;
        }

        return `
          <tr>
            <td>${escapeHtml(run.job_name || "Unmanaged")}</td>
            <td>${escapeHtml(run.started_at)}</td>
            <td><span class="badge ${escapeHtml(run.status)}">${escapeHtml(run.status)}</span></td>
            <td>${formatNumber(run.request_count)}</td>
            <td>${run.pid || "-"}</td>
            <td>${escapeHtml(run.heartbeat_at || "-")}</td>
            <td>${escapeHtml(run.current_org_dn || "-")}</td>
            <td>${actionBtn}</td>
          </tr>
        `;
      }).join("");

      // Update overview dropdown
      const selectEl = el("overview-job-select");
      if (selectEl) {
        const currentVal = selectEl.value || "all";
        let optionsHtml = '<option value="all">All Active/Recent Runs (Combined)</option>';
        runs.forEach(run => {
          if (run.job_id === null) {
            optionsHtml += `<option value="unmanaged">Unmanaged Crawl (${escapeHtml((run.started_at || "").split("T")[0])})</option>`;
          } else {
            optionsHtml += `<option value="${run.id}">${escapeHtml(run.job_name)} (${escapeHtml((run.started_at || "").split("T")[0])})</option>`;
          }
        });
        selectEl.innerHTML = optionsHtml;
        selectEl.value = currentVal;
      }
      renderLiveActivity(runs);
      renderRunHistory(runs);
    }

    function renderLiveActivity(runs) {
      const list = el("live-activity-list");
      if (!list) return;
      const active = runs.filter(run => ["running", "starting", "stopping"].includes(run.status));
      if (!active.length) {
        list.innerHTML = '<div class="empty">No active crawlers right now.</div>';
        return;
      }
      list.innerHTML = active.map(run => `
        <div class="activity-item">
          <strong>${escapeHtml(run.job_name || run.id || "Crawler run")}</strong>
          <span class="status-label ${escapeHtml(run.status)}">${escapeHtml(run.status)}</span>
          <span class="muted">RPS ${(run.measured_rps || run.pagination_metrics?.measured_rps || 0).toFixed(2)}</span>
        </div>
      `).join("");
    }

    function renderRunHistory(runs) {
      const tbody = el("run-history-table-body");
      if (!tbody) return;
      if (!runs.length) {
        tbody.innerHTML = '<tr><td colspan="6" class="empty">No run history yet.</td></tr>';
        return;
      }
      tbody.innerHTML = runs.map(run => `
        <tr>
          <td data-label="Run">${escapeHtml(run.job_name || run.id || "Unmanaged")}</td>
          <td data-label="Status"><span class="status-label ${escapeHtml(run.status || "info")}">${escapeHtml(run.status || "-")}</span></td>
          <td data-label="Started">${escapeHtml(run.started_at || "-")}</td>
          <td data-label="Finished">${escapeHtml(run.finished_at || run.eta?.finish_time || "-")}</td>
          <td data-label="Progress">${escapeHtml(run.crawl_kind || "crawl")}</td>
          <td data-label="Action">${run.crawl_kind === "pagination_backfill" ? `<button class="btn" type="button" onclick="showPaginationOrgsPanel('${escapeHtml(run.id)}')">Inspect</button>` : '<span class="muted">-</span>'}</td>
        </tr>
      `).join("");
    }

    function renderAttentionQueue(data) {
      const list = el("attention-list");
      if (!list) return;
      const items = [];
      if ((data.active_workers || 0) === 0) {
        items.push({ level: "attention", title: "No active crawlers", detail: "Start a crawler if coverage needs to be refreshed." });
      }
      if ((data.measured_rps || 0) < (data.configured_rps || 0) * 0.5 && (data.configured_rps || 0) > 0) {
        items.push({ level: "attention", title: "Measured RPS is low", detail: "Throughput is below half of configured RPS." });
      }
      el("nav-attention-count").textContent = String(items.length);
      if (!items.length) {
        list.innerHTML = '<div class="empty">No attention items. System looks quiet.</div>';
        return;
      }
      list.innerHTML = items.map(item => `
        <div class="attention-item">
          <span class="status-label ${item.level}">${item.level}</span>
          <strong>${escapeHtml(item.title)}</strong>
          <span class="muted">${escapeHtml(item.detail)}</span>
        </div>
      `).join("");
    }

    async function loadControlCoverage() {
      const cov = await getJson("/api/control/coverage");
      const depts = await getJson("/api/control/catalog");
      planState.coverageRows = depts.map(dept => {
        const info = cov[dept.dn] || { status: "unassigned", job_name: null, last_crawled_at: null };
        const status = info.status === "covered-current" ? "covered" : (info.status || "missing");
        const jobName = info.job_name || "-";
        const lastCrawled = info.last_crawled_at || "-";
        return {
          name: dept.name,
          jobName,
          lastCrawled,
          status,
          source: dept.source_url || ""
        };
      });
      const covered = planState.coverageRows.filter(row => row.status === "covered").length;
      const missing = planState.coverageRows.filter(row => row.status === "missing" || row.status === "unassigned").length;
      const overlap = planState.coverageRows.filter(row => row.status === "overlap").length;
      const stale = planState.coverageRows.filter(row => row.status === "stale").length;
      setText("plan-covered-count", covered);
      setText("plan-missing-count", missing);
      setText("plan-overlap-count", overlap);
      setText("plan-stale-count", stale);
      renderCoverageRows(planState.coverageRows);
    }

    function setText(id, value) {
      const node = el(id);
      if (node) node.textContent = String(value);
    }

    function renderCoverageRows(rows) {
      const tbody = el("coverage-table-body");
      if (!tbody) return;
      const filter = planState.coverageFilter;
      const filtered = rows.filter(row => {
        if (filter === "all") return true;
        if (filter === "attention") return row.status !== "covered";
        return row.status === filter;
      });
      if (!filtered.length) {
        tbody.innerHTML = '<tr><td colspan="4" class="empty">No rows match this coverage filter.</td></tr>';
        return;
      }
      tbody.innerHTML = filtered.map(row => `
          <tr>
            <td data-label="Institution Name">${escapeHtml(row.name)}</td>
            <td data-label="Job Name">${escapeHtml(row.jobName)}</td>
            <td data-label="Last Crawled">${escapeHtml(row.lastCrawled)}</td>
            <td data-label="Coverage Status"><span class="status-label ${row.status === "covered" ? "healthy" : "attention"}">${escapeHtml(row.status)}</span></td>
          </tr>
        `).join("");
    }

    async function loadControlSchedules() {
      const scheds = await getJson("/api/control/schedules");
      
      // Update schedule job list dropdown
      const jobs = await getJson("/api/control/jobs");
      const selectEl = el("sched-job");
      selectEl.innerHTML = jobs.map(job => `<option value="${job.id}">${escapeHtml(job.name)}</option>`).join("");
      
      const tbody = el("schedules-table-body");
      tbody.innerHTML = scheds.map(sched => `
        <tr>
          <td>${escapeHtml(sched.job_name)}</td>
          <td>${escapeHtml(sched.expression)}</td>
          <td>${escapeHtml(sched.timezone)}</td>
          <td>${escapeHtml(sched.overlap_policy)}</td>
          <td>${escapeHtml(sched.next_run_at || "-")}</td>
          <td>
            <button class="btn btn-danger" onclick="deleteSchedule('${sched.id}')" style="height:28px;padding:0 8px;">Delete</button>
          </td>
        </tr>
      `).join("");
    }

    window.stopRun = async function(runId) {
      try {
        await postJson(`/api/control/runs/${runId}/stop`, {});
        refreshControl();
      } catch (err) {
        alert(err.message);
      }
    };

    window.resumeRun = async function(runId) {
      try {
        await postJson(`/api/control/runs/${runId}/resume`, {});
        refreshControl();
      } catch (err) {
        alert(err.message);
      }
    };

    window.deleteSchedule = async function(schedId) {
      try {
        await deleteJson(`/api/control/schedules?id=${schedId}`);
        loadControlSchedules();
      } catch (err) {
        alert(err.message);
      }
    };

    // Auto-populate Output Directory dynamically based on Job Name and Date
    const updateOutputDirectory = () => {
      const name = el("job-name").value;
      const dateStr = new Date().toISOString().split('T')[0];
      const slug = name.toLowerCase()
        .replace(/[^a-z0-9_ -]/g, '')
        .replace(/\\s+/g, '-')
        .replace(/-+/g, '-')
        .trim();
      if (slug) {
        el("job-output").value = `outputs/runs/${dateStr}/${slug}`;
      } else {
        el("job-output").value = `outputs/runs/${dateStr}`;
      }
    };
    el("job-name").addEventListener("input", updateOutputDirectory);
    updateOutputDirectory();

    // Refresh overview stats and snapshot views on active DB dropdown changes
    el("overview-job-select").addEventListener("change", () => {
      state.offset = 0;
      autoRefresh();
    });

    // Department table search
    el("job-dept-search").addEventListener("input", () => renderDeptTable());

    // Department table sorting
    document.querySelectorAll("#dept-selection-table thead th[data-sort]").forEach(th => {
      th.addEventListener("click", () => {
        const key = th.dataset.sort;
        if (deptSortKey === key) deptSortAsc = !deptSortAsc;
        else { deptSortKey = key; deptSortAsc = true; }
        renderDeptTable();
      });
    });

    // Toggle all visible checkboxes
    el("dept-toggle-all").addEventListener("change", (e) => {
      document.querySelectorAll('input[name="dept-dns"]').forEach(cb => cb.checked = e.target.checked);
      updateEstimates();
    });

    // Recalculate estimates when rate limit changes
    el("job-rate").addEventListener("input", () => updateEstimates());

    // Crawl Kind Form field toggle
    el("job-crawl-kind").addEventListener("change", () => {
      const isBackfill = el("job-crawl-kind").value === "pagination_backfill";
      el("dept-selection-container").style.display = isBackfill ? "none" : "block";
      el("source-db-container").style.display = isBackfill ? "block" : "none";
      el("job-source-db").required = isBackfill;
      updateEstimates();
    });

    el("new-job-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const name = el("job-name").value;
      const crawlKind = el("job-crawl-kind").value;
      const rate = parseFloat(el("job-rate").value);
      const policy = el("job-policy").value;
      const output = el("job-output").value;
      const sourceDb = el("job-source-db").value;
      
      let dns = [];
      if (crawlKind === "full") {
        document.querySelectorAll('input[name="dept-dns"]:checked').forEach(cb => {
          dns.push(cb.value);
        });
        if (dns.length === 0) {
          alert("Please select at least one department.");
          return;
        }
      } else {
        if (!sourceDb) {
          alert("Please specify a source database path.");
          return;
        }
      }
      
      try {
        const payload = {
          name: name,
          crawl_kind: crawlKind,
          rate_limit_seconds: rate,
          traffic_policy: policy,
          output_dir: output
        };
        if (crawlKind === "full") {
          payload.department_dns = dns;
        } else {
          payload.source_db_path = sourceDb;
        }
        
        const resp = await postJson("/api/control/jobs", payload);
        // Start run automatically
        await postJson("/api/control/runs", { job_id: resp.job_id });
        el("new-job-form").reset();
        
        // Reset crawl kind UI toggles
        el("dept-selection-container").style.display = "block";
        el("source-db-container").style.display = "none";
        el("job-source-db").required = false;
        
        refreshControl();
      } catch (err) {
        alert(err.message);
      }
    });

    el("new-schedule-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const jobId = el("sched-job").value;
      const cron = el("sched-cron").value;
      const policy = el("sched-policy").value;
      
      try {
        await postJson("/api/control/schedules", {
          job_id: jobId,
          expression: cron,
          overlap_policy: policy
        });
        el("new-schedule-form").reset();
        loadControlSchedules();
      } catch (err) {
        alert(err.message);
      }
    });

    // Pagination Orgs Details logic
    async function loadPaginationOrgs() {
      if (!pagState.runId) return;
      const params = new URLSearchParams({
        limit: pagState.limit,
        offset: pagState.offset,
        status: pagState.status
      });
      try {
        const data = await getJson(`/api/control/runs/${pagState.runId}/pagination-orgs?${params}`);
        const tbody = el("pag-orgs-table-body");
        if (!data.items.length) {
          tbody.innerHTML = `<tr><td colspan="7" class="empty">No matching organizations</td></tr>`;
        } else {
          tbody.innerHTML = data.items.map(item => {
            return `
              <tr>
                <td>
                  <strong>${escapeHtml(item.department_name)}</strong><br>
                  <small class="muted">${escapeHtml(item.org_path)}</small>
                </td>
                <td><span class="badge ${escapeHtml(item.status)}">${escapeHtml(item.status)}</span></td>
                <td>${formatNumber(item.pages_crawled)}</td>
                <td>${formatNumber(item.new_people_count)}</td>
                <td>${formatNumber(item.deduplicated_people_count)}</td>
                <td style="font-size:11px; word-break:break-all;">
                  ${item.last_page_url ? `<a class="source" href="${escapeHtml(item.last_page_url)}" target="_blank">${escapeHtml(item.last_page_url)}</a>` : "-"}
                </td>
                <td class="muted">${escapeHtml(item.failure_reason || "-")}</td>
              </tr>
            `;
          }).join("");
        }
        
        pagState.total = data.total;
        const start = data.total ? data.offset + 1 : 0;
        const end = Math.min(data.offset + data.items.length, data.total);
        const page = Math.floor(data.offset / pagState.limit) + 1;
        const pages = Math.max(Math.ceil(data.total / pagState.limit), 1);
        
        el("pag-result-count").textContent = `${formatNumber(start)}-${formatNumber(end)} of ${formatNumber(data.total)}`;
        el("pag-page-label").textContent = `Page ${page} of ${pages}`;
        el("pag-previous").disabled = pagState.offset === 0;
        el("pag-next").disabled = pagState.offset + pagState.limit >= data.total;
      } catch (err) {
        console.error(err);
      }
    }

    window.showPaginationOrgsPanel = function(runId) {
      pagState.runId = runId;
      pagState.offset = 0;
      pagState.status = el("pag-filter-status").value = "";
      el("pag-panel-run-name").textContent = runId;
      el("pagination-orgs-panel").style.display = "block";
      el("pagination-orgs-panel").scrollIntoView({ behavior: "smooth" });
      loadPaginationOrgs();
    };

    window.hidePaginationOrgsPanel = function() {
      pagState.runId = "";
      el("pagination-orgs-panel").style.display = "none";
    };

    el("pag-filter-status").addEventListener("change", () => {
      pagState.status = el("pag-filter-status").value;
      pagState.offset = 0;
      loadPaginationOrgs();
    });
    el("pag-previous").addEventListener("click", () => {
      pagState.offset = Math.max(0, pagState.offset - pagState.limit);
      loadPaginationOrgs();
    });
    el("pag-next").addEventListener("click", () => {
      pagState.offset += pagState.limit;
      loadPaginationOrgs();
    });

    async function refreshJobs() {
      await loadControlCatalog();
    }

    async function refreshRuns() {
      await loadControlRuns();
      if (pagState.runId) {
        await loadPaginationOrgs();
      }
    }

    async function refreshSchedules() {
      await loadControlSchedules();
    }

    async function refreshCoverage() {
      await loadControlCoverage();
    }

    async function refreshEstimates() {
      await loadControlCatalog();
    }

    async function refresh() {
      await refreshLegacy();
    }

    async function refreshControl() {
      if (state.loading) return;
      state.loading = true;
      try {
        await loadControlOverview();
        await loadControlCatalog();
        await loadControlRuns();
        await loadControlCoverage();
        await loadControlSchedules();
        if (pagState.runId) {
          await loadPaginationOrgs();
        }
        setLastUpdated();
      } catch (err) {
        console.error(err);
      } finally {
        state.loading = false;
      }
    }

    // --- Legacy / Snapshot Data view ---
    async function loadStatus() {
      const runId = IS_CONTROL_PLANE ? el("overview-job-select").value : "";
      const url = runId ? `/api/status?run_id=${encodeURIComponent(runId)}` : "/api/status";
      const data = await getJson(url);
      el("run-state").textContent = `Status: ${data.run_status || "unknown"}`;
      el("m-requests").textContent = formatNumber(data.request_count);
      el("m-departments").textContent = formatNumber(data.departments);
      el("m-orgs").textContent = formatNumber(data.org_units);
      el("m-people").textContent = formatNumber(data.people);
      el("m-done").textContent = formatNumber(data.queue.done);
      el("m-pending").textContent = formatNumber(data.queue.pending);
      el("m-qerrors").textContent = formatNumber(data.queue.error);
      el("m-errors").textContent = formatNumber(data.errors);

      // Update legacy elements for backward compatibility
      el("progress-bar").style.width = `${data.completion_percent}%`;
      el("progress-label").textContent = `${data.completion_percent}% complete`;

      // Update new top progress bar and label
      const pct = data.completion_percent || 0.0;
      el("top-progress-bar").style.width = `${pct}%`;
      el("top-progress-label").textContent = `${pct}% complete`;

      const doneVal = data.queue.done || 0;
      const pendingVal = data.queue.pending || 0;
      const errorVal = data.queue.error || 0;
      const totalVal = doneVal + pendingVal + errorVal;

      if (data.crawl_kind === "pagination_backfill") {
        el("top-progress-text").textContent = `Backfill Progress: ${formatNumber(doneVal + errorVal)} / ${formatNumber(totalVal)} orgs`;
      } else {
        el("top-progress-text").textContent = `Crawl Progress: ${formatNumber(doneVal + errorVal)} / ${formatNumber(totalVal)} pages`;
      }

      // Update top estimation metadata
      el("top-kind-val").textContent = data.crawl_kind === "pagination_backfill" ? "Pagination Backfill" : "Full crawl";

      if (data.measured_rps != null) {
        el("top-rps-val").textContent = `${data.measured_rps.toFixed(2)} RPS`;
      } else {
        el("top-rps-val").textContent = "-";
      }

      if (data.eta) {
        el("top-eta-val").textContent = formatRunEta(data.eta);
      } else {
        el("top-eta-val").textContent = "Calculating ETA";
      }
    }

    async function loadDepartments() {
      const selected = el("department").value;
      const runId = IS_CONTROL_PLANE ? el("overview-job-select").value : "";
      const url = runId ? `/api/departments?run_id=${encodeURIComponent(runId)}` : "/api/departments";
      const departments = await getJson(url);
      el("department").innerHTML = '<option value="">All departments</option>' +
        departments.map(name => `<option value="${escapeHtml(name)}">${escapeHtml(name)}</option>`).join("");
      el("department").value = selected;
    }

    function queryUrl() {
      const params = new URLSearchParams({
        q: el("search").value,
        limit: el("page-size").value,
        offset: state.offset
      });
      const runId = IS_CONTROL_PLANE ? el("overview-job-select").value : "";
      if (runId) {
        params.set("run_id", runId);
      }
      if (state.view !== "errors" && el("department").value) {
        params.set("department", el("department").value);
      }
      if (state.view === "queue" && el("queue-status").value) {
        params.set("status", el("queue-status").value);
      }
      return `/api/${state.view}?${params}`;
    }

    function renderTable(data) {
      const columns = views[state.view].columns;
      el("table-head").innerHTML = `<tr>${columns.map(([, label]) => `<th>${label}</th>`).join("")}</tr>`;
      if (!data.items.length) {
        el("table-body").innerHTML = `<tr><td class="empty" colspan="${columns.length}">No matching rows</td></tr>`;
      } else {
        el("table-body").innerHTML = data.items.map(item => `<tr>${columns.map(([key]) => {
          const value = item[key];
          if (key === "source_url") {
            return `<td><a class="source" href="${escapeHtml(value)}" target="_blank" rel="noopener noreferrer">Open GEDS</a></td>`;
          }
          if (key === "status") {
            return `<td><span class="badge ${escapeHtml(value)}">${escapeHtml(value)}</span></td>`;
          }
          return `<td>${value === null || value === "" ? '<span class="muted">-</span>' : escapeHtml(value)}</td>`;
        }).join("")}</tr>`).join("");
      }
      state.total = data.total;
      const start = data.total ? data.offset + 1 : 0;
      const end = Math.min(data.offset + data.items.length, data.total);
      const page = Math.floor(data.offset / data.limit) + 1;
      const pages = Math.max(Math.ceil(data.total / data.limit), 1);
      el("result-count").textContent = `${formatNumber(start)}-${formatNumber(end)} of ${formatNumber(data.total)}`;
      el("page-label").textContent = `Page ${page} of ${pages}`;
      el("previous").disabled = data.offset === 0;
      el("next").disabled = data.offset + data.limit >= data.total;
    }

    async function refreshLegacy() {
      if (state.loading) return;
      state.loading = true;
      try {
        await Promise.all([loadStatus(), loadDepartments()]);
        const data = await getJson(queryUrl());
        renderTable(data);
        el("error-banner").style.display = "none";
        setLastUpdated();
      } catch (error) {
        el("error-banner").textContent = error.message;
        el("error-banner").style.display = "block";
      } finally {
        state.loading = false;
      }
    }

    function setView(view) {
      state.view = view;
      state.offset = 0;
      document.querySelectorAll(".tab").forEach(tab => tab.classList.toggle("active", tab.dataset.view === view));
      el("department").hidden = view === "errors";
      el("queue-status").hidden = view !== "queue";
      refreshLegacy();
    }

    // Attach event listeners for legacy view
    document.querySelectorAll(".tab").forEach(tab => tab.addEventListener("click", () => setView(tab.dataset.view)));
    el("refresh").addEventListener("click", () => {
      refreshCurrentRoute().catch(error => console.error(error));
    });
    
    el("search").addEventListener("input", () => {
      state.offset = 0;
      clearTimeout(window.searchTimer);
      window.searchTimer = setTimeout(() => {
        if (currentRoute() === "#/explore/snapshot") refreshLegacy();
      }, 250);
    });
    
    ["department", "queue-status", "page-size"].forEach(id => el(id).addEventListener("change", () => {
      state.offset = 0;
      refreshLegacy();
    }));
    
    el("previous").addEventListener("click", () => {
      state.offset = Math.max(0, state.offset - Number(el("page-size").value));
      refreshLegacy();
    });
    el("next").addEventListener("click", () => {
      state.offset += Number(el("page-size").value);
      refreshLegacy();
    });

    let lastFocusedElement = null;

    function openDrawer(drawerId) {
      const drawer = el(drawerId);
      const backdrop = el(drawerId.replace("-drawer", "-backdrop"));
      if (!drawer) return;
      lastFocusedElement = document.activeElement;
      drawer.hidden = false;
      if (backdrop) backdrop.hidden = false;
      const firstInput = drawer.querySelector("button, input, select, textarea");
      if (firstInput) firstInput.focus();
    }

    function closeDrawer(drawerId) {
      const drawer = el(drawerId);
      const backdrop = el(drawerId.replace("-drawer", "-backdrop"));
      if (!drawer) return;
      drawer.hidden = true;
      if (backdrop) backdrop.hidden = true;
      if (lastFocusedElement && typeof lastFocusedElement.focus === "function") {
        lastFocusedElement.focus();
      }
    }

    if (el("open-start-crawler")) {
      el("open-start-crawler").addEventListener("click", () => openDrawer("start-crawler-drawer"));
    }
    if (el("open-new-schedule")) {
      el("open-new-schedule").addEventListener("click", () => openDrawer("new-schedule-drawer"));
    }
    document.querySelectorAll("[data-close-drawer]").forEach(button => {
      button.addEventListener("click", () => closeDrawer(button.dataset.closeDrawer));
    });
    document.addEventListener("keydown", event => {
      if (event.key === "Escape") {
        document.querySelectorAll(".drawer:not([hidden])").forEach(drawer => closeDrawer(drawer.id));
      }
    });
    const crawlerCreateSection = el("crawler-create-section");
    const crawlerFormMount = el("start-crawler-form-mount");
    if (crawlerCreateSection && crawlerFormMount) {
      crawlerFormMount.appendChild(crawlerCreateSection);
    }
    const scheduleCreateSection = el("schedule-create-section");
    const scheduleFormMount = el("new-schedule-form-mount");
    if (scheduleCreateSection && scheduleFormMount) {
      scheduleFormMount.appendChild(scheduleCreateSection);
    }
    document.querySelectorAll("[data-coverage-filter]").forEach(button => {
      button.addEventListener("click", () => {
        planState.coverageFilter = button.dataset.coverageFilter;
        document.querySelectorAll("[data-coverage-filter]").forEach(chip => {
          chip.classList.toggle("active", chip.dataset.coverageFilter === planState.coverageFilter);
        });
        renderCoverageRows(planState.coverageRows);
      });
    });
    function updateSchedulePreview() {
      const cron = el("sched-cron") ? el("sched-cron").value : "";
      const preview = el("schedule-next-preview");
      if (preview) preview.textContent = `Next run preview: ${cron || "server default"} in America/Toronto. Server validates the cron expression when saved.`;
    }
    if (el("sched-cron")) {
      el("sched-cron").addEventListener("input", updateSchedulePreview);
      updateSchedulePreview();
    }

    document.querySelectorAll("[data-route]").forEach(button => {
      button.addEventListener("click", () => {
        window.location.hash = button.dataset.route;
      });
    });
    window.addEventListener("hashchange", () => {
      refreshCurrentRoute().catch(error => console.error(error));
    });
    if (el("mobile-nav-toggle")) {
      el("mobile-nav-toggle").addEventListener("click", () => {
        const open = !document.body.classList.contains("nav-open");
        document.body.classList.toggle("nav-open", open);
        el("mobile-nav-toggle").setAttribute("aria-expanded", String(open));
      });
    }

    // Auto-refresh loop
    function autoRefresh() {
      refreshCurrentRoute().catch(error => console.error(error));
    }
    
    autoRefresh();
    setInterval(autoRefresh, 3000);
  </script>
</body>
</html>
"""
