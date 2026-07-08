from __future__ import annotations

import json
import sqlite3
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
    reader = SnapshotReader(db_path)

    class SnapshotHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/":
                self._send(HTTPStatus.OK, DASHBOARD_HTML.encode("utf-8"), "text/html; charset=utf-8")
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

        def _api_payload(self, path: str, query: dict[str, list[str]]):
            if path == "/api/status":
                return reader.status()
            if path == "/api/departments":
                return reader.departments()

            common = {
                "query": _text(query, "q"),
                "limit": _integer(query, "limit", 50),
                "offset": _integer(query, "offset", 0),
            }
            if path == "/api/orgs":
                return reader.orgs(department=_text(query, "department"), **common)
            if path == "/api/people":
                return reader.people(department=_text(query, "department"), **common)
            if path == "/api/queue":
                return reader.queue(
                    department=_text(query, "department"),
                    status=_text(query, "status"),
                    **common,
                )
            if path == "/api/errors":
                return reader.errors(**common)
            return None

        def _json(self, status: HTTPStatus, payload) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self._send(status, body, "application/json; charset=utf-8")

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
  <title>GEDS Snapshot Monitor</title>
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
      --warning: #b54708;
      font-family: Inter, "Segoe UI", Arial, sans-serif;
    }
    * { box-sizing: border-box; }
    body { margin: 0; color: var(--ink); background: var(--soft); font-size: 14px; }
    button, input, select { font: inherit; }
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
    .metrics {
      display: grid; grid-template-columns: repeat(8, minmax(95px, 1fr));
      background: var(--panel); border: 1px solid var(--line); border-radius: 6px;
    }
    .metric { padding: 13px 15px; border-right: 1px solid var(--line); min-width: 0; }
    .metric:last-child { border-right: 0; }
    .metric-label { display: block; color: var(--muted); font-size: 11px; text-transform: uppercase; }
    .metric-value { display: block; margin-top: 4px; font-size: 21px; font-weight: 650; }
    .progress-wrap { margin: 12px 0 18px; display: grid; grid-template-columns: 1fr auto; gap: 10px; align-items: center; }
    .progress { height: 6px; background: #dde3e8; overflow: hidden; border-radius: 3px; }
    .progress > div { height: 100%; width: 0; background: var(--accent); transition: width .25s ease; }
    .progress-label { font-size: 12px; color: var(--muted); }
    .workspace { background: var(--panel); border: 1px solid var(--line); border-radius: 6px; overflow: hidden; }
    .tabs { display: flex; border-bottom: 1px solid var(--line); background: #fafbfc; overflow-x: auto; }
    .tab {
      border: 0; border-right: 1px solid var(--line); border-bottom: 3px solid transparent;
      padding: 12px 18px 9px; background: transparent; color: var(--muted); cursor: pointer;
    }
    .tab.active { color: var(--ink); border-bottom-color: var(--accent); background: white; font-weight: 650; }
    .filters {
      display: grid; grid-template-columns: minmax(220px, 2fr) minmax(180px, 1fr) 150px 110px;
      gap: 10px; padding: 12px; border-bottom: 1px solid var(--line);
    }
    input, select {
      width: 100%; height: 36px; border: 1px solid #bfc8d1; border-radius: 4px;
      background: white; color: var(--ink); padding: 0 10px;
    }
    input:focus, select:focus, button:focus-visible { outline: 2px solid #2b8a6e; outline-offset: 1px; }
    .table-wrap { overflow: auto; min-height: 410px; }
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
    .badge.done { color: #176b4d; background: var(--accent-soft); }
    .badge.pending { color: var(--warning); background: #fff0db; }
    .badge.error { color: var(--danger); background: #fee4e2; }
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
    .error-banner {
      display: none; padding: 10px 12px; color: #7a271a; background: #ffebe9;
      border-bottom: 1px solid #f7b8b3;
    }
    @media (max-width: 1000px) {
      .metrics { grid-template-columns: repeat(4, 1fr); }
      .metric:nth-child(4) { border-right: 0; }
      .metric:nth-child(-n+4) { border-bottom: 1px solid var(--line); }
      .filters { grid-template-columns: 1fr 1fr; }
    }
    @media (max-width: 650px) {
      header { padding: 10px 14px; align-items: flex-start; }
      .brand { display: block; }
      .run-state { display: block; margin-top: 4px; }
      .refresh-meta span { display: none; }
      main { padding: 12px; }
      .metrics { grid-template-columns: repeat(2, 1fr); }
      .metric:nth-child(2n) { border-right: 0; }
      .metric { border-bottom: 1px solid var(--line); }
      .metric:nth-last-child(-n+2) { border-bottom: 0; }
      .filters { grid-template-columns: 1fr; }
      .table-wrap { min-height: 360px; }
      table { min-width: 780px; }
    }
  </style>
</head>
<body>
  <header>
    <div class="brand">
      <h1>GEDS Snapshot Monitor</h1>
      <span id="run-state" class="run-state">Connecting...</span>
    </div>
    <div class="refresh-meta">
      <span id="last-refresh">Waiting for data</span>
      <button id="refresh" class="header-button" type="button">Refresh</button>
    </div>
  </header>
  <main>
    <section class="metrics" aria-label="Crawl metrics">
      <div class="metric"><span class="metric-label">Requests</span><strong id="m-requests" class="metric-value">-</strong></div>
      <div class="metric"><span class="metric-label">Departments</span><strong id="m-departments" class="metric-value">-</strong></div>
      <div class="metric"><span class="metric-label">Org units</span><strong id="m-orgs" class="metric-value">-</strong></div>
      <div class="metric"><span class="metric-label">People</span><strong id="m-people" class="metric-value">-</strong></div>
      <div class="metric"><span class="metric-label">Completed</span><strong id="m-done" class="metric-value">-</strong></div>
      <div class="metric"><span class="metric-label">Pending</span><strong id="m-pending" class="metric-value">-</strong></div>
      <div class="metric"><span class="metric-label">Queue errors</span><strong id="m-qerrors" class="metric-value">-</strong></div>
      <div class="metric"><span class="metric-label">Crawl errors</span><strong id="m-errors" class="metric-value">-</strong></div>
    </section>
    <div class="progress-wrap">
      <div class="progress" aria-label="Queue completion"><div id="progress-bar"></div></div>
      <span id="progress-label" class="progress-label">0%</span>
    </div>

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
  </main>
  <script>
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
    const state = { view: "orgs", offset: 0, total: 0, loading: false };
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

    async function refresh() {
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
      refresh();
    }

    document.querySelectorAll(".tab").forEach(tab => tab.addEventListener("click", () => setView(tab.dataset.view)));
    el("refresh").addEventListener("click", refresh);
    el("search").addEventListener("input", () => { state.offset = 0; clearTimeout(window.searchTimer); window.searchTimer = setTimeout(refresh, 250); });
    ["department", "queue-status", "page-size"].forEach(id => el(id).addEventListener("change", () => { state.offset = 0; refresh(); }));
    el("previous").addEventListener("click", () => { state.offset = Math.max(0, state.offset - Number(el("page-size").value)); refresh(); });
    el("next").addEventListener("click", () => { state.offset += Number(el("page-size").value); refresh(); });

    refresh();
    setInterval(refresh, 3000);
  </script>
</body>
</html>
"""
