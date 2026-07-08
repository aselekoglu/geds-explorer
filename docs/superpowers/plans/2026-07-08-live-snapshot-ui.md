# GEDS Live Snapshot UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local read-only, auto-refreshing web UI for monitoring and browsing a running GEDS SQLite snapshot.

**Architecture:** Add a focused query module for safe read-only SQLite access and an HTTP module for JSON endpoints plus a self-contained dashboard page. Extend the existing CLI with a `ui` subcommand that validates the database and starts a loopback-only standard-library server.

**Tech Stack:** Python 3.11 standard library, SQLite, vanilla HTML/CSS/JavaScript, pytest.

## Global Constraints

- Add no runtime dependency.
- Bind to `0.0.0.0` by default and print loopback plus detected LAN URLs.
- Open SQLite with URI `mode=ro` and `PRAGMA query_only=ON`.
- Never return phone, email, or arbitrary contact fields.
- Preserve official GEDS source URLs.
- Refresh visible data every three seconds.

---

### Task 1: Read-Only Snapshot Queries

**Files:**
- Create: `work/geds-crawler/src/geds_crawler/ui_queries.py`
- Create: `work/geds-crawler/tests/test_ui_queries.py`

**Interfaces:**
- Produces: `SnapshotReader(db_path)`, `status()`, `departments()`, `orgs(...)`, `people(...)`, `queue(...)`, and `errors(...)`.

- [ ] **Step 1: Write failing tests**

Create a temporary snapshot with `SnapshotStore`, insert representative department, org, person, queue, run, and error rows, then assert:

```python
with SnapshotReader(db_path) as reader:
    assert reader.status()["people"] == 1
    assert reader.people(query="developer", department="Shared Services Canada", limit=25, offset=0)["total"] == 1
    assert set(reader.people(limit=25, offset=0)["items"][0]) == {
        "display_name", "title", "department_name", "org_unit", "org_path", "source_url"
    }
```

- [ ] **Step 2: Verify RED**

Run: `py -m pytest tests/test_ui_queries.py -q`

Expected: collection fails because `geds_crawler.ui_queries` does not exist.

- [ ] **Step 3: Implement bounded parameterized queries**

Implement short-lived read-only connections, fixed column projections, escaped `LIKE` search, department/status filtering, deterministic ordering, and `limit` clamped to `1..100`.

- [ ] **Step 4: Verify GREEN**

Run: `py -m pytest tests/test_ui_queries.py -q`

Expected: all query tests pass.

### Task 2: HTTP API and Dashboard

**Files:**
- Create: `work/geds-crawler/src/geds_crawler/ui_server.py`
- Create: `work/geds-crawler/tests/test_ui_server.py`

**Interfaces:**
- Consumes: `SnapshotReader`.
- Produces: `create_server(db_path, host, port)` and HTTP routes from the design.

- [ ] **Step 1: Write failing endpoint tests**

Start the server on port `0` in a test thread and use `urllib.request.urlopen` to assert:

```python
status = get_json("/api/status")
assert status["people"] == 1
people = get_json("/api/people?q=developer")
assert "email" not in json.dumps(people).lower()
assert get_text("/").startswith("<!doctype html>")
```

- [ ] **Step 2: Verify RED**

Run: `py -m pytest tests/test_ui_server.py -q`

Expected: collection fails because `geds_crawler.ui_server` does not exist.

- [ ] **Step 3: Implement server and page**

Implement the fixed route map, structured JSON errors, query parsing, and a responsive dashboard page with metric strip, tabs, filters, paginated tables, source-link actions, three-second refresh, loading, empty, and error states.

- [ ] **Step 4: Verify GREEN**

Run: `py -m pytest tests/test_ui_server.py -q`

Expected: all endpoint and HTML tests pass.

### Task 3: CLI Integration and Documentation

**Files:**
- Modify: `work/geds-crawler/src/geds_crawler/cli.py`
- Modify: `work/geds-crawler/README.md`
- Create: `work/geds-crawler/tests/test_ui_cli.py`

**Interfaces:**
- Consumes: `create_server`.
- Produces: `ui --db PATH [--host 0.0.0.0] [--port 8765]`.

- [ ] **Step 1: Write failing CLI tests**

Patch `create_server` with a test server object and assert that `main(["ui", "--db", str(db_path), "--port", "9000"])` validates the path and calls `serve_forever`. Assert a missing path returns exit code `2`.

- [ ] **Step 2: Verify RED**

Run: `py -m pytest tests/test_ui_cli.py -q`

Expected: parser rejects the unknown `ui` command.

- [ ] **Step 3: Implement CLI command and usage docs**

Add CLI arguments, concise startup output, clean `Ctrl+C` shutdown, and README commands for repository-root and crawler-directory execution.

- [ ] **Step 4: Verify GREEN and regression suite**

Run: `py -m pytest -q`

Expected: all tests pass.

### Task 4: Live Snapshot Verification

**Files:**
- No production file changes expected.

- [ ] **Step 1: Start UI against the active snapshot**

Run from `work/geds-crawler`:

```powershell
py -m geds_crawler.cli ui --db ..\..\outputs\geds-snapshot-2026-07-08\geds.sqlite
```

Expected: startup prints `http://127.0.0.1:8765`.

- [ ] **Step 2: Verify live endpoints**

Request `/api/status`, `/api/orgs?limit=5`, and `/api/people?limit=5`; confirm HTTP 200, increasing crawl counts where applicable, valid official source URLs, and no contact fields.

- [ ] **Step 3: Verify the rendered UI**

Open the local URL and confirm all tabs render, filters work, pagination is stable, and automatic refresh does not reset the selected tab.
