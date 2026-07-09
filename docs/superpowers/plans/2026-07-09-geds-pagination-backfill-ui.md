# GEDS Pagination Backfill and UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the 25-person organization-page ceiling, run a resumable one-time pagination backfill against the 1,418 capped organizations, and expose stable progress, ETA, and crawler controls in the existing UI.

**Architecture:** Keep one `CrawlEngine` and one pagination parser for both normal crawls and `pagination_backfill` runs. Persist page-level and organization-level state in each run's isolated SQLite database, freeze backfill targets in the control database when the run is created, and combine immutable base data with overlay rows by canonical person `source_url`. Move run telemetry and overlay queries out of `ui_server.py` so HTTP handlers only validate inputs and serialize results.

**Tech Stack:** Python 3.11+, SQLite/WAL, BeautifulSoup 4, stdlib `http.server`, pytest 8, vanilla HTML/CSS/JavaScript.

## Global Constraints

- Preserve the completed base snapshot byte-for-byte; every backfill writes to a new run directory.
- Never request person-detail pages (`pgid=015`). Store only the existing contact-free `PersonIndex` fields.
- Follow only a source-provided next-page link. A 25-person count alone must never synthesize a page number.
- Accept pagination URLs only on `https://geds-sage.gc.ca/en/GEDS`.
- Canonicalize page URLs, reject cycles, and stop after 500 pages per organization with a visible terminal error.
- Keep the fixed progress denominator equal to the frozen target-organization count. Newly discovered pages must not reduce progress.
- Treat terminal failures separately from successful organizations in API and UI payloads.
- Check the cooperative stop signal between page requests; resume must skip committed pages and people.
- Logging/UI failures must not turn an already committed page into a crawl failure.
- Do not start the 1,418-organization production backfill as part of implementation. Live verification is limited to two explicitly selected capped organizations.
- Existing uncommitted changes in `process_manager.py`, `ui_server.py`, `worker_cli.py`, `test_control_api.py`, and `test_process_manager.py` belong to the user. Inspect and integrate with them; do not overwrite or revert them.
- Run commands below from `C:\Users\asele\Documents\geds-explorer\work\geds-crawler`.

---

### Task 1: Parse and validate source-provided pagination links

**Files:**

- Create: `work/geds-crawler/src/geds_crawler/pagination.py`
- Modify: `work/geds-crawler/src/geds_crawler/parser.py`
- Modify: `work/geds-crawler/src/geds_crawler/urls.py`
- Create: `work/geds-crawler/tests/fixtures/org_people_page_1.html`
- Create: `work/geds-crawler/tests/fixtures/org_people_page_2.html`
- Modify: `work/geds-crawler/tests/test_parser.py`
- Modify: `work/geds-crawler/tests/test_urls.py`

- [ ] **Step 1: Add failing pagination parser tests**

Add fixtures where page 1 has 25 people and an actual “Next” anchor, while page 2 has the terminal records and no next link. Cover relative, absolute, off-origin, wrong-path, duplicate, malformed, and no-next cases.

```python
def test_extract_people_page_returns_people_and_canonical_next_url():
    page = extract_people_page(
        load_fixture("org_people_page_1.html"),
        org_dn="OU=TEAM,OU=ISED-ISDE,O=GC,C=CA",
        department_dn="OU=ISED-ISDE,O=GC,C=CA",
        department_name="ISED",
        org_name="Team",
        org_path="ISED / Team",
    )
    assert len(page.people) == 25
    assert page.next_url is not None
    parsed = urlsplit(page.next_url)
    assert (parsed.scheme, parsed.netloc, parsed.path) == (
        "https", "geds-sage.gc.ca", "/en/GEDS"
    )
    assert dict(parse_qsl(parsed.query))["page"] == "2"


def test_exactly_25_people_without_next_link_is_terminal():
    links = "".join(
        f'<a href="{geds_url("015", f"CN=Person {index},OU=TEAM,O=GC,C=CA")}">'
        f"Person {index}</a>"
        for index in range(25)
    )
    page = extract_people_page(
        f"<html><body>{links}</body></html>",
        org_dn="OU=TEAM,OU=ISED-ISDE,O=GC,C=CA",
        department_dn="OU=ISED-ISDE,O=GC,C=CA",
        department_name="ISED",
        org_name="Team",
        org_path="ISED / Team",
    )
    assert len(page.people) == 25
    assert page.next_url is None


@pytest.mark.parametrize("href", [
    "https://example.com/en/GEDS?pgid=014&dn=x&page=2",
    "https://geds-sage.gc.ca/not-GEDS?pgid=014&dn=x&page=2",
    "javascript:alert(1)",
])
def test_unsafe_next_link_is_rejected(href):
    assert canonical_pagination_url(href) is None
```

- [ ] **Step 2: Run the focused tests and confirm failure**

Run:

```powershell
py -m pytest tests/test_parser.py tests/test_urls.py -q
```

Expected: failures because `PeoplePage`, `extract_people_page`, and `canonical_pagination_url` do not exist.

- [ ] **Step 3: Implement canonical URL validation**

Create `pagination.py` with the explicit page result and safety boundary:

```python
from dataclasses import dataclass
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

from .config import BASE_URL, GEDS_PATH
from .models import PersonIndex

MAX_PAGES_PER_ORG = 500


@dataclass(frozen=True)
class PeoplePage:
    people: tuple[PersonIndex, ...]
    next_url: str | None


def canonical_pagination_url(href: str | None) -> str | None:
    if not href:
        return None
    absolute = urljoin(f"{BASE_URL}{GEDS_PATH}", href)
    parsed = urlsplit(absolute)
    allowed = urlsplit(BASE_URL)
    if parsed.scheme != "https" or parsed.netloc != allowed.netloc:
        return None
    if parsed.path != GEDS_PATH:
        return None
    query = sorted(parse_qsl(parsed.query, keep_blank_values=True))
    if not any(key == "pgid" and value == "014" for key, value in query):
        return None
    return urlunsplit(("https", allowed.netloc, GEDS_PATH, urlencode(query), ""))
```

Keep fragments out of canonical URLs. Do not require a particular pagination parameter name; the live source owns that contract.

- [ ] **Step 4: Implement `extract_people_page` without duplicating person parsing**

Refactor `extract_people` to call `extract_people_page` with its existing six
arguments and return `list(result.people)`. In `extract_people_page`, parse
people using the current privacy-preserving logic and choose the next link only
from anchors identified by `rel=next`, accessible label, or normalized visible
text `next`/`suivant`. Pass every candidate through
`canonical_pagination_url`.

```python
def extract_people_page(
    html: str,
    org_dn: str,
    department_dn: str,
    department_name: str,
    org_name: str,
    org_path: str,
) -> PeoplePage:
    soup = _soup(html)
    people = tuple(
        _extract_people_from_soup(
            soup,
            org_dn,
            department_dn,
            department_name,
            org_name,
            org_path,
        )
    )
    next_url = _extract_next_page_url(soup)
    return PeoplePage(people=people, next_url=next_url)
```

Reject a next URL that canonicalizes to the current page in the engine, where the visited-page set is available.

- [ ] **Step 5: Run focused tests**

Run:

```powershell
py -m pytest tests/test_parser.py tests/test_urls.py -q
```

Expected: all parser and URL tests pass.

- [ ] **Step 6: Commit**

```powershell
git add src/geds_crawler/pagination.py src/geds_crawler/parser.py src/geds_crawler/urls.py tests/fixtures/org_people_page_1.html tests/fixtures/org_people_page_2.html tests/test_parser.py tests/test_urls.py
git commit -m "feat: parse safe GEDS pagination links"
```

---

### Task 2: Persist resumable organization and page state

**Files:**

- Modify: `work/geds-crawler/src/geds_crawler/models.py`
- Modify: `work/geds-crawler/src/geds_crawler/store.py`
- Modify: `work/geds-crawler/tests/test_store.py`

- [ ] **Step 1: Add failing schema and transition tests**

Test the exact tables and idempotent transitions:

```python
def test_pagination_schema_tracks_fixed_org_targets_and_page_queue(tmp_path):
    with SnapshotStore(tmp_path / "geds.sqlite") as store:
        store.init_schema()
        tables = {
            row[0] for row in store.db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        assert {"pagination_orgs", "people_page_queue"} <= tables


def test_page_completion_and_next_enqueue_are_atomic_and_idempotent(tmp_path):
    page_1 = "https://geds-sage.gc.ca/en/GEDS?dn=team&page=1&pgid=014"
    page_2 = "https://geds-sage.gc.ca/en/GEDS?dn=team&page=2&pgid=014"
    now = "2026-07-09T00:00:00+00:00"
    target = make_pagination_target(org_dn="OU=TEAM,O=GC,C=CA")
    store.seed_pagination_target(target, now)
    store.enqueue_people_page(target.org.dn, page_1, 1, None, now)
    store.complete_people_page(
        page_url=page_1,
        next_url=page_2,
        people_observed=25,
        people_inserted=20,
        people_deduped=5,
        completed_at=now,
    )
    store.complete_people_page(
        page_url=page_1,
        next_url=page_2,
        people_observed=25,
        people_inserted=20,
        people_deduped=5,
        completed_at=now,
    )
    assert store.pagination_metrics()["pages_fetched"] == 1
    assert store.pagination_metrics()["known_pending_pages"] == 1
    assert store.pagination_metrics()["new_people"] == 20
```

Also test that terminal success/error only increments the fixed organization numerator once.

- [ ] **Step 2: Run and confirm failure**

Run:

```powershell
py -m pytest tests/test_store.py -q
```

Expected: failures for missing pagination tables and methods.

- [ ] **Step 3: Add page and target models**

Add immutable records to `models.py`:

```python
@dataclass(frozen=True)
class PaginationTarget:
    org: OrgUnit
    department_name: str
    base_db_path: str
    base_people_count: int


@dataclass(frozen=True)
class PeoplePageItem:
    org_dn: str
    page_url: str
    page_index: int
```

- [ ] **Step 4: Add staging schema**

Extend `SnapshotStore.init_schema()` with:

```sql
CREATE TABLE IF NOT EXISTS pagination_orgs (
  org_dn TEXT PRIMARY KEY,
  department_dn TEXT NOT NULL,
  department_name TEXT NOT NULL,
  org_name TEXT NOT NULL,
  org_path TEXT NOT NULL,
  source_url TEXT NOT NULL,
  base_db_path TEXT NOT NULL,
  base_people_count INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  pages_fetched INTEGER NOT NULL DEFAULT 0,
  people_observed INTEGER NOT NULL DEFAULT 0,
  people_inserted INTEGER NOT NULL DEFAULT 0,
  people_deduped INTEGER NOT NULL DEFAULT 0,
  last_page_url TEXT,
  started_at TEXT,
  heartbeat_at TEXT,
  finished_at TEXT,
  terminal_reason TEXT,
  last_error TEXT
);

CREATE TABLE IF NOT EXISTS people_page_queue (
  page_url TEXT PRIMARY KEY,
  org_dn TEXT NOT NULL,
  page_index INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  attempts INTEGER NOT NULL DEFAULT 0,
  discovered_from TEXT,
  last_error TEXT,
  first_seen TEXT NOT NULL,
  completed_at TEXT,
  FOREIGN KEY (org_dn) REFERENCES pagination_orgs(org_dn)
);
```

Add indexes on `(status, org_dn, page_index)` and `pagination_orgs(status)`.

- [ ] **Step 5: Implement transactional store methods**

Implement:

```python
seed_pagination_target(target, seen_at) -> None
enqueue_people_page(org_dn, page_url, page_index, discovered_from, seen_at) -> None
next_pending_people_page(org_dn: str | None = None) -> PeoplePageItem | None
complete_people_page(
    page_url,
    next_url,
    people_observed,
    people_inserted,
    people_deduped,
    completed_at,
) -> None
mark_pagination_org_success(org_dn, reason, finished_at) -> None
mark_pagination_org_error(org_dn, error, finished_at) -> None
pagination_progress() -> dict[str, int | float]
pagination_metrics() -> dict[str, int]
```

`complete_people_page` must update the page, organization counters, and optional next-page insert in one transaction. Use `INSERT ... ON CONFLICT DO NOTHING` and only increment counters when the page changes from non-done to done.

- [ ] **Step 6: Run focused tests**

Run:

```powershell
py -m pytest tests/test_store.py -q
```

Expected: all store tests pass.

- [ ] **Step 7: Commit**

```powershell
git add src/geds_crawler/models.py src/geds_crawler/store.py tests/test_store.py
git commit -m "feat: persist resumable pagination state"
```

---

### Task 3: Integrate native pagination into the shared crawl engine

**Files:**

- Modify: `work/geds-crawler/src/geds_crawler/engine.py`
- Modify: `work/geds-crawler/src/geds_crawler/worker_cli.py`
- Modify: `work/geds-crawler/tests/test_engine.py`
- Modify: `work/geds-crawler/tests/test_engine_control.py`

- [ ] **Step 1: Add failing multi-page, stop/resume, cycle, and limit tests**

Use a URL-keyed fake fetcher. Verify:

- a normal `full` crawl stores people from pages 1 and 2;
- page 2 is fetched only from the parsed source link;
- stopping after page 1 leaves page 1 done and page 2 pending;
- resume does not refetch page 1;
- a page-2-to-page-1 cycle marks the organization terminal-error;
- page index 501 is never requested;
- a print/logging exception after commit does not mark the page failed.

The main assertion sequence is `requested_urls.count(page_1_url) == 1`,
`requested_urls.count(page_2_url) == 1`, and
`SELECT COUNT(*) FROM people_index` greater than 25 after resume.

- [ ] **Step 2: Run and confirm failure**

Run:

```powershell
py -m pytest tests/test_engine.py tests/test_engine_control.py -q
```

Expected: new tests fail because the engine processes one page per org.

- [ ] **Step 3: Add run kind to the engine configuration**

```python
@dataclass(frozen=True)
class CrawlRunConfig:
    run_id: str
    output_dir: Path
    department_dns: set[str]
    rate_limit_seconds: float = 1.0
    stop_file: Path | None = None
    quiet: bool = False
    max_depth: int | None = None
    crawl_kind: Literal["full", "pagination_backfill"] = "full"
    control_db_path: Path | None = None
    max_pages_per_org: int = MAX_PAGES_PER_ORG
```

Add `--crawl-kind`, `--control-db`, and `--max-pages-per-org` to `worker_cli.py`. Keep existing CLI calls backward compatible with `full`.

- [ ] **Step 4: Extract one resumable page loop**

Add private methods in `CrawlEngine`:

```python
def _ensure_first_page(
    self, store: SnapshotStore, item: QueueItem, seen_at: str
) -> None:
    """Create page-one state only when the org has no persisted page rows."""

def _crawl_pending_pages(
    self, store: SnapshotStore, fetcher: PoliteFetcher, item: QueueItem
) -> Literal["success", "stopped", "error"]:
    """Process persisted pages until terminal, stop, or guard failure."""

def _process_people_page(
    self,
    store: SnapshotStore,
    fetcher: PoliteFetcher,
    item: QueueItem,
    page_item: PeoplePageItem,
) -> Literal["next", "terminal", "stopped", "error"]:
    """Fetch and atomically commit exactly one queued page."""
```

Required order per page:

1. Check stop signal.
2. Mark heartbeat/current org.
3. Fetch the queued canonical URL.
4. Parse people and next URL.
5. Reject self-link, visited URL, or page index above the configured maximum.
6. Upsert people and calculate inserted versus deduped using pre-upsert existence.
7. Commit page completion, counters, and next enqueue atomically.
8. Log only after commit in a separate non-fatal block.

For `full`, parse child org links only from page index 1. For `pagination_backfill`, never enqueue newly observed child orgs.

- [ ] **Step 5: Make organization completion terminal-page based**

Do not call `mark_org_done` until `_crawl_pending_pages` returns `success`. Keep `crawl_queue` pending on cooperative stop. On terminal guard/error, mark both `pagination_orgs` and the corresponding crawl-queue row as error with the explicit reason.

- [ ] **Step 6: Run focused tests**

Run:

```powershell
py -m pytest tests/test_engine.py tests/test_engine_control.py tests/test_store.py -q
```

Expected: all pass, including stop/resume and >25-person assertions.

- [ ] **Step 7: Commit**

```powershell
git add src/geds_crawler/engine.py src/geds_crawler/worker_cli.py tests/test_engine.py tests/test_engine_control.py
git commit -m "feat: crawl all GEDS person pages"
```

---

### Task 4: Freeze capped-org backfill targets in the control plane

**Files:**

- Modify: `work/geds-crawler/src/geds_crawler/control_models.py`
- Modify: `work/geds-crawler/src/geds_crawler/control_store.py`
- Modify: `work/geds-crawler/tests/test_control_store.py`

- [ ] **Step 1: Add failing migration and seed tests**

Test migration from the existing version-1 database as well as fresh creation. Create a base snapshot with org counts 24, 25, 25, and 26, then assert only the two capped orgs are frozen.

```python
run_id = store.create_run(job_id, status="queued")
seeds = store.list_pagination_seeds(run_id)
assert [seed["org_dn"] for seed in seeds] == [
    "OU=A,OU=ISED-ISDE,O=GC,C=CA",
    "OU=B,OU=ISED-ISDE,O=GC,C=CA",
]
```

Assert changing the base snapshot after `create_run` does not change `seeds`.

- [ ] **Step 2: Run and confirm failure**

Run:

```powershell
py -m pytest tests/test_control_store.py -q
```

Expected: failures because control jobs/runs have no kind, source DB, or seed table.

- [ ] **Step 3: Add an explicit version-2 migration**

Do not rely on `CREATE TABLE IF NOT EXISTS` to add columns. Add an idempotent migration helper and move `schema_version` from 1 to 2:

```sql
ALTER TABLE crawl_jobs ADD COLUMN crawl_kind TEXT NOT NULL DEFAULT 'full';
ALTER TABLE crawl_jobs ADD COLUMN source_db_path TEXT;
ALTER TABLE crawl_runs ADD COLUMN crawl_kind TEXT NOT NULL DEFAULT 'full';
ALTER TABLE crawl_runs ADD COLUMN source_db_path TEXT;

CREATE TABLE run_pagination_seeds (
  run_id TEXT NOT NULL,
  org_dn TEXT NOT NULL,
  source_url TEXT NOT NULL,
  department_dn TEXT NOT NULL,
  department_name TEXT NOT NULL,
  org_name TEXT NOT NULL,
  org_path TEXT NOT NULL,
  base_db_path TEXT NOT NULL,
  base_people_count INTEGER NOT NULL,
  seeded_at TEXT NOT NULL,
  PRIMARY KEY (run_id, org_dn),
  FOREIGN KEY (run_id) REFERENCES crawl_runs(id) ON DELETE CASCADE
);
```

Validate `crawl_kind` in Python against `{"full", "pagination_backfill"}`.

- [ ] **Step 4: Extend job/run creation**

Use keyword-only optional arguments so existing callers remain valid:

```python
def create_job(
    self,
    name: str,
    department_dns: set[str],
    rate_limit_seconds: float,
    traffic_policy: str,
    output_dir: str,
    *,
    crawl_kind: str = "full",
    source_db_path: str | None = None,
) -> str:
    """Persist a validated crawler job and return its UUID."""
```

For `pagination_backfill`, require a readable completed snapshot DB. In `create_run`, copy `crawl_kind` and `source_db_path` to the run, then freeze targets with:

```sql
SELECT
  o.dn, o.source_url, o.department_dn, d.name AS department_name,
  o.name, o.org_path, COUNT(p.source_url) AS base_people_count
FROM org_units o
JOIN departments d ON d.dn = o.department_dn
LEFT JOIN people_index p ON p.org_dn = o.dn
GROUP BY o.dn
HAVING COUNT(p.source_url) = 25
ORDER BY o.org_path
```

Use SQLite read-only URI mode for the base. Store its resolved absolute path. Reject a source DB whose latest `crawl_runs.status` is not `finished`.

- [ ] **Step 5: Run focused tests**

Run:

```powershell
py -m pytest tests/test_control_store.py tests/test_scheduler.py tests/test_traffic.py -q
```

Expected: all pass and legacy full-job call sites remain compatible.

- [ ] **Step 6: Commit**

```powershell
git add src/geds_crawler/control_models.py src/geds_crawler/control_store.py tests/test_control_store.py
git commit -m "feat: freeze pagination backfill targets"
```

---

### Task 5: Materialize seeds and launch backfill workers through the existing process manager

**Files:**

- Modify: `work/geds-crawler/src/geds_crawler/process_manager.py`
- Modify: `work/geds-crawler/src/geds_crawler/worker_cli.py`
- Modify: `work/geds-crawler/src/geds_crawler/engine.py`
- Modify: `work/geds-crawler/tests/test_process_manager.py`
- Modify: `work/geds-crawler/tests/test_engine_control.py`

- [ ] **Step 1: Add failing command and seed-materialization tests**

Assert a backfill worker command contains:

```text
--crawl-kind pagination_backfill
--control-db <absolute-control.sqlite>
```

and does not require `--department-dns`. Assert its first run copies every frozen control seed into the staging DB and that resume does not re-read a changed base snapshot.

- [ ] **Step 2: Run and confirm failure**

Run:

```powershell
py -m pytest tests/test_process_manager.py tests/test_engine_control.py -q
```

Expected: failures because worker arguments and backfill seeding are absent.

- [ ] **Step 3: Build kind-aware worker commands**

Read `crawl_kind` and `source_db_path` in `ProcessManager.start_run`. Always pass `--crawl-kind` and `--control-db`. Pass `--department-dns` only for `full`; update argparse from `required=True` to optional and validate the required combination after parsing.

- [ ] **Step 4: Seed the isolated staging DB**

At backfill startup, if `pagination_orgs` is empty:

1. Open the control DB read-only.
2. Read `run_pagination_seeds` for the run.
3. Insert minimal department/org context into the staging DB.
4. Insert every target into `pagination_orgs`.
5. Enqueue its source-provided first org URL in both `crawl_queue` and `people_page_queue`.
6. Commit once.

If no seeds exist, fail the run with `no_frozen_targets`.

- [ ] **Step 5: Preserve resume semantics**

`ProcessManager.start_run` must clear only the stop file. It must not reset staging queues or counters. Reconcile continues to copy heartbeat/request count from the staging `crawl_runs` row for both kinds.

- [ ] **Step 6: Run focused tests**

Run:

```powershell
py -m pytest tests/test_process_manager.py tests/test_engine_control.py -q
```

Expected: all pass.

- [ ] **Step 7: Commit**

```powershell
git add src/geds_crawler/process_manager.py src/geds_crawler/worker_cli.py src/geds_crawler/engine.py tests/test_process_manager.py tests/test_engine_control.py
git commit -m "feat: run managed pagination backfills"
```

---

### Task 6: Add stable progress and evidence-based ETA calculations

**Files:**

- Create: `work/geds-crawler/src/geds_crawler/run_metrics.py`
- Create: `work/geds-crawler/tests/test_run_metrics.py`
- Modify: `work/geds-crawler/src/geds_crawler/store.py`

- [ ] **Step 1: Add deterministic failing tests**

Use a fixed clock. Test:

- progress is `terminal / fixed target`, with success and failure separate;
- adding pending pages does not decrease progress;
- configured-rate fallback before a fresh measured sample;
- EWMA updates from completed organization request counts;
- confidence is low at 0–49, medium at 50–199, high at 200+;
- stale measured RPS falls back to configured RPS;
- low/high range and finish timestamp are deterministic.

```python
assert calculate_progress(total=100, succeeded=20, failed=5) == {
    "total_orgs": 100,
    "completed_orgs": 20,
    "failed_orgs": 5,
    "terminal_orgs": 25,
    "percent": 25.0,
}
```

- [ ] **Step 2: Run and confirm failure**

Run:

```powershell
py -m pytest tests/test_run_metrics.py -q
```

Expected: import failure because `run_metrics.py` does not exist.

- [ ] **Step 3: Implement typed metric functions**

Create frozen result dataclasses:

```python
@dataclass(frozen=True)
class EtaEstimate:
    expected_seconds: int | None
    low_seconds: int | None
    high_seconds: int | None
    confidence: Literal["low", "medium", "high"]
    basis: Literal["configured_rate", "measured_rate"]
    estimated_finish_at: str | None
```

Implement:

```python
calculate_progress(total, succeeded, failed) -> dict
ewma(values: Sequence[float], alpha: float = 0.25) -> float | None
estimate_remaining_requests(
    known_pending_pages: int,
    incomplete_orgs_without_known_next: int,
    completed_org_request_samples: Sequence[float],
) -> float
estimate_eta(
    remaining_requests: float,
    configured_rps: float,
    measured_rps: float | None,
    measured_at: datetime | None,
    completed_orgs: int,
    now: datetime,
) -> EtaEstimate
```

Use:

```text
remaining requests =
known pending pages
+ incomplete orgs with no known next page
  * max(1.0, EWMA requests per completed org)
```

Use measured RPS only when positive and sampled within 30 seconds. Apply uncertainty multipliers `0.65–1.55` for low, `0.80–1.30` for medium, and `0.90–1.15` for high confidence.

- [ ] **Step 4: Expose per-org samples from the staging store**

Add a query returning completed org duration, pages fetched, and request-equivalent pages in completion order. Keep calculation pure in `run_metrics.py`.

- [ ] **Step 5: Run focused tests**

Run:

```powershell
py -m pytest tests/test_run_metrics.py tests/test_store.py -q
```

Expected: all pass.

- [ ] **Step 6: Commit**

```powershell
git add src/geds_crawler/run_metrics.py src/geds_crawler/store.py tests/test_run_metrics.py tests/test_store.py
git commit -m "feat: calculate stable backfill progress and ETA"
```

---

### Task 7: Add overlay-aware, deduplicated reads

**Files:**

- Modify: `work/geds-crawler/src/geds_crawler/ui_queries.py`
- Modify: `work/geds-crawler/tests/test_ui_queries.py`

- [ ] **Step 1: Add failing overlay tests**

Create base and overlay DBs with one duplicate and one new person. Assert:

- base file hash is unchanged before/after query;
- total unique people is base + one;
- overlay version wins for duplicate `source_url`;
- filters, ordering, limit, and offset operate after deduplication;
- no contact fields appear.

- [ ] **Step 2: Run and confirm failure**

Run:

```powershell
py -m pytest tests/test_ui_queries.py -q
```

Expected: failure because `SnapshotReader` accepts one DB only.

- [ ] **Step 3: Add optional overlay paths**

Change construction to:

```python
SnapshotReader(
    base_db_path: Path | str,
    overlay_db_paths: Sequence[Path | str] = (),
)
```

For `people`, open an in-memory read connection, attach each source in SQLite
read-only mode, and query a union with precedence:

```sql
WITH all_people AS (
  SELECT 0 AS precedence, display_name, title, department_name,
         org_unit, org_path, source_url, last_seen
  FROM base.people_index
  UNION ALL
  SELECT 1 AS precedence, display_name, title, department_name,
         org_unit, org_path, source_url, last_seen
  FROM overlay_0.people_index
),
ranked AS (
  SELECT *,
         ROW_NUMBER() OVER (
           PARTITION BY source_url ORDER BY precedence DESC, last_seen DESC
         ) AS rn
  FROM all_people
)
SELECT display_name, title, department_name, org_unit, org_path, source_url
FROM ranked
WHERE rn = 1
```

Build all database aliases internally; never interpolate user input. Keep base-only queue/errors/status behavior explicit.

- [ ] **Step 4: Run focused tests**

Run:

```powershell
py -m pytest tests/test_ui_queries.py -q
```

Expected: all pass.

- [ ] **Step 5: Commit**

```powershell
git add src/geds_crawler/ui_queries.py tests/test_ui_queries.py
git commit -m "feat: read immutable snapshots with pagination overlays"
```

---

### Task 8: Expose backfill creation, telemetry, and per-org status through the API

**Files:**

- Create: `work/geds-crawler/src/geds_crawler/control_queries.py`
- Modify: `work/geds-crawler/src/geds_crawler/control_store.py`
- Modify: `work/geds-crawler/src/geds_crawler/ui_server.py`
- Modify: `work/geds-crawler/tests/test_control_api.py`

- [ ] **Step 1: Add failing API contract tests**

Test:

```json
POST /api/control/jobs
{
  "name": "Capped org backfill",
  "crawl_kind": "pagination_backfill",
  "source_db_path": "C:\\Users\\asele\\Documents\\geds-explorer\\outputs\\geds-snapshot-2026-07-08\\geds.sqlite",
  "rate_limit_seconds": 1.5,
  "traffic_policy": "queue",
  "output_dir": "outputs\\runs\\2026-07-09\\pagination-backfill"
}
```

The response must include `job_id`, `crawl_kind`, and `estimated_targets`. Reject missing/non-finished source DBs.

Assert every `/api/control/runs` backfill row contains:

```python
{
    "crawl_kind": "pagination_backfill",
    "progress": {
        "total_orgs": 1418,
        "completed_orgs": 200,
        "failed_orgs": 3,
        "terminal_orgs": 203,
        "percent": 14.3,
    },
    "pagination_metrics": {
        "pages_fetched": 812,
        "known_pending_pages": 17,
        "new_people": 14350,
        "deduped_people": 5075,
        "active_org": "OU=TEAM,OU=ISED-ISDE,O=GC,C=CA",
    },
    "eta": {
        "expected_seconds": 7200,
        "low_seconds": 5760,
        "high_seconds": 9360,
        "confidence": "high",
        "basis": "measured_rate",
        "estimated_finish_at": "2026-07-09T04:00:00+00:00",
    },
}
```

Also test:

```text
GET /api/control/runs/<run-id>/pagination-orgs?status=error&limit=50&offset=0
```

including bounded pagination and no contact values.

- [ ] **Step 2: Run and confirm failure**

Run:

```powershell
py -m pytest tests/test_control_api.py -q
```

Expected: contract failures.

- [ ] **Step 3: Implement read-only control query service**

Create `ControlQueries` to:

- resolve run output directories relative to the control DB;
- read staging telemetry in SQLite read-only mode;
- calculate measured rolling RPS from request-count samples/heartbeat data;
- call pure functions in `run_metrics.py`;
- return neutral metrics for queued runs whose staging DB does not yet exist;
- page/filter `pagination_orgs`;
- resolve base + overlay DBs for run-specific people views.

Keep DB discovery and telemetry SQL out of `ui_server.py`.

- [ ] **Step 4: Extend mutation validation**

In POST `/api/control/jobs`, parse and validate `crawl_kind`. For backfill, ignore department selection, require `source_db_path`, and return the frozen-target estimate. Preserve the existing unauthenticated-control warning on every mutation response and header.

- [ ] **Step 5: Extend run responses and route**

Use `ControlQueries.enrich_run(row)` for `/api/control/runs`. Add the per-org route before the general snapshot route. Return 404 for unknown run IDs and 400 for invalid status/limits.

- [ ] **Step 6: Wire overlay-aware people reads**

When a selected run is a backfill, construct `SnapshotReader(base_db, [overlay_db])`. For `run_id=all`, include successful/stopped backfill overlays after the immutable base and deduplicate by source URL.

- [ ] **Step 7: Run focused tests**

Run:

```powershell
py -m pytest tests/test_control_api.py tests/test_ui_server.py tests/test_ui_queries.py -q
```

Expected: all pass.

- [ ] **Step 8: Commit**

```powershell
git add src/geds_crawler/control_queries.py src/geds_crawler/control_store.py src/geds_crawler/ui_server.py tests/test_control_api.py
git commit -m "feat: expose pagination backfill telemetry API"
```

---

### Task 9: Render crawler type, stable progress, metrics, ETA, and details in the UI

**Files:**

- Modify: `work/geds-crawler/src/geds_crawler/ui_server.py`
- Modify: `work/geds-crawler/tests/test_ui_server.py`
- Modify: `work/geds-crawler/tests/test_control_api.py`

- [ ] **Step 1: Add failing HTML and payload-rendering tests**

Assert dashboard HTML contains stable element/test IDs:

```text
job-crawl-kind
job-source-db
run-progress-<run-id>
run-eta-<run-id>
pagination-orgs-panel
```

Add a browser-independent JavaScript formatting contract by keeping pure formatters in the page and asserting their source markers. API tests remain authoritative for numeric values.

- [ ] **Step 2: Run and confirm failure**

Run:

```powershell
py -m pytest tests/test_ui_server.py tests/test_control_api.py -q
```

Expected: failures for missing controls and telemetry markup.

- [ ] **Step 3: Extend the crawler creation form**

Add crawl type options:

```html
<select id="job-crawl-kind">
  <option value="full">Full crawl</option>
  <option value="pagination_backfill">Pagination backfill</option>
</select>
```

When backfill is selected:

- hide department checkboxes;
- require a completed source DB path;
- show target orgs, estimated requests, duration, people, and DB size;
- label estimates as planning ranges;
- send `crawl_kind` and `source_db_path`.

Show the agreed current planning estimates:

| Scenario | Requests | Duration at 1.5 s/request | New people | Total selected DB size |
|---|---:|---:|---:|---:|
| Minimum | ~2,800 | 1.2–1.4 h | ~30k | ~220 MiB |
| Expected | ~7,500 | 3.1–3.6 h | ~120k–160k | ~360–400 MiB |
| High | ~11,400 | 4.8–5.5 h | ~200k | ~420–460 MiB |

- [ ] **Step 4: Replace the runs table cells with crawler telemetry**

For backfill rows render:

- `Pagination backfill` badge;
- stacked success/error progress bar;
- `terminal / total orgs` and percent;
- pages fetched and pending;
- new and deduped people;
- measured/configured RPS;
- ETA range, confidence, finish time;
- heartbeat age;
- existing Stop/Resume buttons.

Compute widths from `completed_orgs / total_orgs` and `failed_orgs / total_orgs`. Do not use discovered page count as the main bar denominator.

- [ ] **Step 5: Add per-organization detail**

Clicking a backfill row loads `/pagination-orgs` and renders department, org path, status, pages, new people, deduped people, last page, and error/terminal reason. Add status filter and next/previous paging. Escape all text through the existing `escapeHtml`.

- [ ] **Step 6: Add ETA display helpers**

Implement pure JS helpers:

```javascript
function formatDurationRange(lowSeconds, highSeconds) {
  if (lowSeconds == null || highSeconds == null) return "Calculating ETA";
  return `${formatDuration(lowSeconds)}–${formatDuration(highSeconds)}`;
}
function formatHeartbeatAge(heartbeatAt) {
  if (!heartbeatAt) return "No heartbeat";
  const seconds = Math.max(0, Math.floor((Date.now() - Date.parse(heartbeatAt)) / 1000));
  return `${formatDuration(seconds)} ago`;
}
function formatRunEta(eta) {
  const range = formatDurationRange(eta.low_seconds, eta.high_seconds);
  const confidence = eta.confidence || "low";
  return `${range} · ${confidence} confidence`;
}
```

Render `Calculating ETA · low confidence` when expected seconds is null. Never display `NaN`, negative time, or a finish timestamp from a stale run.

- [ ] **Step 7: Run focused tests**

Run:

```powershell
py -m pytest tests/test_ui_server.py tests/test_control_api.py -q
```

Expected: all pass.

- [ ] **Step 8: Commit**

```powershell
git add src/geds_crawler/ui_server.py tests/test_ui_server.py tests/test_control_api.py
git commit -m "feat: show backfill progress and ETA in crawler UI"
```

---

### Task 10: Full regression, privacy audit, and bounded live verification tooling

**Files:**

- Create: `work/geds-crawler/scripts/verify_pagination_backfill.py`
- Create: `work/geds-crawler/tests/test_verify_pagination_backfill.py`
- Modify: `work/geds-crawler/README.md`

- [ ] **Step 1: Add a failing verification-script test**

The script must accept:

```text
--base-db
--overlay-db
--expected-org-dn (exactly two occurrences)
```

and emit JSON with string `base_sha256_before`/`base_sha256_after`, boolean
`base_unchanged`, an `organizations` array containing `org_dn`,
`pages_fetched`, `unique_people`, `exceeds_25`, and `status`, plus boolean
`contact_columns_present` and integer `duplicate_source_urls`.

Tests use temporary fixture DBs; they must not access the network.

- [ ] **Step 2: Run and confirm failure**

Run:

```powershell
py -m pytest tests/test_verify_pagination_backfill.py -q
```

Expected: failure because the script does not exist.

- [ ] **Step 3: Implement the read-only verifier**

Hash the base before and after all queries. Inspect `PRAGMA table_info(people_index)` for contact columns. Count unique person `source_url`s per selected org and duplicate URLs in the overlay. Exit non-zero if:

- base hash changes;
- either org is missing or non-terminal;
- neither org exceeds 25 people;
- contact columns exist;
- duplicate source URLs exist.

- [ ] **Step 4: Document operator workflow**

In `README.md`, document:

1. Upgrade/init the control schema.
2. Create a `pagination_backfill` job from a completed base DB.
3. Use a two-org frozen seed for the first live run.
4. Start, stop during a continuation page, and resume.
5. Run the verifier.
6. Review UI progress monotonicity, ETA, errors, and base hash.
7. Only then create the 1,418-org production run.

State that GEDS and TBS employee totals are different populations and should not be forced to equality.

- [ ] **Step 5: Run the complete automated suite**

Run:

```powershell
py -m pytest -q
```

Expected: all tests pass.

- [ ] **Step 6: Run static repository checks**

Run:

```powershell
rg -n "TODO|FIXME|pass\\s*$|NotImplementedError" src tests scripts
git diff --check
```

Expected: no newly introduced placeholders, whitespace errors, or conflict markers. Existing intentional `pass` statements must be reviewed individually.

- [ ] **Step 7: Run the bounded live verification only after explicit operator approval**

Use the UI to create a two-org backfill at the default aggregate rate. Stop after a continuation page is visible, resume, then run:

```powershell
$baseDb = Resolve-Path "outputs/geds-snapshot-2026-07-08/geds.sqlite"
$overlayDb = Resolve-Path "outputs/runs/2026-07-09/two-org-backfill/geds.sqlite"
py scripts/verify_pagination_backfill.py `
  --base-db $baseDb `
  --overlay-db $overlayDb `
  --expected-org-dn "OU=FIRST-CAPPED-ORG,O=GC,C=CA" `
  --expected-org-dn "OU=SECOND-CAPPED-ORG,O=GC,C=CA"
```

Expected: exit code 0, `base_unchanged=true`, and at least one `exceeds_25=true`.

- [ ] **Step 8: Final acceptance review**

Verify against the design:

- future full crawls follow actual next links;
- backfill uses an isolated overlay and frozen target list;
- fixed-denominator progress never regresses;
- ETA includes range, confidence, basis, and finish time;
- stop/resume is idempotent;
- UI exposes type, progress, metrics, ETA, heartbeat, and org details;
- no person-detail requests or contact fields were introduced;
- the production backfill has not been auto-started.

- [ ] **Step 9: Commit**

```powershell
git add scripts/verify_pagination_backfill.py tests/test_verify_pagination_backfill.py README.md
git commit -m "docs: add pagination backfill verification workflow"
```
