# GEDS Crawl Control Plane and Temporal History Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a resumable multi-run GEDS crawler controller, scheduler, coverage UI, and deduplicated temporal history store without duplicating crawler implementations.

**Architecture:** One generic worker writes an isolated staging SQLite database per run. A controller database manages jobs, subprocesses, schedules, traffic policy, and coverage; successful staging data is transactionally reconciled into a temporal master containing current state plus change events.

**Tech Stack:** Python 3.11+, SQLite WAL, standard-library HTTP server, vanilla HTML/CSS/JavaScript, BeautifulSoup, `croniter`, pytest.

## Global Constraints

- Do not stop or alter the currently running unmanaged crawler during implementation.
- Default aggregate GEDS traffic target is 1 request/second.
- Traffic above 1 request/second requires explicit operator acknowledgement.
- Never store or expose phone, email, fax, or address data.
- Never crawl person detail pages in v1.
- Select departments by canonical DN, not display-name equality.
- The LAN control UI is intentionally unauthenticated and must show a persistent development-only warning.
- Do not commit SQLite databases or generated personal-data snapshots to Git.
- Follow strict test-first red-green-refactor for every behavior change.

---

## Phase 1: Generic Managed Worker

### Task 1: Extract Crawl Engine and Canonical Department Selection

**Files:**
- Create: `work/geds-crawler/src/geds_crawler/engine.py`
- Create: `work/geds-crawler/src/geds_crawler/catalog.py`
- Modify: `work/geds-crawler/src/geds_crawler/cli.py`
- Modify: `work/geds-crawler/src/geds_crawler/parser.py`
- Test: `work/geds-crawler/tests/test_engine.py`
- Test: `work/geds-crawler/tests/test_catalog.py`

**Interfaces:**
- `CrawlEngine(config: CrawlRunConfig).run() -> CrawlResult`
- `select_departments(catalog: list[Department], allowed_dns: set[str]) -> list[Department]`
- `CrawlRunConfig(run_id, output_dir, department_dns, rate_limit_seconds, stop_file, quiet)`

- [ ] Write a failing catalog test where the long bilingual ISED display name is selected by canonical DN.
- [ ] Run `py -m pytest tests/test_catalog.py -q`; verify failure is caused by missing DN selection.
- [ ] Implement DN-based selection and keep display-name selection only as a backwards-compatible CLI adapter.
- [ ] Write a failing engine characterization test proving the existing BFS queue, privacy projection, and per-page commit behavior.
- [ ] Extract `run_crawl` from `cli.py` into `CrawlEngine` without changing snapshot schema.
- [ ] Run the focused tests, then `py -m pytest -q`.

### Task 2: Cooperative Stop, Resume, and Heartbeat

**Files:**
- Modify: `work/geds-crawler/src/geds_crawler/engine.py`
- Modify: `work/geds-crawler/src/geds_crawler/store.py`
- Test: `work/geds-crawler/tests/test_engine_control.py`

**Interfaces:**
- `StopSignal.is_requested() -> bool`
- `crawl_runs` adds `heartbeat_at`, `current_org_dn`, `current_department_dn`, and `stop_reason`.

- [ ] Write a failing test that requests stop after one fetched page and expects status `stopped` with remaining queue preserved.
- [ ] Implement stop checks before and after fetches, then persist heartbeat and progress after every page.
- [ ] Write a failing resume test using the same staging DB and assert completed DNs are not fetched again.
- [ ] Implement resume status transitions and run the full suite.

## Phase 2: Controller, Traffic, and Scheduler

### Task 3: Controller Schema and Repository

**Files:**
- Create: `work/geds-crawler/src/geds_crawler/control_store.py`
- Create: `work/geds-crawler/src/geds_crawler/control_models.py`
- Test: `work/geds-crawler/tests/test_control_store.py`

**Interfaces:**
- `ControlStore.create_job(...)`
- `ControlStore.create_run(...)`
- `ControlStore.list_runs()`
- `ControlStore.request_stop(run_id)`
- `ControlStore.upsert_catalog(departments)`
- `ControlStore.coverage()`

- [ ] Write schema tests for jobs, explicit job department DNs, runs, schedules, events, and catalog.
- [ ] Implement migrations with a `schema_version` table and WAL mode.
- [ ] Test that “all remaining” excludes assigned/current DNs and reports overlaps deterministically.
- [ ] Run all tests.

### Task 4: Worker Process Manager

**Files:**
- Create: `work/geds-crawler/src/geds_crawler/process_manager.py`
- Create: `work/geds-crawler/src/geds_crawler/worker_cli.py`
- Test: `work/geds-crawler/tests/test_process_manager.py`

**Interfaces:**
- `ProcessManager.start_run(run_id) -> int`
- `ProcessManager.stop_run(run_id, force=False)`
- `ProcessManager.reconcile()`

- [ ] Write tests with a fake child executable for PID registration, log paths, cooperative stop, stale heartbeat, and restart reconciliation.
- [ ] Implement workers with `sys.executable -m geds_crawler.worker_cli`; never construct a shell command string.
- [ ] Keep unmanaged legacy snapshots read-only unless explicitly adopted.
- [ ] Verify stopped runs remain resumable.

### Task 5: Aggregate Traffic Policy

**Files:**
- Create: `work/geds-crawler/src/geds_crawler/traffic.py`
- Modify: `work/geds-crawler/src/geds_crawler/control_store.py`
- Test: `work/geds-crawler/tests/test_traffic.py`

**Interfaces:**
- `TrafficSummary(configured_rps, measured_rps, warning_level)`
- `TrafficPolicy` values: `queue`, `shared`, `independent`
- `can_start(projected_rps, budget_rps, acknowledged) -> StartDecision`

- [ ] Test configured aggregate RPS including unmanaged estimates.
- [ ] Test rolling RPS from request-count/heartbeat deltas.
- [ ] Test queue, shared, and independent decisions, including mandatory acknowledgement above 1 RPS.
- [ ] Implement a SQLite transaction-backed shared rate gate for managed workers.
- [ ] Run all tests.

### Task 6: Persistent Preset and Cron Scheduler

**Files:**
- Modify: `work/geds-crawler/pyproject.toml`
- Create: `work/geds-crawler/src/geds_crawler/scheduler.py`
- Test: `work/geds-crawler/tests/test_scheduler.py`

**Interfaces:**
- `validate_cron(expression) -> str`
- `next_occurrence(expression, timezone, after) -> datetime`
- overlap policy values: `skip`, `queue`, `allow`

- [ ] Add `croniter` as the only new runtime dependency.
- [ ] Test one-time, hourly, daily, weekly, valid cron, invalid cron, DST, and all overlap policies.
- [ ] Implement scheduler ticks idempotently using a unique scheduled occurrence key.
- [ ] Run all tests.

## Phase 3: Management API and UI

### Task 7: Control API

**Files:**
- Modify: `work/geds-crawler/src/geds_crawler/ui_server.py`
- Create: `work/geds-crawler/tests/test_control_api.py`

**Interfaces:**
- `GET /api/control/overview`
- `GET/POST /api/control/jobs`
- `POST /api/control/runs`
- `POST /api/control/runs/:id/stop`
- `POST /api/control/runs/:id/resume`
- `GET /api/control/coverage`
- `GET/POST/PUT/DELETE /api/control/schedules`

- [ ] Write HTTP tests for success, validation failures, overlap warnings, rate acknowledgement, and missing runs.
- [ ] Require POST/PUT/DELETE for mutations; never mutate state on GET.
- [ ] Add the unauthenticated-control warning to every mutation response.
- [ ] Run API and regression tests.

### Task 8: Operations Dashboard

**Files:**
- Modify: `work/geds-crawler/src/geds_crawler/ui_server.py`
- Modify: `work/geds-crawler/src/geds_crawler/ui_queries.py`
- Test: `work/geds-crawler/tests/test_ui_server.py`

**Interfaces:**
- Tabs: `Overview`, `Crawlers`, `Coverage`, `Schedules`, `Snapshot Data`, `History`.

- [ ] Add HTML contract tests for the permanent security warning and required tabs.
- [ ] Build the crawler table with institutions, org units, pending, completion, ETA, configured/measured RPS, heartbeat, and actions.
- [ ] Build the creation flow with explicit DNs, “all remaining”, three traffic policies, and warning acknowledgement.
- [ ] Build schedule presets plus cron validation and coverage status filters.
- [ ] Preserve active tab, filters, and pagination during the three-second refresh.
- [ ] Run all tests and manually inspect desktop and mobile widths.

## Phase 4: Temporal Master and Audit

### Task 9: Temporal Master Schema and Reconciler

**Files:**
- Create: `work/geds-crawler/src/geds_crawler/history_store.py`
- Create: `work/geds-crawler/src/geds_crawler/reconcile.py`
- Test: `work/geds-crawler/tests/test_reconcile.py`

**Interfaces:**
- `Reconciler.merge(staging_db, run_id) -> MergeSummary`
- statuses: `active`, `uncertain_missing`, `departed`
- confidence: `certain`, `uncertain`

- [ ] Test first observation emits `joined`.
- [ ] Test same canonical DN with changed title/org emits certain field-level events.
- [ ] Test first complete absence emits `missing_once` and preserves `last_seen`.
- [ ] Test second consecutive complete absence emits `departed`.
- [ ] Test partial/failed runs do not increment `missing_streak`.
- [ ] Test reappearance resets streak and emits `reappeared`.
- [ ] Test changed DN plus same normalized name/department emits a separate uncertain `possible_move` without identity merge.
- [ ] Implement content hashes and department-scoped transactions.
- [ ] Run all tests.

### Task 10: Retention and Git-Compatible Audit Artifacts

**Files:**
- Create: `work/geds-crawler/src/geds_crawler/audit.py`
- Modify: `work/geds-crawler/src/geds_crawler/exporter.py`
- Modify: `work/geds-crawler/README.md`
- Create: `work/geds-crawler/SECURITY.md`
- Test: `work/geds-crawler/tests/test_audit.py`

**Interfaces:**
- `write_audit_bundle(merge_id) -> Path`
- retention: delete successful merged staging DBs when enabled; retain stopped/failed staging DBs.

- [ ] Test deterministic manifest, JSONL event ordering, and summary counts.
- [ ] Test that audit output contains no contact fields.
- [ ] Implement optional separate audit-repo commit behind explicit configuration; default disabled.
- [ ] Document that SQLite files must not be committed.
- [ ] Document the unauthenticated LAN control vulnerability and production blockers.
- [ ] Run the full suite.

## Phase 5: Controlled Rollout

### Task 11: Import Current Run and Create Initial Jobs

**Files:**
- Create: `work/geds-crawler/src/geds_crawler/bootstrap_control.py`
- Test: `work/geds-crawler/tests/test_bootstrap_control.py`

- [ ] Import the existing snapshot as an `unmanaged` run without stopping it.
- [ ] Refresh all department DNs from the live GEDS catalog.
- [ ] Create job `ISED + CRTC` from their canonical DNs.
- [ ] Create job `All remaining institutions` from catalog difference and freeze the selected DN list.
- [ ] Verify no department is silently omitted and overlaps are explicit.
- [ ] Run ISED + CRTC with `max_depth=1` and inspect privacy/report outputs.
- [ ] Start larger jobs only after the dry run passes and the operator chooses traffic policy.

## Completion Verification

Run:

```powershell
cd work\geds-crawler
py -m pytest -q
```

Then verify:

- Existing unmanaged crawl was not interrupted.
- ISED is selected by DN despite its display-name variation.
- CRTC is selected by DN.
- Coverage accounts for every current GEDS department DN exactly once or marks overlap.
- Stop/resume preserves completed queue entries.
- Aggregate configured and measured RPS are visible.
- A first absence is uncertain and a second valid absence is departed.
- No database/API/export schema contains contact fields.
- The UI visibly states that control endpoints are unauthenticated.

