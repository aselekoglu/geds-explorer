# Canonical Snapshot Data and Person History Design

## Status and objective

Approved design. This work makes Snapshot Data a story-first browser for one
authoritative, current GEDS dataset and its change history. It replaces the
ambiguous run selector with a deterministic canonical snapshot pointer. The
screen must show what the data means now, how it changed since the preceding
trusted global state, and let an operator browse both the current records and
person-level movements.

The current implementation does **not** yet provide this model. Its `all`
selection combines the imported nine-department snapshot with pagination
overlays, but omits the other full-crawl bases. As observed on 2026-07-09 this
returned 108,777 people, while the verified completed pagination lineage
returned 193,297 unique people. The existing SQLite files only have a current
`people_index`; they have no snapshot manifests or person change events.

## Product decisions

- Snapshot Data has no data-source picker. It always browses the current
  canonical snapshot.
- A canonical snapshot is an immutable manifest, not a copied full SQLite
  database. It has a parent manifest, an as-of time, coverage and quality
  totals, a deterministic source lineage, and a content fingerprint.
- Only a complete, validated global dataset may become canonical. A failed,
  stopped, partial, or unverified run never advances the current pointer or
  counts as a person absence.
- The initial migrated state is the baseline. History starts with the next
  complete canonical snapshot; the system never invents pre-baseline events.
- The UI is story-first: current total and as-of time, headline changes versus
  the parent snapshot, coverage/change visuals, and direct paths to browse
  people, organizations, and changes.

## Storage model

Create `outputs/master/geds-master.sqlite`; it is the history source of truth.
It stores current rows plus append-only deltas, rather than repeated full
snapshots.

### Canonical manifests

`canonical_snapshots`

- `snapshot_id`, `parent_snapshot_id`, `created_at`, `as_of_at`, `status`
- `people_count`, `org_units_count`, `departments_count`, coverage and quality
  metrics
- `source_fingerprint`, `merge_fingerprint`, and `baseline` flag

`canonical_snapshot_members`

- `snapshot_id`, `run_id`, resolved database path, role (`base` or `overlay`),
  precedence, and source checksum

This preserves exactly how a result was constructed without copying all person
rows. The current snapshot is a single transactional pointer in the master DB.
It moves only after the manifest and every member validate successfully.

### Current entities and events

`people_current` has one row per currently known person, their current title,
org, department, last seen snapshot/time, content hash, missing streak, and
status. The existing stable `source_url` is the initial strong identity key;
when the crawler exposes a canonical person DN, it becomes the preferred
identity key. A new URL/DN is never silently merged to an existing person.

`person_change_events` is append-only and indexed by both
`(person_key, occurred_at)` and `(snapshot_id, event_type)`. Each event records
the canonical snapshot, event time, certainty, and compact before/after values
for the affected fields. Supported event types are:

- `joined`
- `title_changed`
- `org_changed`
- `department_changed`
- `missing_once`
- `departed`
- `reappeared`
- `possible_move`

`possible_move` links a newly observed identity to a newly missing identity
only as an uncertain candidate when normalized name and department match. A
title, org, or department change is certain only when the strong person key is
unchanged.

## Canonicalization and diff lifecycle

1. Resolve a prospective global dataset from the completed run graph. For a
   pagination backfill, use every base path from `run_pagination_seeds` plus its
   final overlay; do not use the old `all` shortcut.
2. Validate that every included department is complete and error-free for the
   intended scope, that all sources exist, and that deduplication by stable
   person identity succeeds.
3. In one transaction, compare the resolved rows to `people_current` through
   indexed identity and content hashes. Update `people_current` and append only
   the resulting change events.
4. First absence in a complete, error-free scope yields `missing_once` and
   `uncertain_missing`. A second consecutive eligible absence yields
   `departed`. Partial, failed, or stopped work does not advance this state.
5. Write the immutable manifest and members, verify aggregate counts against
   the resolved view, then atomically set `current_snapshot_id`.
6. If any step fails, retain source staging data, record the failed merge, and
   leave the current pointer and history unchanged.

The complexity is `O(current entities + change events + small manifest
metadata)`, rather than `O(current entities × snapshot count)`. A 193k-person
canonical state stays as one current table; a refresh in which 1% of people
change appends roughly 1.9k events, not another 193k-row snapshot. Each global
refresh still performs an indexed comparison against the current rows, which is
appropriate for SQLite at this scale.

## Snapshot Data experience

The default route reads only `current_snapshot_id` and presents:

1. **Current dataset:** as-of time, unique people, organizations, departments,
   coverage and data-quality state.
2. **What changed:** counts and trends for joins, title/org/department changes,
   possible moves, uncertain missing records, and confirmed departures versus
   the parent canonical snapshot.
3. **Where it changed:** the departments and organizations with the largest
   movements, with links to filtered browse views.
4. **Browse current data:** current people and organizations, retaining search
   and department filters. A person row opens an event timeline showing dates,
   event type, before/after position, source snapshot, and certainty.
5. **Trust details:** a read-only drawer for parent snapshot, included runs,
   coverage, checksums, and warnings. It explains the result but cannot switch
   the dataset.

The data-source selector is removed from this route. Historical manifests may
be exposed later through a separate audit/history route, never by silently
changing the default browse dataset.

## Git-compatible audit and retention

SQLite files and person-level event rows stay out of Git. For every successful
canonicalization, generate small audit artifacts containing the manifest ID,
parent ID, hashes, aggregate change counts, and source lineage. A private audit
repository may commit those artifacts. Do not commit raw person-level JSONL by
default: it duplicates the master DB, increases retention cost, and is less
privacy-efficient. Staging databases can be deleted after a successful verified
merge when recovery policy permits; the manifest and change events remain.

## Verification criteria

- A regression test proves the current canonical resolver includes every base
  recorded in `run_pagination_seeds`; the tested count equals the deduplicated
  canonical count, not the old 108,777 partial view.
- A baseline snapshot emits no invented historical movement.
- Tests cover joined, title/org/department changes, missing-once,
  departed-on-second-eligible-miss, reappeared, partial-crawl suppression, and
  uncertain possible moves.
- A failed validation or merge leaves `current_snapshot_id`, `people_current`,
  and committed event history untouched.
- UI tests assert that Snapshot Data has no source picker, shows current
  manifest/as-of metadata, and a person timeline renders before/after values
  and certainty.
