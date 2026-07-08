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
                    
                    if not name or not dept_dns or not out_dir:
                        self._json(HTTPStatus.BAD_REQUEST, {"error": "Missing parameters"})
                        return
                        
                    from .control_store import ControlStore
                    with ControlStore(db_path) as store:
                        job_id = store.create_job(name, dept_dns, rate_limit, policy, out_dir)
                    self._json(HTTPStatus.OK, {"job_id": job_id})
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
                    pm.start_run(run_id)
                    self._json(HTTPStatus.OK, {"run_id": run_id, "status": "running"})
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
            # Control plane GET endpoints
            if is_control_plane:
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
                    with ControlStore(db_path) as store:
                        runs = store.list_runs()
                    
                    fb = (db_path.parent.parent / "geds-snapshot-2026-07-08" / "geds.sqlite").resolve()
                    if not fb.is_file():
                        fb = Path("outputs/geds-snapshot-2026-07-08/geds.sqlite").resolve()
                        
                    if fb.is_file():
                        try:
                            with sqlite3.connect(fb) as conn:
                                conn.row_factory = sqlite3.Row
                                # Inspect actual columns to handle older schema versions gracefully
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
                                    if not any(r["id"] == run_id for r in runs):
                                        runs.append({
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
                    return runs

            # Legacy / snapshot reader endpoints
            snap_db = db_path
            if is_control_plane:
                try:
                    with sqlite3.connect(db_path) as conn:
                        row = conn.execute(
                            "SELECT output_dir FROM crawl_runs ORDER BY started_at DESC LIMIT 1"
                        ).fetchone()
                        if row:
                            out_dir = Path(row[0])
                            for name in ("geds.sqlite", "staging.sqlite"):
                                p = out_dir / name
                                if p.is_file():
                                    snap_db = p
                                    break
                except Exception:
                    pass
                if snap_db == db_path:
                    fb = Path("outputs/geds-snapshot-2026-07-08/geds.sqlite").resolve()
                    if fb.is_file():
                        snap_db = fb

            try:
                req_reader = SnapshotReader(snap_db)
                if path == "/api/status":
                    return req_reader.status()
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
    .badge.done, .badge.running, .badge.covered-current { color: #176b4d; background: var(--accent-soft); }
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
  <div class="warning-banner">
    Development only: unauthenticated crawl control. Do not expose this service to an untrusted LAN or the public internet.
  </div>
  <header>
    <div class="brand">
      <h1 id="brand-title">GEDS Snapshot Monitor</h1>
      <span id="run-state" class="run-state">Connecting...</span>
    </div>
    <div class="refresh-meta">
      <span id="last-refresh">Waiting for data</span>
      <button id="refresh" class="header-button" type="button">Refresh</button>
    </div>
  </header>
  <main>
    <nav class="nav-tabs" id="control-tabs" hidden>
      <button class="nav-tab active" data-tab="overview">Overview</button>
      <button class="nav-tab" data-tab="crawlers">Crawlers</button>
      <button class="nav-tab" data-tab="coverage">Coverage</button>
      <button class="nav-tab" data-tab="schedules">Schedules</button>
      <button class="nav-tab" data-tab="legacy">Snapshot Data</button>
    </nav>

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
    <div class="progress-wrap" id="legacy-progress-section">
      <div class="progress" aria-label="Queue completion"><div id="progress-bar"></div></div>
      <span id="progress-label" class="progress-label">0%</span>
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
    </div>

    <!-- CRAWLERS TAB -->
    <div class="tab-content" id="tab-crawlers" style="display:none;">
      <!-- Create Crawler Job -->
      <div class="form-section">
        <h3>Create New Crawler Job</h3>
        <form id="new-job-form">
          <div class="form-grid">
            <div class="form-group">
              <label for="job-name">Job Name</label>
              <input type="text" id="job-name" required placeholder="e.g. ISED + CRTC">
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
          </div>
          <div class="form-group" style="margin-bottom:16px;">
            <label>Select Departments</label>
            <div style="max-height: 150px; overflow-y: scroll; border: 1px solid var(--line); padding: 8px; border-radius: 4px;" id="dept-selection-list">
              <!-- Checkboxes populate dynamically -->
            </div>
            <label style="margin-top: 6px; display: flex; align-items: center; gap: 6px;">
              <input type="checkbox" id="job-all-remaining" style="width: auto; height: auto;"> Or use "All remaining institutions"
            </label>
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
    </div>

    <!-- COVERAGE TAB -->
    <div class="tab-content" id="tab-coverage" style="display:none;">
      <div class="workspace">
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Institution Name</th>
                <th>Canonical DN</th>
                <th>Coverage Status</th>
              </tr>
            </thead>
            <tbody id="coverage-table-body"></tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- SCHEDULES TAB -->
    <div class="tab-content" id="tab-schedules" style="display:none;">
      <div class="form-section">
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
  </main>

  <script>
    const IS_CONTROL_PLANE = false;
    
    // UI Router
    if (IS_CONTROL_PLANE) {
      document.getElementById("brand-title").textContent = "GEDS Crawl Control Plane";
      document.getElementById("control-tabs").hidden = false;
      document.getElementById("tab-legacy").style.display = "none";
    }

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
    const el = id => document.getElementById(id);

    function escapeHtml(value) {
      return String(value ?? "").replace(/[&<>"']/g, char => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
      })[char]);
    }

    function formatNumber(value) {
      return Number(value || 0).toLocaleString();
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
    }

    async function loadControlCatalog() {
      const depts = await getJson("/api/control/catalog");
      const listEl = el("dept-selection-list");
      if (listEl.children.length === 0) {
        listEl.innerHTML = depts.map(dept => `
          <label style="display: block; margin-bottom: 4px;">
            <input type="checkbox" name="dept-dns" value="${escapeHtml(dept.dn)}" style="width:auto;height:auto;">
            ${escapeHtml(dept.name)}
          </label>
        `).join("");
      }
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
    }

    async function loadControlCoverage() {
      const cov = await getJson("/api/control/coverage");
      const depts = await getJson("/api/control/catalog");
      const tbody = el("coverage-table-body");
      tbody.innerHTML = depts.map(dept => {
        const status = cov[dept.dn] || "unassigned";
        return `
          <tr>
            <td>${escapeHtml(dept.name)}</td>
            <td>${escapeHtml(dept.dn)}</td>
            <td><span class="badge ${status}">${status}</span></td>
          </tr>
        `;
      }).join("");
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

    el("new-job-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const name = el("job-name").value;
      const rate = parseFloat(el("job-rate").value);
      const policy = el("job-policy").value;
      const output = el("job-output").value;
      const allRemaining = el("job-all-remaining").checked;
      
      let dns = [];
      if (!allRemaining) {
        document.querySelectorAll('input[name="dept-dns"]:checked').forEach(cb => {
          dns.push(cb.value);
        });
        if (dns.length === 0) {
          alert("Please select at least one department or check 'All remaining'");
          return;
        }
      } else {
        // "all remaining" - get from API
        const rem = await getJson("/api/control/catalog");
        dns = rem.map(r => r.dn);
      }
      
      try {
        const resp = await postJson("/api/control/jobs", {
          name: name,
          department_dns: dns,
          rate_limit_seconds: rate,
          traffic_policy: policy,
          output_dir: output
        });
        // Start run automatically
        await postJson("/api/control/runs", { job_id: resp.job_id });
        el("new-job-form").reset();
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

    async function refreshControl() {
      if (state.loading) return;
      state.loading = true;
      try {
        await loadControlOverview();
        await loadControlCatalog();
        await loadControlRuns();
        await loadControlCoverage();
        await loadControlSchedules();
        el("last-refresh").textContent = `Updated ${new Date().toLocaleTimeString()}`;
      } catch (err) {
        console.error(err);
      } finally {
        state.loading = false;
      }
    }

    // Tab switching for Control Plane
    document.querySelectorAll("#control-tabs .nav-tab").forEach(tab => {
      tab.addEventListener("click", () => {
        document.querySelectorAll("#control-tabs .nav-tab").forEach(t => t.classList.remove("active"));
        tab.classList.add("active");
        
        const target = tab.dataset.tab;
        state.activeTab = target;
        
        // Hide all tab contents
        document.querySelectorAll(".tab-content").forEach(tc => tc.style.display = "none");
        
        if (target === "legacy") {
          el("tab-legacy").style.display = "block";
          refreshLegacy();
        } else {
          el(`tab-${target}`).style.display = "block";
          refreshControl();
        }
      });
    });

    // --- Legacy / Snapshot Data view ---
    async function loadStatus() {
      const data = await getJson("/api/status");
      el("run-state").textContent = `Status: ${data.run_status || "unknown"}`;
      el("m-requests").textContent = formatNumber(data.request_count);
      el("m-departments").textContent = formatNumber(data.departments);
      el("m-orgs").textContent = formatNumber(data.org_units);
      el("m-people").textContent = formatNumber(data.people);
      el("m-done").textContent = formatNumber(data.queue.done);
      el("m-pending").textContent = formatNumber(data.queue.pending);
      el("m-qerrors").textContent = formatNumber(data.queue.error);
      el("m-errors").textContent = formatNumber(data.errors);
      el("progress-bar").style.width = `${data.completion_percent}%`;
      el("progress-label").textContent = `${data.completion_percent}% complete`;
    }

    async function loadDepartments() {
      const selected = el("department").value;
      const departments = await getJson("/api/departments");
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
        el("last-refresh").textContent = `Updated ${new Date().toLocaleTimeString()}`;
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
      if (IS_CONTROL_PLANE && state.activeTab !== "legacy") {
        refreshControl();
      } else {
        refreshLegacy();
      }
    });
    
    el("search").addEventListener("input", () => {
      state.offset = 0;
      clearTimeout(window.searchTimer);
      window.searchTimer = setTimeout(() => {
        if (IS_CONTROL_PLANE && state.activeTab !== "legacy") {
          // Add search filter for control plane views if needed
        } else {
          refreshLegacy();
        }
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

    // Auto-refresh loop
    function autoRefresh() {
      if (IS_CONTROL_PLANE && state.activeTab !== "legacy") {
        refreshControl();
        loadStatus();
      } else {
        refreshLegacy();
      }
    }
    
    autoRefresh();
    setInterval(autoRefresh, 3000);
  </script>
</body>
</html>
"""
