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
