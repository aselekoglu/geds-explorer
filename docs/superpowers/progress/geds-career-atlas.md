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
