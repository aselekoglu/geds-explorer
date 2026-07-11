# GEDS Career Atlas Implementation Progress

Branch: codex/geds-career-atlas
Worktree: C:\Users\asele\Documents\geds-explorer\.worktrees\geds-career-atlas
Plan: docs/superpowers/plans/2026-07-10-geds-career-atlas-constellation.md

## Baseline

- 2026-07-10: py -m pytest -q
- Result: 98 passed in 15.52s

## Task 1 — Terminal overlay resolution and per-organization fallback

Status: verified

Implemented:

- accepts both completed and historical finished organization success states;
- treats failed as terminal with an explicit base-fallback warning;
- rejects non-terminal pending/running states;
- replaces base people and organization metadata only for successful targets;
- discards partial overlay rows and preserves complete base rows for failed targets;
- deterministically deduplicates people, organizations, and departments.

RED evidence:

- tests/test_canonical_resolver.py: finished and failed-fallback tests failed against the strict completed-only validator;
- tests/test_canonical_projection.py: four tests failed because canonical_projection did not exist.

GREEN evidence:

- py -m pytest tests/test_canonical_resolver.py tests/test_canonical_projection.py -v
- Result: 13 passed in 1.05s
- py -m pytest -q
- Result: 103 passed in 13.90s

Implementation note:

- apply_patch resolves paths from the primary checkout, not a shell workdir. All implementation patch paths must therefore start with .worktrees/geds-career-atlas/ while this worktree is active.

Next:

- Task 2: derive and validate the canonical LDAP hierarchy.

## Task 2 — DN-derived canonical hierarchy

Status: verified

Implemented:

- parses DN suffixes without splitting escaped commas;
- handles even/odd backslash escaping at separators;
- assigns the nearest known suffix as parent and ignores stored parent/path;
- skips absent intermediate DNs without inventing nodes;
- generates stable case-insensitive URL-safe organization IDs;
- derives canonical paths and depths through memoized parent traversal;
- reports roots, missing parents, cycles, and maximum depth.

RED evidence:

- py -m pytest tests/test_canonical_hierarchy.py -v
- Result: collection failed because canonical_hierarchy did not exist.

GREEN evidence:

- py -m pytest tests/test_canonical_hierarchy.py -v
- Result: 7 passed in 1.59s
- Real lineage: 26421 organizations, 156 roots, 0 missing parents, 0 cycle nodes, maximum depth 12.
- py -m pytest -q
- Result: 110 passed in 14.16s

Next:

- Task 3: materialize canonical current departments, organizations, people, source lineage, and quality.

## Task 3 — Canonical current projection and source lineage schema

Status: verified

Implemented:

- immutable canonical source, department, organization, person, and quality types;
- snapshot quality status, warnings, fallback count, and hierarchy metrics;
- true canonical_snapshot_sources lineage records;
- departments_current and organizations_current projections;
- expanded people_current organization, department, canonical path, and freshness fields;
- transactional replace_current_projection and pointer rollback;
- read-only current manifest and decoded quality warnings;
- parent/name, department/depth, org/title, and department indexes;
- legacy people_current column migration before index creation.

RED evidence:

- initial canonical-store collection failed because new immutable types were absent;
- after adding types, five tests failed for missing schema/store methods;
- the legacy upgrade test failed with sqlite3.OperationalError because indexes were created before migrated columns.

GREEN evidence:

- py -m pytest tests/test_canonical_store.py -v
- Result: 13 passed in 0.34s
- py -m pytest -q
- Result: 117 passed in 15.89s

Compatibility note:

- canonical_snapshot_members and replace_current_people remain temporarily for the pre-Task-4 canonicalizer tests. Task 4 moves publication to canonical_snapshot_sources plus replace_current_projection before legacy cleanup.

Next:

- Task 4: publish the real canonical baseline atomically through the new projection.

## Task 4 — Real canonical publication command and baseline

Status: verified

Implemented:

- publish_canonical resolves one terminal run, applies safe per-organization overlay fallback, derives and validates hierarchy, and promotes one atomic current projection;
- canonical source files are recorded with roles, precedence, and SHA-256 checksums;
- normalized source lineage and projected entities contribute to a deterministic snapshot fingerprint;
- promotion records joined, changed, possible-move, missing, departed, and reappeared person events while retaining stable source-url identity;
- failed partial overlays remain visible as partial_overlay warnings instead of silently replacing good base rows;
- geds-career publish CLI emits a machine-readable canonical manifest and returns a nonzero code for invalid input;
- generated master databases and future frontend build/test artifacts are ignored.

RED evidence:

- focused canonicalizer tests initially had three failures for absent source lineage, absent partial-overlay quality, and missing reappeared-person restoration;
- test_career_cli.py initially failed during collection because geds_crawler.career_cli did not exist.

GREEN evidence:

- py -m pytest tests/test_canonicalizer.py tests/test_career_cli.py -v
- Result: 7 passed in 0.73s.
- py -m pytest -q
- Result: 121 passed in 18.65s.

Real baseline publication:

- Source run: 769b7b73-dc8e-4911-b1d5-80cbe07e34f8 at 2026-07-09T07:05:04.674049+00:00.
- Snapshot: edd5d0f4269da97163b33a5cf7dd8c850ad51331a913721e0ce7a07e1977fce5.
- 193163 unique people, 26421 organizations, 156 departments, and 6 recorded source databases.
- 156 roots, maximum depth 12, 0 missing parents, and 0 cycles.
- Quality partial_overlay with 4 named fallback organizations.
- Independent read-only verification: PRAGMA integrity_check returned ok, foreign_key_check returned 0 violations, and people_current contained 193163 distinct source URLs with 0 empty organization DNs.

Next:

- Task 5: implement the versioned bilingual taxonomy and noisy-text normalization with explainable category evidence.

## Task 5 — Versioned bilingual taxonomy and normalization

Status: verified

Implemented:

- versioned 1.0.0 taxonomy with all ten approved career-category IDs;
- English and French labels, phrases, synonyms, abbreviations, exclusions, and reviewed positive/negative examples for every category;
- Unicode NFKD, casefold, diacritic, whitespace, and punctuation normalization used only for comparison;
- deterministic bilingual query interpretation with sorted category IDs, expanded related terms, and human-readable match evidence;
- load-time guards for duplicate IDs, empty bilingual fields, normalized positive collisions, and positive/exclusion collisions;
- immutable taxonomy and interpretation models so repeated queries produce reproducible outputs.

Data-preservation rule:

- crawled titles and organization names remain unchanged; normalization creates comparison keys and never overwrites source strings.

RED evidence:

- py -m pytest tests/test_career_taxonomy.py -v
- Result: collection failed with ModuleNotFoundError for geds_crawler.career_taxonomy.

GREEN evidence:

- py -m pytest tests/test_career_taxonomy.py -v
- Result: 15 passed in 0.16s.
- py -m pytest -q
- Result: 136 passed in 15.97s.

Next:

- Task 6: score title, organization, and ancestor evidence with deterministic weights, explicit exclusions, and a fixed bilingual evaluation set.

## Task 6 — Explainable deterministic matcher and fixed evaluation set

Status: verified

Implemented:

- immutable entity, evidence, match, evaluation-case, and evaluation-report models;
- deterministic weights: title phrase/abbreviation 100, organization phrase/abbreviation 85, title synonym 70, organization synonym 55, and ancestor evidence 25;
- visible source-field evidence for every score, with duplicate phrase/source evidence counted once;
- per-category exclusions that suppress ambiguous matches and record the exact excluded phrase and source field;
- ancestor-only matches capped at score 60 and medium confidence;
- a checked-in 40-case bilingual fixture: four reviewed cases per taxonomy category covering English, French, abbreviation/deep-ancestor, and ambiguous-negative paths;
- evaluation report gates expected categories, minimum confidence, forbidden categories, and precision-at-10 where a future fixture has at least ten positives for a category.

RED evidence:

- py -m pytest tests/test_career_matcher.py -v
- Result: collection failed with ModuleNotFoundError for geds_crawler.career_matcher.

GREEN evidence:

- py -m pytest tests/test_career_matcher.py -v
- Result: 6 passed in 0.05s; all 40 reviewed fixture cases pass.
- py -m pytest -q
- Result: 142 passed in 16.46s.

Next:

- Task 7: build the snapshot-versioned FTS index and explicitly label GEDS vacancy signals as unverified source observations.

## Task 7 — Snapshot-versioned FTS index and recorded vacancy signals

Status: verified

Implemented:

- atomic FTS5 index build for current organizations and present people, with normalized comparison fields retained alongside source display fields;
- career entity, FTS, per-category explainable match, vacancy signal, and singleton index-state tables;
- transactional next-table validation and swap so a failed rebuild leaves the previous public index state usable;
- career index state bound to one canonical snapshot and taxonomy version;
- CLI index command with a machine-readable build manifest;
- conservative vacancy parser accepting only placeholder-shaped names, not job titles such as Vacancy Planning Officer;
- vacancy rows hold source text, role title, organization ID, snapshot ID, confidence, and reasons only: no contact, application-status, or application-URL fields.

RED evidence:

- py -m pytest tests/test_career_index.py -v
- Result: collection failed with ModuleNotFoundError for geds_crawler.career_index.

GREEN evidence:

- py -m pytest tests/test_career_index.py -v
- Result: 9 passed in 0.53s, including CLI output, failed-rebuild preservation, and conservative vacancy tests.
- py -m pytest -q
- Result: 150 passed in 17.51s before the final CLI assertion was added.

Real index build:

- Snapshot edd5d0f4269da97163b33a5cf7dd8c850ad51331a913721e0ce7a07e1977fce5, taxonomy 1.0.0.
- 219584 entities: 26421 organizations and 193163 people.
- 170415 persisted explainable category matches and 18 high-confidence GEDS vacancy signals.
- Independent read-only verification: integrity_check ok, 0 foreign-key violations, 219584 FTS rows, and no contact/application columns in vacancy_signals.
- The earlier 17-signal expectation was a pre-build estimate. Source-lineage inspection found 18 distinct person source URLs/DNs; similar titles remain separate when GEDS exposes distinct records.
- Full production indexing duration was 167.6 seconds; it is a refresh-time offline job, never a public request-path operation.

Next:

- Task 8: implement bounded, read-only repository queries over the indexed canonical snapshot.

## Task 8 — Bounded read-only repository queries

Status: verified

Implemented:

- mode=ro SQLite connections with query_only and bounded busy timeout;
- snapshot-aware meta, explainable category search, department list, child navigation, ancestor lineage, safe team profile, roles, constellation, and tour queries;
- ordinary pages capped at 200 and constellation slices capped at 2000;
- every response carries current snapshot ID, quality status, and deterministic ETag derived from snapshot plus normalized arguments;
- only role/title, organization, hierarchy, category-evidence, and aggregate fields cross the boundary; contact, source URL, and crawler-control fields do not;
- stable tie ordering by score then entity ID.

RED evidence:

- py -m pytest tests/test_career_repository.py -v
- Result: collection failed with ModuleNotFoundError for geds_crawler.career_repository; later navigation tests failed while the planned query methods were absent.

GREEN evidence:

- py -m pytest tests/test_career_repository.py -v
- Result: 6 passed in 0.57s, covering ranking, caps, read-only connection enforcement, navigation, and privacy.
- py -m pytest -q
- Result: 157 passed in 15.60s.

Next:

- Task 9: expose only this repository through a separate FastAPI public application.

## Task 9 — Separate read-only FastAPI application

Status: verified

Implemented:

- separate GEDS Career Atlas FastAPI app factory backed only by CareerRepository;
- public meta, search, department, org-walk, role, constellation, and tour routes;
- no crawler, job, schedule, or control-plane routes;
- same-origin Content-Security-Policy, nosniff, and strict referrer headers without wildcard CORS;
- response ETags forwarded from immutable snapshot-aware repository results;
- pinned FastAPI, Uvicorn, and HTTPX dependencies;
- geds-career serve defaults to 127.0.0.1:8780 and refuses missing master/index state with exit code 2.

RED evidence:

- py -m pytest tests/test_career_api.py -v
- Result: collection failed with ModuleNotFoundError for geds_crawler.career_api.

GREEN evidence:

- py -m pytest tests/test_career_api.py -v
- Result: 6 passed in 0.77s, including control-route isolation, headers, caps, and missing-master refusal.
- py -m pytest -q
- Result: 163 passed in 16.62s.

Next:

- Task 10: create the separate public React application and visual system.

## Task 10 — Separate React application and visual system

Status: verified

Implemented:

- separate React 19 + Vite public application, with a committed dependency lockfile;
- accessible public shell with skip link and no crawler-control actions;
- dark civic-tech visual system: navy surface tokens, cyan focus/selection, star-field constellation canvas, responsive sidebar, filter rail, and detail inspector;
- selected constellation node is interactive and updates the public inspector state;
- responsive collapse preserves the public explorer surface without exposing admin UI.

Visual reference:

- generated and inspected a full-screen Constellation concept before implementation; its navigation hierarchy, central constellation, filter rail, and right-side hierarchy/detail inspector informed the shell.

Verification:

- npm.cmd test -- --run src/app/App.test.tsx: 1 passed.
- npm.cmd run typecheck: passed.
- npm.cmd run build: passed; dist includes index.html and hashed CSS/JS assets.

Next:

- Task 11: add typed public API client and shareable explorer URL state.

## Task 11 — Typed API client and shareable URL state

Status: verified

Implemented:

- strict Zod schema for query, categories, department, organization, confidence, vacancy, language, mode, and focus;
- deterministic/default-safe parsing for incomplete URL state;
- typed client with encoded query parameters, AbortSignal support, and typed non-2xx errors;
- minimum validated public response contracts for snapshot-aware meta and explainable search.

Verification:

- npm.cmd test -- --run src/api/client.test.ts src/state/explorerSearch.test.ts: 2 passed.
- npm.cmd run typecheck: passed.

Next:

- Task 12: build the Discover journey over real explainable API search results.

## Current verification snapshot

- Frontend: 9 Vitest files passed; TypeScript typecheck and Vite production build passed.
- Python: 163 tests passed.
- Vite foreground startup verified readiness at 127.0.0.1:5174; persistent background launch is terminated by this sandbox host-process lifecycle, so browser screenshot QA remains explicitly outstanding.

## Task 12 — Discover and explainable ranked results

Status: verified

Implemented and verified vertical slice:

- Discover result surface renders interpreted AI interest language, accessible result articles, confidence, and the first explainable evidence records;
- vacancy language is exactly "Recorded as vacant in GEDS — unverified" and no application action is present.
- npm.cmd test -- --run src/features/discover/DiscoverPage.test.tsx: 1 passed.
- npm.cmd test: 4 passed; npm.cmd run typecheck and npm.cmd run build: passed.
- Debounced query state updates the browser URL and uses one memoized public API client.

Next:

- connect the Discover surface to URL state and real public API data, then add no-match/loading/partial-quality states.

## Tasks 13â€“16 â€” Org Walk, team evidence, and required Constellation

Status: in progress; functional vertical slice verified

Implemented:

- bounded `/api/constellation/slice` contract with root/focused hierarchy reads, depth validation, a 2,000-node cap, truncation status, snapshot binding, and deterministic ETags;
- API-backed multi-column Organization Walk with keyboard traversal and responsive one-column fallback;
- API-backed team profile and observed-title surface with explicit non-job language and no Apply action;
- deterministic D3 circle-pack layout sized by descendant people indexed, stable ordering, cyan selected state, keyboard-selectable SVG nodes, and a synchronized accessible list;
- URL-backed `q` and `focus` state shared by search, Constellation, Org Walk, and the right-side profile inspector;
- Constellation overview preserves all 156 root institutions as marks while directly labeling only sufficiently large circles; focus and branch drill-down are separate actions;
- interest queries switch the Constellation to a bounded, deduplicated set of matching teams, size circles by accumulated explainable match score, and expose the first observed evidence string in the inspector;
- desktop and mobile-responsive styling for the central map, evidence overlay, filter rail, inspector, and Org Walk.

Verification:

- frontend: 20 Vitest tests passed; TypeScript typecheck passed; Vite production build passed;
- backend: 166 pytest tests passed;
- real canonical master API returned snapshot `edd5d0f4269da97163b33a5cf7dd8c850ad51331a913721e0ce7a07e1977fce5`;
- headless Chrome desktop render at 1487x1058 verified the real 156-institution circle pack, automatic largest-institution selection, matched-evidence overlay, and API-backed team inspector;
- accepted concept and current desktop render were inspected together; palette, three-column shell, central constellation, selected cyan state, search/filter rail, and right inspector align semantically;
- headless Chrome on Windows enforces a layout viewport wider than the requested 390px screenshot, so the 390x844 capture is cropped horizontally and is not accepted as final mobile fidelity evidence. Responsive CSS is present, but true 390px browser emulation remains a final QA gate.

Remaining for Tasks 13â€“16:

- add full URL/back-button navigation semantics for drill-down rather than replace-only history;
- extend interest lighting from matching teams to optional parent-institution rollups and confidence filters;
- record measured real-data layout timings and the circle-pack/partition/treemap evaluation artifact;
- complete true mobile viewport/browser verification and final visual-fidelity ledger.

Next:

- implement category-aware Constellation lighting over explainable match evidence, then complete tours/saved views and bilingual/responsive polish.

## Task 17 â€” Curated tours and saved local maps

Status: verified in source, tests, and live runtime

Implemented:

- versioned bilingual AI, software, cybersecurity, policy, and data tour definitions;
- stable organization stop IDs validated against the current snapshot, with missing stops explicitly marked unavailable and never silently retargeted;
- public Tours API now returns editorial titles, descriptions, taxonomy categories, initial focus, ordered evidence notes, and stop availability;
- tour actions produce shareable constellation query/category/focus state;
- local-only saved maps persist aggregate explorer state, cap comparisons at four, cap notes at 2,000 characters, and redact contact/person field names;
- rolling compatibility for the previous department-tour response prevents the already-running server from crashing before its next restart.

Verification:

- frontend: 16 Vitest files / 23 tests passed; TypeScript typecheck and Vite production build passed;
- focused backend repository/API suite: 16 tests passed;
- the server was restarted against the real master database after quota renewal; `/api/tours` and the current production build are live on port 8780.

Next:

- continue Task 18 conservative career-conversation lead inference.

## Task 18 — Conservative career-conversation leads and vacancy signals

Status: implemented and verified

Implemented:

- versioned bilingual leadership-title rules for manager, gestionnaire, director/directeur/directrice, chief/chef, head/responsable, commissioner/commissaire, and executive variants;
- explicit assistant, advisor-to, support, office, and administrative exclusions;
- deterministic inference with direct-team leads ranked before parent-organization leads, high/medium explainable confidence, and a maximum of three suggestions;
- a privacy-bounded `LeadSuggestion` contract containing only kind, confidence, observed title, organization ID, official source URL, and reasons—no person name or contact fields;
- profile payloads now include snapshot date, conservative conversation leads, and source-derived vacancy markers with `live_competition_verified: false`;
- non-claiming UI cards distinguish “Possible team lead” and “Career conversation lead,” explain why each was suggested, link to the official GEDS record, and never call anyone a hiring manager;
- vacancy cards preserve the exact GEDS marker, observed title/date/source, state “No live competition verified,” and expose no Apply action.

TDD evidence:

- backend RED: `ModuleNotFoundError: No module named 'geds_crawler.career_leads'`;
- repository RED: `KeyError: 'conversation_leads'`;
- frontend RED: unresolved `./CareerConversationLeads` module;
- backend GREEN: `31 passed` across lead, repository, and API tests;
- frontend GREEN: `17` Vitest files / `25` tests passed; TypeScript typecheck and Vite production build passed.

Live verification:

- server listens on `0.0.0.0:8780`, `/api/meta` returns HTTP 200, and the refreshed production build is active;
- real master snapshot profile “Agriculture and Food Inspection Legal Services - AAFC” returned three observed manager-title suggestions and snapshot time `2026-07-09T07:05:04.674049+00:00`;
- no personal name/contact field is added to the public lead contract; vacancy state remains explicitly unverified.

Next:

- implement Task 19 complete bilingual and responsive experience, including real language switching and the remaining true-mobile verification gate.
