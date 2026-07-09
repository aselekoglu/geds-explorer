# GEDS UI Overhaul Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the GEDS local control-plane UI into a clear Command Center Rail experience while preserving existing crawler, coverage, schedule, run history, and snapshot-data functionality.

**Architecture:** Keep the existing standard-library HTTP server and vanilla HTML/CSS/JS model. Refactor the single dashboard surface inside `work/geds-crawler/src/geds_crawler/ui_server.py` into clearer client-side UI sections, hash-routed workspaces, guided drawers, and isolated state buckets without changing the current API contract. Add focused server-rendered HTML tests that lock the new IA, accessibility hooks, and legacy API references before changing the UI.

**Tech Stack:** Python standard-library HTTP server, SQLite-backed GEDS crawler stores, vanilla HTML, CSS, JavaScript, pytest, optional local Playwright/browser smoke testing.

## Global Constraints

- Preserve existing API endpoints.
- Preserve existing crawler, coverage, schedule, run history, and snapshot inspection functionality.
- Do not perform a large framework migration.
- Do not replace the backend.
- Do not remove existing functionality.
- Preserve the current visible unauthenticated-local warning.
- Active DB, snapshot metrics, and table browsing must be visually centered in Explore Data, not Operate or Plan.
- Start Crawler must work as a guided flow rather than a large always-visible form.
- Coverage must default to problem-oriented scanning while preserving access to the full table.
- Schedules must show next-run context and treat cron as advanced configuration.
- Desktop and mobile layouts must not overlap or clip.
- Keyboard focus must be visible.
- Status labels must not rely on color alone.

---

## File Structure

- Modify `work/geds-crawler/tests/test_ui_server.py`
  - Adds HTML contract tests for the new Command Center Rail IA, hash routes, guided flow containers, accessibility attributes, and preservation of existing API/script references.
- Modify `work/geds-crawler/src/geds_crawler/ui_server.py`
  - Keeps `create_server()` and API handlers unchanged except for any minimal UI-support fields that prove necessary.
  - Replaces the current tab-heavy dashboard markup with a left-rail app shell.
  - Replaces current mixed CSS with reusable surface, rail, status, table, drawer, responsive, and focus classes.
  - Refactors client-side JS state into global, operate, plan, and explore buckets.
  - Preserves current functions and API calls where possible: `getJson`, `postJson`, `deleteJson`, `refreshControl`, `refreshJobs`, `refreshRuns`, `refreshCoverage`, `refreshSchedules`, legacy snapshot refresh functions, stop/resume/delete schedule actions, and pagination org inspection.
- Optional modify `docs/ux-audit/README.md`
  - Only if implementation changes invalidate audit notes; otherwise leave it unchanged.

No new frontend framework, package manager dependency, or build step is introduced.

---

### Task 1: Lock the new UI contract with failing tests

**Files:**
- Modify: `work/geds-crawler/tests/test_ui_server.py`
- Test: `work/geds-crawler/tests/test_ui_server.py`

**Interfaces:**
- Consumes: `create_server(db_path, host, port)` from `geds_crawler.ui_server`.
- Produces: HTML contract tests that later tasks must satisfy.

- [ ] **Step 1: Add a helper for root HTML**

Add this helper after `_get_json` in `work/geds-crawler/tests/test_ui_server.py`:

```python
def _get_root_html(base_url: str) -> str:
    with urlopen(f"{base_url}/", timeout=2) as response:
        assert response.status == 200
        return response.read().decode("utf-8")
```

- [ ] **Step 2: Update existing root HTML tests to use the helper**

Replace the body-fetching code in `test_root_serves_dashboard_html` with:

```python
def test_root_serves_dashboard_html(running_server):
    body = _get_root_html(running_server)

    assert body.lower().startswith("<!doctype html>")
    assert "GEDS" in body
    assert "/api/status" in body
```

Replace the body-fetching code in `test_dashboard_contains_pagination_elements` with:

```python
def test_dashboard_contains_pagination_elements(running_server):
    body = _get_root_html(running_server)
    assert "job-crawl-kind" in body
    assert "job-source-db" in body
    assert "pagination-orgs-panel" in body
    assert "formatDurationRange" in body
    assert "formatRunEta" in body
    assert "pagination_metrics.known_pending_pages" in body
    assert "pagination_metrics.active_org" in body
    assert "pagination_metrics.pages_pending" not in body
```

- [ ] **Step 3: Add IA and routing contract test**

Add this test after `test_root_serves_dashboard_html`:

```python
def test_dashboard_uses_command_center_information_architecture(running_server):
    body = _get_root_html(running_server)

    assert 'class="app-shell"' in body
    assert 'aria-label="Primary workspace navigation"' in body
    assert 'data-route="#/operate/overview"' in body
    assert 'data-route="#/operate/crawlers"' in body
    assert 'data-route="#/operate/history"' in body
    assert 'data-route="#/plan/coverage"' in body
    assert 'data-route="#/plan/schedules"' in body
    assert 'data-route="#/explore/snapshot"' in body
    assert "Operate" in body
    assert "Plan" in body
    assert "Explore Data" in body
```

- [ ] **Step 4: Add guided crawler and schedule flow contract test**

Add this test:

```python
def test_dashboard_contains_guided_creation_flows(running_server):
    body = _get_root_html(running_server)

    assert 'id="start-crawler-drawer"' in body
    assert 'aria-modal="true"' in body
    assert 'id="open-start-crawler"' in body
    assert "Select target" in body
    assert "Review estimate" in body
    assert "Configure options" in body
    assert "Confirm start" in body
    assert 'id="new-schedule-drawer"' in body
    assert 'id="open-new-schedule"' in body
    assert "Advanced cron" in body
    assert "Next run preview" in body
```

- [ ] **Step 5: Add Explore Data isolation contract test**

Add this test:

```python
def test_dashboard_isolates_snapshot_data_in_explore_workspace(running_server):
    body = _get_root_html(running_server)

    explore_index = body.index('id="workspace-explore-snapshot"')
    legacy_metrics_index = body.index('id="legacy-metrics-section"')
    active_db_index = body.index('id="active-db"')

    assert explore_index < legacy_metrics_index
    assert explore_index < active_db_index
    assert 'id="workspace-operate-overview"' in body
    overview_chunk = body[
        body.index('id="workspace-operate-overview"') : body.index('id="workspace-operate-crawlers"')
    ]
    assert 'id="active-db"' not in overview_chunk
```

- [ ] **Step 6: Add accessibility and responsive hook contract test**

Add this test:

```python
def test_dashboard_has_accessibility_and_responsive_hooks(running_server):
    body = _get_root_html(running_server)

    assert ":focus-visible" in body
    assert "@media (max-width: 760px)" in body
    assert 'id="mobile-nav-toggle"' in body
    assert 'aria-expanded="false"' in body
    assert 'role="status"' in body
    assert 'aria-live="polite"' in body
    assert "status-label" in body
```

- [ ] **Step 7: Run the new tests and verify they fail**

Run:

```powershell
py -m pytest work\geds-crawler\tests\test_ui_server.py -q
```

Expected: FAIL with missing strings such as `class="app-shell"` or `id="start-crawler-drawer"`.

- [ ] **Step 8: Commit the failing UI contract tests**

Run:

```powershell
git -c safe.directory='C:/Users/asele/Documents/geds-explorer' add -- work/geds-crawler/tests/test_ui_server.py
git -c safe.directory='C:/Users/asele/Documents/geds-explorer' commit -m "test: lock geds ui overhaul contract"
```

Expected: commit succeeds and includes only `test_ui_server.py`.

---

### Task 2: Build the Command Center app shell and visual system

**Files:**
- Modify: `work/geds-crawler/src/geds_crawler/ui_server.py`
- Test: `work/geds-crawler/tests/test_ui_server.py`

**Interfaces:**
- Consumes: HTML contract tests from Task 1.
- Produces:
  - `.app-shell`
  - `.sidebar`
  - `[data-route]` navigation buttons
  - workspace containers named `workspace-operate-overview`, `workspace-operate-crawlers`, `workspace-operate-history`, `workspace-plan-coverage`, `workspace-plan-schedules`, `workspace-explore-snapshot`
  - reusable CSS variables and focus/responsive hooks.

- [ ] **Step 1: Replace the top-level dashboard shell markup**

In `DASHBOARD_HTML` in `work/geds-crawler/src/geds_crawler/ui_server.py`, replace the old header/nav wrapper beginning at the first `<div class="warning-banner">` and ending before the first current tab content with this app shell skeleton. Keep existing content blocks nearby so later steps can move them into the new workspaces.

```html
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

      <section class="workspace-panel active" id="workspace-operate-overview" data-workspace="#/operate/overview"></section>
      <section class="workspace-panel" id="workspace-operate-crawlers" data-workspace="#/operate/crawlers"></section>
      <section class="workspace-panel" id="workspace-operate-history" data-workspace="#/operate/history"></section>
      <section class="workspace-panel" id="workspace-plan-coverage" data-workspace="#/plan/coverage"></section>
      <section class="workspace-panel" id="workspace-plan-schedules" data-workspace="#/plan/schedules"></section>
      <section class="workspace-panel" id="workspace-explore-snapshot" data-workspace="#/explore/snapshot"></section>
    </main>
  </div>
```

- [ ] **Step 2: Replace old tab CSS with visual-system CSS**

Inside the `<style>` block, add these classes near the existing root variables. Keep existing table, badge, button, progress, and form classes until later tasks finish moving content.

```css
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

    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      background: radial-gradient(circle at top left, rgba(16, 185, 129, 0.12), transparent 32rem), var(--bg-deep);
      color: var(--text);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    button, input, select { font: inherit; }
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
```

- [ ] **Step 3: Add route metadata in JavaScript**

Near the start of the dashboard `<script>`, add this route map:

```javascript
    const routes = {
      "#/operate/overview": {
        title: "Operate",
        description: "Live crawler status, attention items, and next actions.",
        refresh: () => Promise.all([refreshControl(), refreshRuns(), refreshSchedules()])
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
```

- [ ] **Step 4: Add route activation functions**

Add these functions after `const routes = ...`:

```javascript
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
      document.body.classList.remove("nav-open");
      const navToggle = el("mobile-nav-toggle");
      if (navToggle) navToggle.setAttribute("aria-expanded", "false");
    }

    async function refreshCurrentRoute() {
      const route = currentRoute();
      activateRoute(route);
      await routes[route].refresh();
    }
```

- [ ] **Step 5: Wire navigation controls**

In the `DOMContentLoaded` or bottom-of-script initialization area, add:

```javascript
    document.querySelectorAll("[data-route]").forEach(button => {
      button.addEventListener("click", () => {
        window.location.hash = button.dataset.route;
      });
    });

    window.addEventListener("hashchange", () => {
      refreshCurrentRoute().catch(showError);
    });

    el("mobile-nav-toggle").addEventListener("click", () => {
      const open = !document.body.classList.contains("nav-open");
      document.body.classList.toggle("nav-open", open);
      el("mobile-nav-toggle").setAttribute("aria-expanded", String(open));
    });
```

- [ ] **Step 6: Update refresh button behavior**

Replace the old refresh button event handler with:

```javascript
    el("refresh").addEventListener("click", () => {
      refreshCurrentRoute().catch(showError);
    });
```

- [ ] **Step 7: Run the UI server tests**

Run:

```powershell
py -m pytest work\geds-crawler\tests\test_ui_server.py -q
```

Expected: Task 1 IA/focus/mobile assertions should now pass; content-specific guided-flow assertions may still fail until later tasks.

- [ ] **Step 8: Commit the app shell**

Run:

```powershell
git -c safe.directory='C:/Users/asele/Documents/geds-explorer' add -- work/geds-crawler/src/geds_crawler/ui_server.py
git -c safe.directory='C:/Users/asele/Documents/geds-explorer' commit -m "feat: add geds command center app shell"
```

Expected: commit includes only `ui_server.py`.

---

### Task 3: Rebuild Operate overview, crawler workspace, and run history

**Files:**
- Modify: `work/geds-crawler/src/geds_crawler/ui_server.py`
- Test: `work/geds-crawler/tests/test_ui_server.py`

**Interfaces:**
- Consumes:
  - `routes` and `activateRoute(route)` from Task 2.
  - Existing APIs `/api/control/overview`, `/api/control/jobs`, `/api/control/runs`, `/api/control/catalog`, `/api/control/coverage`, `/api/control/estimates`.
- Produces:
  - `renderAttentionQueue(data)`
  - `renderLiveActivity(runs)`
  - `openDrawer(drawerId)` and `closeDrawer(drawerId)`
  - guided crawler drawer with existing form fields preserved.

- [ ] **Step 1: Fill the Overview workspace markup**

Set `workspace-operate-overview` content to:

```html
        <div class="status-grid">
          <article class="panel-card metric-card">
            <span class="metric-label">Active crawlers</span>
            <strong id="ctrl-m-workers" class="metric-value">0</strong>
            <span class="status-label running">Running workers</span>
          </article>
          <article class="panel-card metric-card">
            <span class="metric-label">Configured RPS</span>
            <strong id="ctrl-m-conf-rps" class="metric-value">0.0</strong>
            <span class="status-label info">Configured</span>
          </article>
          <article class="panel-card metric-card">
            <span class="metric-label">Measured RPS</span>
            <strong id="ctrl-m-meas-rps" class="metric-value">0.0</strong>
            <span id="rps-health-label" class="status-label healthy">Healthy</span>
          </article>
          <article class="panel-card metric-card">
            <span class="metric-label">Cataloged departments</span>
            <strong id="ctrl-m-depts" class="metric-value">0</strong>
            <span class="status-label info">Coverage base</span>
          </article>
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

        <div class="command-grid">
          <section class="panel-card">
            <h2 class="panel-title">Coverage Summary</h2>
            <div class="summary-row">
              <span>Covered <strong id="coverage-covered-count">0</strong></span>
              <span>Missing <strong id="coverage-missing-count">0</strong></span>
              <span>Overlap <strong id="coverage-overlap-count">0</strong></span>
              <span>Stale <strong id="coverage-stale-count">0</strong></span>
            </div>
          </section>
          <section class="panel-card">
            <h2 class="panel-title">Next Schedules</h2>
            <div id="next-schedules-list" class="activity-list">
              <div class="empty">No schedules loaded yet.</div>
            </div>
          </section>
        </div>
```

- [ ] **Step 2: Add CSS for overview grids**

Add:

```css
    .status-grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 14px;
      margin-bottom: 16px;
    }
    .metric-card { display: grid; gap: 8px; }
    .metric-label { color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: 0.08em; }
    .metric-value { font-size: clamp(26px, 4vw, 38px); line-height: 1; }
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
    .attention-item strong, .activity-item strong { display: block; }
    .summary-row {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
    }
    .summary-row span {
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 12px;
      color: var(--muted);
    }
    .summary-row strong { display: block; color: var(--text); font-size: 24px; margin-top: 6px; }
    @media (max-width: 980px) {
      .status-grid, .command-grid, .summary-row { grid-template-columns: 1fr; }
    }
```

- [ ] **Step 3: Fill Crawlers workspace markup**

Move the existing crawler form fields into a drawer while preserving IDs. Set `workspace-operate-crawlers` content to:

```html
        <div class="workspace-header-row">
          <div>
            <h2 class="section-title">Crawlers</h2>
            <p class="panel-subtitle">Monitor active runs and start focused crawler work.</p>
          </div>
          <button id="open-start-crawler" class="btn btn-primary" type="button">Start crawler</button>
        </div>

        <section class="panel-card">
          <h3 class="panel-title">Active Runs</h3>
          <div class="table-wrap">
            <table class="responsive-table">
              <thead>
                <tr><th>Run</th><th>Status</th><th>Progress</th><th>Rate</th><th>Heartbeat</th><th>Action</th></tr>
              </thead>
              <tbody id="runs-table-body"><tr><td colspan="6" class="empty">Loading runs...</td></tr></tbody>
            </table>
          </div>
        </section>

        <section id="pagination-orgs-panel" class="panel-card" style="display:none; margin-top:16px;">
          <div class="workspace-header-row">
            <div>
              <h3 class="panel-title">Pagination Organizations</h3>
              <p class="panel-subtitle">Inspect organization-level pagination backfill status.</p>
            </div>
            <button type="button" class="btn" onclick="hidePaginationOrgsPanel()">Close Panel</button>
          </div>
          <div class="filters compact-filters">
            <input id="pag-filter-q" placeholder="Search organization" />
            <select id="pag-filter-status">
              <option value="">All statuses</option>
              <option value="pending">Pending</option>
              <option value="active">Active</option>
              <option value="done">Done</option>
              <option value="failed">Failed</option>
            </select>
            <button class="btn" type="button" onclick="refreshPaginationOrgs()">Apply</button>
          </div>
          <div class="table-wrap">
            <table class="responsive-table">
              <thead>
                <tr><th>Organization</th><th>Status</th><th>Known pages</th><th>Fetched</th><th>Last URL</th><th>Failure</th><th>Action</th></tr>
              </thead>
              <tbody id="pagination-orgs-body">
                <tr><td colspan="7" class="empty">No data loaded.</td></tr>
              </tbody>
            </table>
          </div>
          <div class="footer">
            <span id="pag-result-count" class="muted">No rows loaded</span>
            <div class="pager">
              <button id="pag-prev" class="btn" type="button">Previous</button>
              <button id="pag-next" class="btn" type="button">Next</button>
            </div>
          </div>
        </section>
```

- [ ] **Step 4: Add the Start Crawler drawer markup**

Place this after `.app-shell` but before `<script>`:

```html
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
    <form id="new-job-form" class="drawer-body">
      <div class="form-grid">
        <div class="form-group">
          <label for="job-name">Job name</label>
          <input id="job-name" name="name" value="Manual crawl" />
        </div>
        <div class="form-group">
          <label for="job-crawl-kind">Crawl kind</label>
          <select id="job-crawl-kind" name="crawl_kind">
            <option value="department">Department crawl</option>
            <option value="pagination_backfill">Pagination backfill</option>
          </select>
        </div>
        <div class="form-group">
          <label for="job-rps">Requests per second</label>
          <input id="job-rps" name="rps" type="number" min="0.1" step="0.1" value="1.0" />
        </div>
        <div class="form-group">
          <label for="job-worker-count">Workers</label>
          <input id="job-worker-count" name="worker_count" type="number" min="1" step="1" value="1" />
        </div>
        <div class="form-group" id="source-db-container" style="display:none;">
          <label for="job-source-db">Source DB</label>
          <select id="job-source-db" name="source_db"></select>
        </div>
      </div>

      <div class="form-group" id="dept-selection-container">
        <div class="workspace-header-row">
          <label for="department-search">Department picker</label>
          <div class="button-row">
            <button type="button" class="btn" onclick="deptSelectUncrawled()">Select Uncrawled</button>
            <button type="button" class="btn" onclick="deptSelectOutdated()">Select Outdated (&gt;7d)</button>
            <button type="button" class="btn" onclick="deptSelectAll()">Select All</button>
            <button type="button" class="btn" onclick="deptClearAll()">Clear</button>
          </div>
        </div>
        <input id="department-search" placeholder="Search departments" />
        <div id="department-options" class="checkbox-list"></div>
      </div>

      <section class="estimate-panel">
        <h3>Review estimate</h3>
        <div class="summary-row">
          <span>Selected <strong id="est-selected">0</strong></span>
          <span>Requests <strong id="est-requests">0</strong></span>
          <span>Duration <strong id="est-duration">0m</strong></span>
          <span>People <strong id="est-people">0</strong></span>
        </div>
        <p class="muted">Estimated DB size: <span id="est-size">0 MB</span></p>
      </section>

      <div class="drawer-footer">
        <button type="button" class="btn" data-close-drawer="start-crawler-drawer">Cancel</button>
        <button type="submit" class="btn btn-primary">Create and Start Job</button>
      </div>
    </form>
  </aside>
```

- [ ] **Step 5: Fill Run History workspace markup**

Set `workspace-operate-history` content to:

```html
        <section class="panel-card">
          <h2 class="panel-title">Run History</h2>
          <p class="panel-subtitle">Completed, stopped, failed, and historical crawler runs.</p>
          <div class="filters compact-filters">
            <input id="run-history-filter" placeholder="Search run id or job" />
            <select id="run-history-status">
              <option value="">All statuses</option>
              <option value="running">Running</option>
              <option value="finished">Finished</option>
              <option value="failed">Failed</option>
              <option value="stopped">Stopped</option>
            </select>
          </div>
          <div class="table-wrap">
            <table class="responsive-table">
              <thead>
                <tr><th>Run</th><th>Status</th><th>Started</th><th>Finished</th><th>Progress</th><th>Action</th></tr>
              </thead>
              <tbody id="run-history-table-body"><tr><td colspan="6" class="empty">Loading run history...</td></tr></tbody>
            </table>
          </div>
        </section>
```

- [ ] **Step 6: Add drawer CSS**

Add:

```css
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
    .drawer-header, .drawer-footer, .workspace-header-row {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 16px;
    }
    .drawer-body { display: grid; gap: 18px; margin-top: 18px; }
    .drawer-footer {
      position: sticky;
      bottom: 0;
      background: linear-gradient(180deg, rgba(17, 28, 45, 0), var(--surface) 28%);
      padding-top: 18px;
      justify-content: flex-end;
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
    .checkbox-list {
      max-height: 280px;
      overflow: auto;
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 10px;
      margin-top: 8px;
      display: grid;
      gap: 6px;
    }
    .button-row { display: flex; gap: 8px; flex-wrap: wrap; }
    .estimate-panel {
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 14px;
      background: rgba(8, 17, 31, 0.5);
    }
```

- [ ] **Step 7: Add drawer JavaScript**

Add:

```javascript
    let lastFocusedElement = null;

    function openDrawer(drawerId) {
      const drawer = el(drawerId);
      const backdrop = el(drawerId.replace("-drawer", "-backdrop"));
      lastFocusedElement = document.activeElement;
      drawer.hidden = false;
      if (backdrop) backdrop.hidden = false;
      const firstInput = drawer.querySelector("button, input, select, textarea");
      if (firstInput) firstInput.focus();
    }

    function closeDrawer(drawerId) {
      const drawer = el(drawerId);
      const backdrop = el(drawerId.replace("-drawer", "-backdrop"));
      drawer.hidden = true;
      if (backdrop) backdrop.hidden = true;
      if (lastFocusedElement && typeof lastFocusedElement.focus === "function") {
        lastFocusedElement.focus();
      }
    }
```

Add event wiring:

```javascript
    el("open-start-crawler").addEventListener("click", () => openDrawer("start-crawler-drawer"));
    document.querySelectorAll("[data-close-drawer]").forEach(button => {
      button.addEventListener("click", () => closeDrawer(button.dataset.closeDrawer));
    });
    document.addEventListener("keydown", event => {
      if (event.key === "Escape") {
        document.querySelectorAll(".drawer:not([hidden])").forEach(drawer => closeDrawer(drawer.id));
      }
    });
```

- [ ] **Step 8: Refactor run rendering for overview and history**

Update `refreshRuns()` so it renders active runs and history separately:

```javascript
    async function refreshRuns() {
      const runs = await getJson("/api/control/runs");
      renderActiveRuns(runs);
      renderRunHistory(runs);
      renderLiveActivity(runs);
    }
```

Add:

```javascript
    function renderLiveActivity(runs) {
      const active = runs.filter(run => ["running", "starting", "stopping"].includes(run.status));
      const list = el("live-activity-list");
      if (!list) return;
      if (!active.length) {
        list.innerHTML = '<div class="empty">No active crawlers right now.</div>';
        return;
      }
      list.innerHTML = active.map(run => `
        <div class="activity-item">
          <strong>${escapeHtml(run.id)}</strong>
          <span class="status-label ${escapeHtml(run.status)}">${escapeHtml(run.status)}</span>
          <span class="muted">RPS ${(run.measured_rps || 0).toFixed(2)} / ${(run.configured_rps || 0).toFixed(1)}</span>
        </div>
      `).join("");
    }
```

Keep the existing detailed row logic inside a new `renderActiveRuns(runs)` function. In each `<td>`, add `data-label`, for example:

```javascript
    function runStatusCell(run) {
      return `<span class="status-label ${escapeHtml(run.status)}">${escapeHtml(run.status)}</span>`;
    }
```

- [ ] **Step 9: Render attention queue**

At the end of `refreshControl()`, call:

```javascript
      renderAttentionQueue(data);
```

Add:

```javascript
    function renderAttentionQueue(data) {
      const items = [];
      if ((data.active_workers || 0) === 0) {
        items.push({ level: "attention", title: "No active crawlers", detail: "Start a crawler if coverage needs to be refreshed." });
      }
      if ((data.measured_rps || 0) < (data.configured_rps || 0) * 0.5 && (data.configured_rps || 0) > 0) {
        items.push({ level: "attention", title: "Measured RPS is low", detail: "Throughput is below half of configured RPS." });
      }
      const list = el("attention-list");
      if (!list) return;
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
```

- [ ] **Step 10: Run tests**

Run:

```powershell
py -m pytest work\geds-crawler\tests\test_ui_server.py -q
```

Expected: PASS for Task 1 contract tests except any plan/schedule/explore-specific assertions not yet implemented.

- [ ] **Step 11: Commit Operate workspace**

Run:

```powershell
git -c safe.directory='C:/Users/asele/Documents/geds-explorer' add -- work/geds-crawler/src/geds_crawler/ui_server.py
git -c safe.directory='C:/Users/asele/Documents/geds-explorer' commit -m "feat: rebuild geds operate workspace"
```

Expected: commit includes only `ui_server.py`.

---

### Task 4: Rebuild Plan coverage and schedules workspaces

**Files:**
- Modify: `work/geds-crawler/src/geds_crawler/ui_server.py`
- Test: `work/geds-crawler/tests/test_ui_server.py`

**Interfaces:**
- Consumes:
  - Existing `/api/control/coverage`, `/api/control/catalog`, `/api/control/schedules`, `/api/control/jobs`.
  - `openDrawer(drawerId)` and `closeDrawer(drawerId)` from Task 3.
- Produces:
  - coverage summary cards and filter chips
  - `coverageFilter` state
  - `renderCoverageRows(rows)`
  - schedule drawer with advanced cron section
  - next-run preview text container

- [ ] **Step 1: Fill Coverage workspace markup**

Set `workspace-plan-coverage` content to:

```html
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
            <button class="chip" type="button" data-coverage-filter="attention">Needs attention</button>
            <button class="chip" type="button" data-coverage-filter="all">All</button>
            <button class="chip" type="button" data-coverage-filter="missing">Missing</button>
            <button class="chip" type="button" data-coverage-filter="overlap">Overlap</button>
            <button class="chip" type="button" data-coverage-filter="stale">Stale</button>
          </div>
          <div class="table-wrap">
            <table class="responsive-table">
              <thead>
                <tr><th>Department</th><th>Status</th><th>Last crawl</th><th>Source</th><th>Action</th></tr>
              </thead>
              <tbody id="coverage-table-body"></tbody>
            </table>
          </div>
        </section>
```

- [ ] **Step 2: Fill Schedules workspace markup**

Set `workspace-plan-schedules` content to:

```html
        <div class="workspace-header-row">
          <div>
            <h2 class="section-title">Schedules</h2>
            <p class="panel-subtitle">Recurring crawler work with next-run context.</p>
          </div>
          <button id="open-new-schedule" class="btn btn-primary" type="button">New schedule</button>
        </div>
        <section class="panel-card">
          <h3 class="panel-title">Schedule List</h3>
          <div class="table-wrap">
            <table class="responsive-table">
              <thead>
                <tr><th>Job</th><th>Status</th><th>Cron</th><th>Next run</th><th>Overlap</th><th>Action</th></tr>
              </thead>
              <tbody id="schedules-table-body">
                <tr><td colspan="6" class="empty">Loading schedules...</td></tr>
              </tbody>
            </table>
          </div>
        </section>
```

- [ ] **Step 3: Add New Schedule drawer markup**

Place after the Start Crawler drawer:

```html
  <div class="drawer-backdrop" id="new-schedule-backdrop" hidden></div>
  <aside class="drawer" id="new-schedule-drawer" role="dialog" aria-modal="true" aria-labelledby="new-schedule-title" hidden>
    <div class="drawer-header">
      <div>
        <p class="eyebrow">Guided flow</p>
        <h2 id="new-schedule-title">New schedule</h2>
      </div>
      <button class="btn" type="button" data-close-drawer="new-schedule-drawer">Close</button>
    </div>
    <form id="new-schedule-form" class="drawer-body">
      <div class="form-group">
        <label for="schedule-job-id">Target job</label>
        <select id="schedule-job-id" name="job_id"></select>
      </div>
      <div class="form-group">
        <label for="schedule-cadence">Cadence</label>
        <select id="schedule-cadence">
          <option value="0 5 * * *">Daily at 05:00</option>
          <option value="0 5 * * 1">Weekly Monday 05:00</option>
          <option value="0 */6 * * *">Every 6 hours</option>
          <option value="advanced">Advanced cron</option>
        </select>
      </div>
      <div class="form-group" id="advanced-cron-panel" hidden>
        <label for="schedule-expression">Advanced cron</label>
        <input id="schedule-expression" name="expression" value="0 5 * * *" />
      </div>
      <div class="form-group">
        <label for="schedule-timezone">Timezone</label>
        <input id="schedule-timezone" name="timezone" value="America/Toronto" />
      </div>
      <div class="form-group">
        <label for="schedule-overlap-policy">Overlap policy</label>
        <select id="schedule-overlap-policy" name="overlap_policy">
          <option value="skip">Skip if running</option>
          <option value="queue">Queue next run</option>
        </select>
      </div>
      <section class="estimate-panel">
        <h3>Next run preview</h3>
        <p id="schedule-next-preview" class="muted">Next run preview updates after cadence selection.</p>
      </section>
      <div class="drawer-footer">
        <button type="button" class="btn" data-close-drawer="new-schedule-drawer">Cancel</button>
        <button type="submit" class="btn btn-primary">Create Schedule</button>
      </div>
    </form>
  </aside>
```

- [ ] **Step 4: Add coverage filter CSS**

Add:

```css
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
```

- [ ] **Step 5: Add plan state and coverage filter behavior**

Near other state declarations, add:

```javascript
    const planState = {
      coverageFilter: "attention",
      coverageRows: []
    };
```

Add event wiring:

```javascript
    document.querySelectorAll("[data-coverage-filter]").forEach(button => {
      button.addEventListener("click", () => {
        planState.coverageFilter = button.dataset.coverageFilter;
        document.querySelectorAll("[data-coverage-filter]").forEach(chip => {
          chip.classList.toggle("active", chip.dataset.coverageFilter === planState.coverageFilter);
        });
        renderCoverageRows(planState.coverageRows);
      });
    });
    document.querySelector('[data-coverage-filter="attention"]').classList.add("active");
```

- [ ] **Step 6: Refactor `refreshCoverage()`**

Replace the body of `refreshCoverage()` with:

```javascript
    async function refreshCoverage() {
      const cov = await getJson("/api/control/coverage");
      const depts = await getJson("/api/control/catalog");
      const covered = Number(cov.covered || 0);
      const missing = Math.max(0, depts.length - covered);
      const overlap = Number(cov.overlap || cov.overlaps || 0);
      const stale = Number(cov.stale || 0);

      setText("coverage-covered-count", covered);
      setText("coverage-missing-count", missing);
      setText("coverage-overlap-count", overlap);
      setText("coverage-stale-count", stale);
      setText("plan-covered-count", covered);
      setText("plan-missing-count", missing);
      setText("plan-overlap-count", overlap);
      setText("plan-stale-count", stale);

      planState.coverageRows = depts.map(dept => {
        const status = dept.last_crawled_at ? "covered" : "missing";
        return {
          name: dept.name || dept.department_name || dept.code || "Unknown department",
          status,
          lastCrawl: dept.last_crawled_at || "",
          source: dept.source_url || "",
          action: status === "missing" ? "Start crawler" : "Review"
        };
      });
      renderCoverageRows(planState.coverageRows);
    }
```

If `setText` does not exist, add:

```javascript
    function setText(id, value) {
      const node = el(id);
      if (node) node.textContent = String(value);
    }
```

- [ ] **Step 7: Add `renderCoverageRows(rows)`**

Add:

```javascript
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
        tbody.innerHTML = '<tr><td colspan="5" class="empty">No rows match this coverage filter.</td></tr>';
        return;
      }
      tbody.innerHTML = filtered.map(row => `
        <tr>
          <td data-label="Department">${escapeHtml(row.name)}</td>
          <td data-label="Status"><span class="status-label ${row.status === "covered" ? "healthy" : "attention"}">${escapeHtml(row.status)}</span></td>
          <td data-label="Last crawl">${row.lastCrawl ? escapeHtml(row.lastCrawl) : '<span class="muted">Never</span>'}</td>
          <td data-label="Source">${row.source ? `<a class="source" href="${escapeHtml(row.source)}" target="_blank" rel="noopener noreferrer">Open</a>` : '<span class="muted">-</span>'}</td>
          <td data-label="Action"><button class="btn" type="button" onclick="window.location.hash='#/operate/crawlers'">${escapeHtml(row.action)}</button></td>
        </tr>
      `).join("");
    }
```

- [ ] **Step 8: Wire schedule drawer and cadence preview**

Add event wiring:

```javascript
    el("open-new-schedule").addEventListener("click", () => openDrawer("new-schedule-drawer"));
    el("schedule-cadence").addEventListener("change", () => {
      const cadence = el("schedule-cadence").value;
      const advanced = cadence === "advanced";
      el("advanced-cron-panel").hidden = !advanced;
      if (!advanced) el("schedule-expression").value = cadence;
      updateSchedulePreview();
    });
    el("schedule-expression").addEventListener("input", updateSchedulePreview);
```

Add:

```javascript
    function updateSchedulePreview() {
      const expression = el("schedule-expression").value.trim();
      const timezone = el("schedule-timezone").value.trim() || "America/Toronto";
      el("schedule-next-preview").textContent = `Next run preview: ${expression || "invalid expression"} in ${timezone}. Server validates the cron expression when saved.`;
    }
```

- [ ] **Step 9: Ensure schedule submit still posts existing payload**

Keep the existing `new-schedule-form` submit handler but ensure it reads the preserved IDs:

```javascript
    el("new-schedule-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      await postJson("/api/control/schedules", {
        job_id: el("schedule-job-id").value,
        expression: el("schedule-expression").value,
        timezone: el("schedule-timezone").value,
        overlap_policy: el("schedule-overlap-policy").value
      });
      closeDrawer("new-schedule-drawer");
      el("new-schedule-form").reset();
      updateSchedulePreview();
      await refreshSchedules();
    });
```

- [ ] **Step 10: Update `refreshSchedules()` row labels**

Ensure schedule rows use responsive labels:

```javascript
      tbody.innerHTML = scheds.map(sched => `
        <tr>
          <td data-label="Job">${escapeHtml(sched.job_name || sched.job_id || "-")}</td>
          <td data-label="Status"><span class="status-label ${sched.enabled ? "scheduled" : "stale"}">${sched.enabled ? "enabled" : "disabled"}</span></td>
          <td data-label="Cron"><code>${escapeHtml(sched.expression || "-")}</code></td>
          <td data-label="Next run">${escapeHtml(sched.next_run_at || "Not calculated")}</td>
          <td data-label="Overlap">${escapeHtml(sched.overlap_policy || "skip")}</td>
          <td data-label="Action"><button class="btn btn-danger" onclick="deleteSchedule('${escapeHtml(sched.id)}')" type="button">Delete</button></td>
        </tr>
      `).join("");
```

- [ ] **Step 11: Run tests**

Run:

```powershell
py -m pytest work\geds-crawler\tests\test_ui_server.py work\geds-crawler\tests\test_control_api.py -q
```

Expected: PASS.

- [ ] **Step 12: Commit Plan workspace**

Run:

```powershell
git -c safe.directory='C:/Users/asele/Documents/geds-explorer' add -- work/geds-crawler/src/geds_crawler/ui_server.py
git -c safe.directory='C:/Users/asele/Documents/geds-explorer' commit -m "feat: rebuild geds plan workspace"
```

Expected: commit includes only `ui_server.py`.

---

### Task 5: Rebuild Explore Data workspace and isolate snapshot state

**Files:**
- Modify: `work/geds-crawler/src/geds_crawler/ui_server.py`
- Test: `work/geds-crawler/tests/test_ui_server.py`

**Interfaces:**
- Consumes:
  - Existing legacy APIs `/api/status`, `/api/departments`, `/api/orgs`, `/api/people`, `/api/queue`, `/api/errors`.
  - Existing legacy state object if present.
- Produces:
  - Explore-only active DB selector and snapshot metrics.
  - Preserved snapshot table tabs and filters.
  - Clear separation from Operate and Plan.

- [ ] **Step 1: Fill Explore Data workspace markup**

Move legacy snapshot metrics, active DB selector, snapshot table tabs, filters, table, and pager into `workspace-explore-snapshot`:

```html
        <section class="panel-card explore-context">
          <div class="workspace-header-row">
            <div>
              <h2 class="panel-title">Snapshot Data</h2>
              <p class="panel-subtitle">Inspect the selected database snapshot without mixing it into crawler operations.</p>
            </div>
            <div class="form-group compact-control">
              <label for="active-db">Active DB</label>
              <select id="active-db"></select>
            </div>
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
        </section>

        <section class="panel-card">
          <nav class="tabs" aria-label="Snapshot tables">
            <button class="tab active" data-view="orgs" type="button">Org Units</button>
            <button class="tab" data-view="people" type="button">People</button>
            <button class="tab" data-view="queue" type="button">Queue</button>
            <button class="tab" data-view="errors" type="button">Errors</button>
          </nav>
          <div id="error-banner" class="error-banner" role="alert"></div>
          <div class="filters">
            <input id="search" placeholder="Search current table" />
            <select id="department"></select>
            <select id="status-filter"></select>
          </div>
          <div class="table-wrap">
            <table class="responsive-table">
              <thead id="table-head"></thead>
              <tbody id="table-body"><tr><td class="empty">Loading snapshot...</td></tr></tbody>
            </table>
          </div>
          <div class="footer">
            <span id="result-count" class="muted">No rows loaded</span>
            <div class="pager">
              <button id="prev-page" class="btn" type="button">Previous</button>
              <button id="next-page" class="btn" type="button">Next</button>
            </div>
          </div>
        </section>
```

- [ ] **Step 2: Add Explore state object**

Replace or wrap legacy snapshot state with:

```javascript
    const exploreState = {
      view: "orgs",
      q: "",
      department: "",
      status: "",
      limit: 50,
      offset: 0,
      activeDb: ""
    };
```

If existing code uses `state`, either rename it to `exploreState` everywhere in snapshot functions or keep:

```javascript
    const state = exploreState;
```

This compatibility alias keeps the existing snapshot functions working while making the state boundary explicit.

- [ ] **Step 3: Keep active DB refresh isolated**

Ensure the active DB change handler only refreshes control data and snapshot data from Explore state:

```javascript
    el("active-db").addEventListener("change", async () => {
      exploreState.activeDb = el("active-db").value;
      await Promise.all([refreshControl(), refresh(), loadDepartments()]);
    });
```

Do not place `active-db` outside `workspace-explore-snapshot`.

- [ ] **Step 4: Add mobile labels to snapshot table rendering**

In the function that renders `table-body`, change the `<td>` template to include `data-label`:

```javascript
        el("table-body").innerHTML = data.items.map(item => `<tr>${columns.map(([key, label]) => {
          const value = item[key];
          if (key === "source_url" || key === "url") {
            return `<td data-label="${escapeHtml(label)}"><a class="source" href="${escapeHtml(value)}" target="_blank" rel="noopener noreferrer">Open GEDS</a></td>`;
          }
          if (key === "status") {
            return `<td data-label="${escapeHtml(label)}"><span class="status-label ${escapeHtml(value)}">${escapeHtml(value)}</span></td>`;
          }
          return `<td data-label="${escapeHtml(label)}">${value === null || value === "" ? '<span class="muted">-</span>' : escapeHtml(value)}</td>`;
        }).join("")}</tr>`).join("");
```

- [ ] **Step 5: Run tests**

Run:

```powershell
py -m pytest work\geds-crawler\tests\test_ui_server.py -q
```

Expected: PASS, including `test_dashboard_isolates_snapshot_data_in_explore_workspace`.

- [ ] **Step 6: Commit Explore Data workspace**

Run:

```powershell
git -c safe.directory='C:/Users/asele/Documents/geds-explorer' add -- work/geds-crawler/src/geds_crawler/ui_server.py
git -c safe.directory='C:/Users/asele/Documents/geds-explorer' commit -m "feat: isolate geds explore data workspace"
```

Expected: commit includes only `ui_server.py`.

---

### Task 6: Polish responsive behavior, accessibility, and empty/error states

**Files:**
- Modify: `work/geds-crawler/src/geds_crawler/ui_server.py`
- Modify: `work/geds-crawler/tests/test_ui_server.py`
- Test: `work/geds-crawler/tests/test_ui_server.py`

**Interfaces:**
- Consumes:
  - Workspaces from Tasks 2-5.
  - Existing `showError` and data-loading functions.
- Produces:
  - panel-level empty/error/loading helpers
  - mobile table labels across all control-plane tables
  - visible focus and keyboard escape behavior
  - status labels for color-independent state.

- [ ] **Step 1: Add HTML contract test for panel-level states**

Add this test to `work/geds-crawler/tests/test_ui_server.py`:

```python
def test_dashboard_defines_panel_level_state_helpers(running_server):
    body = _get_root_html(running_server)

    assert "function renderEmptyState" in body
    assert "function renderPanelError" in body
    assert "function setPanelLoading" in body
    assert 'data-state-region="attention"' in body
    assert 'data-state-region="runs"' in body
    assert 'data-state-region="coverage"' in body
    assert 'data-state-region="schedules"' in body
```

- [ ] **Step 2: Add state-region attributes to main dynamic panels**

Update dynamic containers:

```html
            <div id="attention-list" class="attention-list" data-state-region="attention">
            <div id="live-activity-list" class="activity-list" data-state-region="runs">
              <tbody id="coverage-table-body" data-state-region="coverage"></tbody>
              <tbody id="schedules-table-body" data-state-region="schedules">
```

- [ ] **Step 3: Add panel state helper functions**

Add:

```javascript
    function renderEmptyState(message, actionLabel, action) {
      const button = actionLabel ? `<button class="btn" type="button" onclick="${escapeHtml(action)}">${escapeHtml(actionLabel)}</button>` : "";
      return `<div class="empty-state"><p>${escapeHtml(message)}</p>${button}</div>`;
    }

    function renderPanelError(message) {
      return `<div class="panel-error" role="alert"><strong>Panel could not load.</strong><span>${escapeHtml(message)}</span></div>`;
    }

    function setPanelLoading(id, message) {
      const node = el(id);
      if (node) {
        node.innerHTML = `<div class="loading-state" role="status" aria-live="polite">${escapeHtml(message)}</div>`;
      }
    }
```

- [ ] **Step 4: Add state CSS**

Add:

```css
    .empty-state, .panel-error, .loading-state {
      border: 1px dashed var(--line);
      border-radius: 14px;
      padding: 18px;
      color: var(--muted);
      background: rgba(8, 17, 31, 0.38);
    }
    .panel-error {
      border-color: rgba(248, 113, 113, 0.42);
      color: #fecaca;
      display: grid;
      gap: 4px;
    }
```

- [ ] **Step 5: Use empty states in attention, runs, schedules, and coverage**

Replace basic empty strings with specific helper calls:

```javascript
        list.innerHTML = renderEmptyState("No attention items. System looks quiet.", "View coverage", "window.location.hash='#/plan/coverage'");
```

```javascript
        list.innerHTML = renderEmptyState("No active crawlers right now.", "Start crawler", "openDrawer('start-crawler-drawer')");
```

```javascript
        tbody.innerHTML = `<tr><td colspan="5">${renderEmptyState("No rows match this coverage filter.", "Show all", "document.querySelector('[data-coverage-filter=all]').click()")}</td></tr>`;
```

```javascript
        tbody.innerHTML = `<tr><td colspan="6">${renderEmptyState("No schedules yet. Create one to keep coverage fresh.", "New schedule", "openDrawer('new-schedule-drawer')")}</td></tr>`;
```

- [ ] **Step 6: Guard route refresh errors at panel level**

Update `refreshCurrentRoute()`:

```javascript
    async function refreshCurrentRoute() {
      const route = currentRoute();
      activateRoute(route);
      try {
        await routes[route].refresh();
      } catch (error) {
        showError(error);
        const activePanel = document.querySelector(".workspace-panel.active");
        if (activePanel) {
          const firstRegion = activePanel.querySelector("[data-state-region]");
          if (firstRegion) firstRegion.innerHTML = renderPanelError(error.message || String(error));
        }
      }
    }
```

- [ ] **Step 7: Run tests**

Run:

```powershell
py -m pytest work\geds-crawler\tests\test_ui_server.py work\geds-crawler\tests\test_control_api.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit polish**

Run:

```powershell
git -c safe.directory='C:/Users/asele/Documents/geds-explorer' add -- work/geds-crawler/src/geds_crawler/ui_server.py work/geds-crawler/tests/test_ui_server.py
git -c safe.directory='C:/Users/asele/Documents/geds-explorer' commit -m "feat: polish geds ui responsive states"
```

Expected: commit includes UI server and UI tests.

---

### Task 7: End-to-end verification and visual audit handoff

**Files:**
- Modify: `docs/ux-audit/README.md` only if new screenshots are captured and should be referenced.
- Test: no source file required unless verification reveals a defect.

**Interfaces:**
- Consumes: completed UI implementation from Tasks 1-6.
- Produces: verified local UI with screenshots and test output.

- [ ] **Step 1: Run focused Python test suite**

Run:

```powershell
py -m pytest work\geds-crawler\tests\test_ui_server.py work\geds-crawler\tests\test_control_api.py -q
```

Expected: all tests PASS.

- [ ] **Step 2: Run broader crawler tests touched by current worktree**

Run:

```powershell
py -m pytest work\geds-crawler\tests -q
```

Expected: PASS. If unrelated pre-existing failures appear, record exact failing tests and continue with focused UI verification.

- [ ] **Step 3: Start or reuse local UI server**

Use the repo's existing command documented for the GEDS UI. If a server is already running and serving `/`, reuse it. Verify:

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8765/ | Select-Object -ExpandProperty StatusCode
```

Expected: `200`.

- [ ] **Step 4: Capture desktop screenshots**

Using the previously approved Playwright fallback or the user's browser if available, capture:

```text
docs/ux-audit/overhaul-01-overview.png
docs/ux-audit/overhaul-02-crawlers.png
docs/ux-audit/overhaul-03-coverage.png
docs/ux-audit/overhaul-04-schedules.png
docs/ux-audit/overhaul-05-explore-data.png
```

Expected visual checks:

- Left rail is visible and uncluttered.
- Overview shows status, attention, live activity, coverage summary, and next schedules.
- Crawlers shows Active Runs and Start crawler as the clear primary action.
- Coverage defaults to problem-oriented controls.
- Schedules exposes New schedule and next-run context.
- Explore Data owns Active DB and snapshot metrics.

- [ ] **Step 5: Capture mobile screenshot**

Capture:

```text
docs/ux-audit/overhaul-06-mobile-overview.png
```

Expected visual checks:

- Header and navigation do not overlap.
- Mobile menu opens and closes.
- Tables render as card/list rows with labels.
- Primary action remains reachable.

- [ ] **Step 6: Run browser console smoke**

Open the UI and navigate through:

```text
#/operate/overview
#/operate/crawlers
#/operate/history
#/plan/coverage
#/plan/schedules
#/explore/snapshot
```

Expected:

- No uncaught JavaScript exceptions.
- Refresh button works on each route.
- Drawers open and close.
- Escape closes an open drawer.
- Existing stop/resume/delete schedule buttons still call their existing handlers.

- [ ] **Step 7: Commit verification artifacts only if useful**

If new screenshots or audit notes are added:

```powershell
git -c safe.directory='C:/Users/asele/Documents/geds-explorer' add -- docs/ux-audit
git -c safe.directory='C:/Users/asele/Documents/geds-explorer' commit -m "docs: add geds ui overhaul audit captures"
```

Expected: commit includes only screenshot/audit artifacts. If screenshots are not committed because they are large or transient, state their local paths in the final handoff.

---

## Self-Review

- Spec coverage: The plan covers information architecture, Operate, Plan, Explore Data, functionality preservation, state separation, refresh behavior, hash routing, visual system, accessibility, responsive behavior, empty/error/loading states, implementation boundaries, and verification.
- Placeholder scan: No task contains unresolved marker text or fill-in placeholders. Broader tests are required to run; if unrelated pre-existing failures appear, the worker must record exact failing tests and continue focused UI verification.
- Type consistency: Route keys, workspace IDs, drawer IDs, and helper names are consistent across tasks:
  - `#/operate/overview`
  - `#/operate/crawlers`
  - `#/operate/history`
  - `#/plan/coverage`
  - `#/plan/schedules`
  - `#/explore/snapshot`
  - `openDrawer(drawerId)`
  - `closeDrawer(drawerId)`
  - `renderCoverageRows(rows)`
  - `renderEmptyState(message, actionLabel, action)`
  - `renderPanelError(message)`
  - `setPanelLoading(id, message)`
