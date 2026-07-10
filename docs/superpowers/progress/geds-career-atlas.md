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
