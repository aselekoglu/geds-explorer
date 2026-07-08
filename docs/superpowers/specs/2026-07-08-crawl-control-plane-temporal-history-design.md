# GEDS Crawl Control Plane and Temporal History Design

## Objective

Turn the existing single-process crawler and read-only monitor into a local crawl control plane that can:

- run multiple independently configured crawl jobs from one generic crawler engine;
- show institution coverage and aggregate GEDS request traffic;
- start, stop, resume, queue, and schedule jobs;
- avoid storing a complete duplicate snapshot after every crawl;
- retain current state plus meaningful changes over time;
- distinguish certain changes from inferred or uncertain changes.

The initial managed jobs are:

1. ISED and CRTC.
2. Every GEDS institution not covered by the current IT-focused crawl or job 1.

Institution selection must use canonical department DN, not exact display-name matching. This fixes the current ISED name mismatch.

## Safety and Privacy

- Continue the existing default of 1 request/second.
- Show configured aggregate RPS and measured rolling aggregate RPS.
- Allow the operator to exceed 1 aggregate RPS only after an explicit warning acknowledgement.
- Never fetch person detail pages in v1.
- Never store phone numbers, email addresses, fax numbers, or addresses.
- Every person and org record retains its official GEDS source URL and crawl dates.
- Do not provide bulk contact export.

The management UI is intentionally unauthenticated for the current local-only phase. This is a known vulnerability because LAN users can start and stop crawlers. The UI, README, and security notes must display:

> Development only: unauthenticated crawl control. Do not expose this service to an untrusted LAN or the public internet.

Production is blocked until authentication, authorization, CSRF protection, and TLS or a trusted reverse proxy are added.

## Architecture

### Generic Worker

There is one crawler implementation. A job supplies an explicit list of canonical department DNs, output directory, rate policy, and optional schedule. Do not create copied ISED, CRTC, or all-department crawler modules.

The crawler loop becomes a reusable engine with:

- cooperative stop checks between requests;
- heartbeat and request-count updates after each page;
- resumable queue state in its staging SQLite database;
- canonical department selection by DN;
- clean statuses: `queued`, `running`, `stopping`, `stopped`, `completed`, `failed`;
- no destructive reset of completed queue items on resume.

### Controller Database

Create `outputs/control/control.sqlite` for operational metadata only:

- `department_catalog`
- `crawl_jobs`
- `job_departments`
- `crawl_runs`
- `run_departments`
- `schedules`
- `controller_events`
- `rate_gate`

The controller owns worker subprocesses and polls their staging databases. Workers never write the controller database directly.

### Run Storage

Each run writes to:

```text
outputs/runs/<run-id>/
  staging.sqlite
  run-manifest.json
  crawl-report.md
  org-units.jsonl
  people-index.jsonl
  worker.stdout.log
  worker.stderr.log
```

Staging databases isolate concurrent writes. After a successful temporal merge, completed staging databases may be deleted according to retention policy. Failed or stopped staging databases remain resumable.

### Traffic Policies

At start time the operator chooses:

- `queue`: start only when projected aggregate RPS is within the selected global budget;
- `shared`: run concurrently through a controller-owned global rate gate;
- `independent`: use the run's own rate limit even if aggregate traffic exceeds 1 RPS.

The UI shows:

- configured RPS per run;
- projected aggregate RPS;
- rolling measured aggregate RPS from request-count deltas;
- an amber warning above 1 RPS and a stronger warning above 2 RPS.

Legacy processes that predate the controller are shown as `unmanaged`. Their estimated RPS is configurable and included in projected aggregate traffic. The controller must not kill an unmanaged process unless it has been explicitly adopted with a verified PID and output directory.

### Scheduler

Schedules are persisted in the controller database and evaluated by the controller process in timezone `America/Toronto`.

The UI supports:

- one-time execution;
- hourly, daily, and weekly presets;
- validated five-field cron expressions;
- overlap policies: `skip`, `queue`, or `allow`;
- enable, disable, edit, and delete.

Use a proven cron parser such as `croniter`; do not hand-roll cron parsing.

### Coverage

Refresh the GEDS department catalog from `pgid=012` and store canonical DN, display name, source URL, and last-seen time.

For every institution show:

- `unassigned`
- `scheduled`
- `queued`
- `running`
- `covered-current`
- `covered-stale`
- `failed`
- `overlap`

Job creation snapshots the selected department DNs into `job_departments` for reproducibility. The “all remaining” builder means catalog DNs minus DNs already assigned to enabled jobs or the current managed/imported run.

### Temporal Master

Create `outputs/master/geds-master.sqlite`. It stores current state and deltas, not full repeated snapshots.

Core current tables:

- `departments_current`
- `org_units_current`
- `people_current`

History tables:

- `change_events`
- `person_observations`
- `org_observations`
- `merge_runs`

Each normalized entity has a deterministic content hash over permitted fields. A successful staging run is reconciled department by department:

1. Insert newly observed entities and emit `joined` or `created`.
2. Update changed entities and emit field-level `title_changed`, `org_changed`, `department_changed`, `renamed`, or `org_restructured`.
3. Leave unchanged rows untouched except for `last_seen`.
4. On first absence after a complete, error-free department crawl, set `missing_streak=1`, status `uncertain_missing`, preserve `last_seen`, and emit `missing_once`.
5. On second consecutive complete, error-free absence, set status `departed` and emit `departed`.
6. Partial, stopped, or failed department crawls never advance absence state.
7. A later observation emits `reappeared` and resets the missing streak.

Certain person changes require the same canonical person DN. If a newly joined DN and a newly missing DN have the same normalized display name and department, create a separate `possible_move` candidate with `confidence=uncertain`; never silently merge them.

### Git Audit

Do not commit SQLite files to Git. SQLite page churn produces opaque binary diffs and poor repository behavior.

After each successful merge, generate:

```text
history/<merge-id>/manifest.json
history/<merge-id>/changes.jsonl
history/<merge-id>/summary.md
```

An optional separate private audit repository may commit these small, readable artifacts once per successful merge. Automatic Git commits are disabled by default. Source code, migrations, and schemas belong in the code repository; crawl data does not.

## Management UI

Extend the existing monitor with:

- Overview: aggregate traffic, active workers, coverage totals, next schedules.
- Crawlers: name, institutions, status, org units, people, pending, errors, completion, configured RPS, measured RPS, ETA, last heartbeat, actions.
- Coverage: every catalog institution and its assigned/current status.
- New crawler: department multi-select, “all remaining”, rate, traffic policy, start mode, output retention, schedule.
- Schedules: presets, cron expression, timezone, overlap policy, next run.
- History: merge summaries and certain/uncertain changes.

ETA uses an exponentially weighted moving average of completed pages per minute. Until enough samples exist, label ETA as low confidence and estimate from pending pages and configured rate.

Start, stop, resume, and schedule endpoints are POST/PUT/DELETE operations. Even though v1 is unauthenticated, do not implement state changes as GET requests.

## Error Handling

- A worker heartbeat older than 30 seconds while its process is absent becomes `failed`.
- A stop request is cooperative; after a 30-second timeout the UI may offer a separate force-stop action.
- Controller restart reconciles registered PIDs, staging DB state, and schedules before launching anything.
- Temporal merge is transactional per department.
- Failed merges preserve staging data and do not alter current/history tables.
- Overlapping department jobs are warned and visually marked but may run after explicit acknowledgement.

## Testing

- Unit tests for catalog selection, coverage calculation, rate warnings, cron validation, ETA, and temporal transitions.
- Worker tests for stop/resume and queue preservation.
- Controller integration tests with fake workers; do not hit live GEDS.
- HTTP tests for all read and mutation endpoints.
- Privacy tests asserting no contact fields in controller, master, exports, or API.
- Temporal tests for joined, changed, missing-once, departed-on-second-miss, reappeared, partial-crawl suppression, and uncertain possible moves.
- A live dry run limited to ISED and CRTC depth 1 before starting either large job.

