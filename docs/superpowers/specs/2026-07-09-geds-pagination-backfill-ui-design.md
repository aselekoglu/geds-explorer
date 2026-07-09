# GEDS Person Pagination Backfill and UI Design

## Objective

Remove the current 25-person-per-organization-page ceiling without repeating
the full organization crawl, expose the backfill as a managed crawler in the
existing control UI, and provide stable progress and evidence-based ETA
metrics.

The completed base crawl remains immutable. Pagination backfill data is stored
as a separate overlay and combined with base data by person `source_url`.
Future full crawls use the same pagination implementation automatically.

## Current Evidence

The completed crawl contains:

- 156 departments;
- 26,421 organization units;
- 154,863 captured person records;
- 1,418 organization units with exactly 25 captured people;
- 35,450 people in those capped units.

No organization contains more than 25 people. The parser reads person links
from one organization page, while the crawler has no person-list pagination
queue. The TBS comparison also shows coverage degrading materially with
organization size. These signals justify treating the 25-person boundary as a
pagination defect.

## Scope

This change includes:

1. A reusable parser for the next person-list page or cursor.
2. A resumable pagination queue.
3. A managed `pagination_backfill` job type.
4. A one-time backfill seeded from the 1,418 capped organization units.
5. Native pagination in future normal crawls.
6. Overlay-aware person reads and analysis.
7. UI progress, ETA, metrics, stop, and resume support.
8. Automated tests and a bounded live verification run.

This change does not:

- fetch person-detail pages;
- store phone, email, fax, or address data;
- mutate completed base crawl databases;
- assume that GEDS directory counts equal TBS employee population;
- start the production backfill automatically.

## Architecture

### Shared Pagination Component

Add one pagination component used by both full crawls and backfills. Given a
fetched organization/person-list page, it returns:

- parsed person index records;
- a canonical next-page URL or cursor when present;
- a terminal result when no next page exists.

Pagination links are allowlisted to the official GEDS host and expected GEDS
path. The component canonicalizes URLs and rejects cursor cycles.

The crawler must follow the source-provided next-page link. It must not guess
page numbers merely because a page contains 25 people.

### Backfill Seed

The backfill seed is a frozen list of organization units whose completed base
snapshot contains exactly 25 people. Each seed records:

- organization DN and source URL;
- department DN and name;
- organization name and path;
- base source database identifier;
- seed creation timestamp.

The seed is persisted with the run configuration so resume behavior and audit
results do not depend on a later-changing base snapshot.

### Isolated Overlay Storage

Every pagination backfill writes to an isolated run directory:

```text
outputs/runs/<date>/<backfill-name>/
  geds.sqlite
  worker.stdout.log
  worker.stderr.log
  crawl_report.md
  run-manifest.json
```

The backfill database stores:

- the existing `people_index` shape;
- `pagination_orgs`;
- `people_page_queue`;
- `crawl_runs`;
- `crawl_errors`.

`pagination_orgs` tracks one row per target organization:

- org and department identifiers;
- status;
- pages fetched;
- people observed;
- people inserted;
- people already known;
- last page URL;
- started, heartbeat, and finished timestamps;
- terminal or error reason.

`people_page_queue` tracks one row per page:

- canonical page URL or cursor;
- organization DN;
- page index;
- status and attempts;
- discovered-from page;
- last error;
- first-seen and completed timestamps.

Completed base crawl databases are never rewritten. Overlay-aware readers union
base and successful backfill records and deduplicate people by canonical
`source_url`. When the temporal master is implemented, the same overlay is
eligible for a normal transactional merge.

### Managed Job Type

Extend control-plane jobs and runs with a `crawl_kind`:

- `full`
- `pagination_backfill`

The existing process manager, traffic policies, stop/resume behavior, logs,
heartbeats, and schedules remain shared. No separate copied crawler engine is
introduced.

The UI can create a pagination backfill from a selected completed source set.
The default builder selects every organization at the observed 25-person
ceiling. The UI shows the seed count and estimated cost before the run can be
started.

## Runtime Flow

For each target organization:

1. Fetch its first organization page again because raw HTML was not retained.
2. Parse people and upsert them into the overlay.
3. Detect the actual next-page link.
4. If no next link exists, mark the organization complete.
5. If a next link exists, enqueue and fetch it.
6. Continue one page at a time until no next link remains.
7. Mark the organization complete only after its terminal page commits.

The worker checks cooperative stop state between page requests. Resume leaves
completed organizations and pages untouched and continues pending or retryable
work.

## Progress Model

### Stable Main Progress

The main progress bar is:

```text
completed target organizations / total target organizations
```

For the current seed the denominator is fixed at 1,418. This progress never
regresses when a newly fetched page discovers another page.

An organization counts as completed only when:

- a terminal page without a next link commits successfully; or
- it reaches a terminal error state that the UI counts separately as failed.

The bar visually separates successful and failed terminal organizations.
Pending and active organizations remain unfilled.

### Supporting Metrics

Each run exposes:

- target organizations;
- completed organizations;
- failed organizations;
- active organization;
- pages fetched;
- currently known pending pages;
- new people inserted;
- existing/deduplicated people;
- configured RPS;
- measured rolling RPS;
- ETA range;
- ETA confidence;
- estimated finish time;
- heartbeat age.

## ETA Model

ETA uses an exponentially weighted moving average over completed organizations.
Each completed organization contributes its observed remaining work:

- requests used;
- pagination depth;
- elapsed active time.

Estimated remaining requests are:

```text
known pending page requests
+ incomplete organizations without a known next page
   * EWMA additional pages per completed organization
```

Estimated duration divides remaining requests by measured rolling RPS when the
measurement is fresh. Otherwise it uses configured RPS.

The API returns:

- expected seconds;
- low and high seconds;
- confidence: `low`, `medium`, or `high`;
- calculation basis: `configured_rate` or `measured_rate`.

Confidence thresholds:

- fewer than 50 completed organizations: low;
- 50 through 199: medium;
- 200 or more: high.

The range remains deliberately wide at low confidence. The UI renders, for
example:

```text
ETA 2h 20m–3h 10m · medium confidence
Expected finish 12:45 AM
```

## UI Design

### Crawlers Tab

Pagination backfills appear in the existing crawler list with a visible
`Pagination backfill` type badge. A running row shows:

- stable progress bar and percent;
- `completed / target orgs`;
- pages fetched;
- new people;
- pending pages;
- measured RPS;
- ETA range and confidence;
- heartbeat;
- stop action.

Stopped or failed rows expose resume when resumable state exists.

### Run Detail

Selecting the run opens its existing snapshot views plus a pagination status
view. The status view lists target organizations with:

- department and org path;
- status;
- pages fetched;
- new and deduplicated people;
- last page;
- error or terminal reason.

No contact values are returned.

### New Crawler Form

The form supports `Pagination backfill` as a job type. Before creation it shows
the frozen estimate:

- target orgs: 1,418;
- estimated requests: approximately 7,500;
- estimated duration at 1.5 seconds/request: 3.1–3.6 hours;
- estimated additional people: 120k–160k;
- estimated additional database size: 180–220 MiB.

These are planning estimates, not guarantees. The live ETA replaces them after
the run starts.

## API Changes

Existing run endpoints remain authoritative. Their run payloads gain:

- `crawl_kind`;
- `progress`;
- `pagination_metrics`;
- `eta`.

`progress` contains fixed-denominator organization totals and percentage.
`pagination_metrics` contains page and person counters. `eta` contains expected,
low, high, confidence, basis, and estimated finish time.

Add a read-only endpoint for per-organization backfill status:

```text
GET /api/control/runs/<run-id>/pagination-orgs
```

Job creation continues through the existing mutation endpoint with
`crawl_kind=pagination_backfill` and an explicit completed source selection.

## Safety and Error Handling

- Default rate remains aggregate 1 request/second unless the operator chooses a
  slower interval.
- Existing queue/shared/independent traffic policies apply.
- Next-page links must remain on the official GEDS origin and GEDS path.
- Canonical page URLs prevent duplicate page requests.
- A visited-cursor set prevents pagination loops.
- Default maximum is 500 pages per organization.
- Reaching the page limit produces a visible terminal error, not silent
  completion.
- Page writes and queue transitions commit atomically.
- Logging failures cannot change an already-committed page status.
- Retry exhaustion preserves resumable state.
- Person rows remain contact-free and person-detail pages remain prohibited.

## Cost Model

For the current 1,418-target seed:

| Scenario | Requests | Duration at 1.5 s/request | New people | Final people | Total selected DB size |
|---|---:|---:|---:|---:|---:|
| Minimum | ~2,800 | 1.2–1.4 h | ~30k | ~185k | ~220 MiB |
| Expected | ~7,500 | 3.1–3.6 h | ~120k–160k | ~275k–315k | ~360–400 MiB |
| High | ~11,400 | 4.8–5.5 h | ~200k | ~355k | ~420–460 MiB |

The expected request count includes refetching 1,418 first pages because raw
HTML was not saved. TBS population gaps inform the people range but do not imply
that GEDS and TBS totals should become equal.

## Testing

### Parser

- page with fewer than 25 people and no next link;
- exactly 25 people and no next link;
- exactly 25 people with a valid next link;
- relative and absolute next links;
- off-origin or malformed next links;
- duplicate person and next-page links.

### Worker and Storage

- multi-page organization reaches terminal completion;
- page and person upserts are idempotent;
- stop and resume preserve completed pages;
- retry exhaustion preserves resumable state;
- cursor cycle becomes a visible error;
- maximum-page guard becomes a visible error;
- completed base databases remain byte-for-byte untouched;
- overlay union deduplicates by source URL.

### ETA

- configured-rate fallback before measured samples;
- EWMA update from completed organizations;
- low, medium, and high confidence thresholds;
- progress never decreases when a next page is discovered;
- range and finish timestamp are deterministic under a fixed clock.

### API and UI

- job creation persists `crawl_kind` and frozen seed;
- run payload exposes progress, pagination metrics, and ETA;
- per-org status filtering and pagination;
- progress bar, ETA, and metrics render for active and completed runs;
- stop and resume actions use existing POST endpoints;
- no contact fields are exposed.

### Live Verification

Before the production backfill:

1. Run against two known capped organizations.
2. Confirm at least one organization retrieves more than 25 unique people.
3. Stop and resume during a continuation page.
4. Confirm the progress bar never regresses.
5. Compare stored people with the visible terminal page.
6. Confirm base databases are unchanged.

The full 1,418-organization backfill starts only after this verification is
reviewed.

## Acceptance Criteria

- Future full crawls follow every valid person-list page.
- The backfill is visible and controllable in the existing UI.
- Progress is based on a fixed target-org denominator and never regresses.
- ETA shows a range, confidence, and expected finish time.
- Stop/resume is lossless and idempotent.
- Completed base databases are not mutated.
- Overlay-aware reads expose newly captured people without duplicates.
- At least one live capped-org verification exceeds 25 captured people.
- Privacy constraints remain unchanged.
