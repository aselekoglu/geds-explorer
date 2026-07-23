# Dependency-Free BreadcrumbTrail Checklist

## Phase 1: Local foundation

- [x] Task 1: Build and unit-test the semantic local `BreadcrumbTrail`.
- [x] Add dependency-free inline chevron and scoped `breadcrumb.css`.
- [x] Confirm package, lockfile, Vite, and theme files remain unchanged.

## Checkpoint: Foundation

- [x] Empty, single-item, actionable, static, duplicate-label, and long paths pass.
- [x] Light/dark component fixture is readable.
- [x] No npm dependency has been added.

## Phase 2: View migration

- [x] Task 2: Migrate Organization Explorer and ancestor navigation.
- [x] Task 3: Migrate Team Profile canonical path.
- [x] Task 4: Migrate legacy `OrgWalk` while preserving its tree.

## Checkpoint: Migration

- [x] All three breadcrumb views use `BreadcrumbTrail`.
- [x] Current crumb and actionable ancestor semantics are correct.
- [x] No feature/control was removed.

## Phase 3: Style cleanup

- [x] Task 5: Remove obsolete joined-string breadcrumb styles.
- [x] Verify mobile back-button target, wrapping, focus, and no overflow.

## Phase 4: Verification

- [x] Task 6: Run unit tests, typecheck, and production build.
- [x] Run accessibility and org-walk E2E checks.
- [x] Compare affected desktop/mobile surfaces.
- [x] Run `git diff --check`.
- [x] Confirm package manifest and lockfile have no migration diff.
- [x] Confirm unrelated worktree changes are untouched.

## Approval Gate

- [x] User approved the revised plan before implementation started.
