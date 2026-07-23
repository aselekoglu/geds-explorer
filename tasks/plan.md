# Implementation Plan: Dependency-Free BreadcrumbTrail Migration

## Implementation Status

Completed on 2026-07-23. All six tasks and both checkpoints passed. Final
verification: 100 unit tests, typecheck, production build, 8 targeted Playwright
E2E checks, axe serious/critical scan, mobile overflow check, and
`git diff --check`.

## Overview

`work/geds-career-atlas` icindeki mevcut organizasyon-yolu gorunumlerini, yeni
dependency eklemeden ortak bir yerel `BreadcrumbTrail` component'ine tasiyacagiz.
Component Untitled UI'nin sade "Breadcrumbs text" varyantini gorsel referans
alacak; Untitled UI kaynak kodu, PRO asset'i, CLI'i, React Aria veya Tailwind
kullanilmayacak.

Bu tur yalnizca planlama kapsamindadir; implementasyon yapilmayacaktir.

Mevcut envanter:

1. `OrgBreadcrumb.tsx`: Organization Explorer icindeki canli, secili organizasyon
   yolu. Mobilde ayri bir "bir seviye geri" kontrolu de var.
2. `TeamProfile.tsx`: Profil drawer'inda `canonical_path` su anda duz metin ve
   slash separator ile render ediliyor.
3. `OrgWalk.tsx`: Production tarafinda su an import edilmeyen legacy yol
   gorunumu. Kod tabaninda eski breadcrumb markup'i birakmamak icin kapsamda.

## Architecture Decisions

- Yeni `BreadcrumbTrail`, yalnızca React ve semantik HTML kullanacak:
  `<nav aria-label>`, `<ol>`, `<li>`, ancestor icin gercek bir action varsa
  `<button>`, mevcut sayfa icin `<span aria-current="page">`.
- Component API'si feature verisini bilmeyecek. `items`, erisilebilir `label` ve
  opsiyonel `onSelect(index)` alacak.
- Sahte URL uretilmeyecek. Organization Explorer ancestor seviyelerini gercekten
  degistirebildigi icin crumb'lari button olacak; Team Profile ve legacy
  `OrgWalk` path'leri statik metin olacak.
- Separator, yeni icon paketi yerine dependency'siz inline SVG chevron olarak
  render edilecek ve `aria-hidden="true"` olacak.
- Stil, mevcut `tokens.css` degiskenlerini kullanacak. Light/dark tema mevcut
  `data-theme` sistemiyle otomatik uyumlu kalacak; theme kodu degismeyecek.
- Untitled UI'den yalnizca gorsel ilkeler alinacak: muted ancestor, belirgin
  current crumb, dengeli chevron boslugu, net hover/focus state'i ve kompakt
  tipografi. Herhangi bir lisansli kaynak kod kopyalanmayacak.
- Uzun path'lerde tum crumb'lar DOM'da kalacak ve satira kirilabilecek.
  Uygulanacak ilk surumde dropdown/collapse state'i olmayacak. Responsive test
  gercek bir sorun kanitlarsa sonraki bir task olarak ele alinacak.
- Organization Explorer'daki mevcut mobil "bir seviye geri" butonu breadcrumb
  yaninda korunacak. Bu buton breadcrumb semantigine dahil edilmeyecek.
- Yeni component bos item listesinde hicbir landmark render etmeyecek; tek
  item'da yalnizca current crumb render edecek.
- `package.json`, `package-lock.json`, `vite.config.ts`, theme provider/toggle ve
  global build pipeline kapsam disidir.
- Implementasyondan once worktree tekrar kontrol edilecek. Alakasiz kullanici
  degisiklikleri restore, format veya stage edilmeyecek.

## Dependency Graph

```text
Local BreadcrumbTrail contract
    |
    +-- Semantic markup + focused unit tests
    |
    +-- Dependency-free breadcrumb.css
            |
            +-- Organization Explorer migration
            |
            +-- Team Profile migration
            |
            +-- Legacy OrgWalk migration
                    |
                    +-- Obsolete CSS cleanup
                            |
                            +-- Full unit/build/E2E verification
```

## Task Details

### Task 1: Build the local BreadcrumbTrail component

**Description:** Create the reusable component, its dependency-free inline
separator, Untitled-inspired scoped styles, and focused semantic tests.

**Acceptance criteria:**

- [ ] Output is a named navigation landmark containing an ordered list.
- [ ] The final crumb is a non-interactive
      `<span aria-current="page">`; only actionable ancestors are buttons.
- [ ] Separators are decorative, empty paths render nothing, and single-item
      paths render correctly.
- [ ] Styling uses only existing project tokens and remains scoped under the
      component class.

**Verification:**

- [ ] Unit test nav/list/listitem semantics and current-page state.
- [ ] Unit test ancestor click plus keyboard activation.
- [ ] Unit test empty, single-item, duplicate-label, and long-path inputs.
- [ ] Run focused Vitest for `BreadcrumbTrail`.

**Dependencies:** None

**Files likely touched:**

- `work/geds-career-atlas/src/components/BreadcrumbTrail.tsx`
- `work/geds-career-atlas/src/components/BreadcrumbTrail.test.tsx`
- `work/geds-career-atlas/src/styles/breadcrumb.css`
- `work/geds-career-atlas/src/main.tsx`

**Estimated scope:** Medium

### Checkpoint: Local foundation

- [ ] `BreadcrumbTrail` renders without a new npm dependency.
- [ ] Semantic tests pass.
- [ ] Light/dark component fixture is readable.
- [ ] `package.json`, lockfile, Vite config, and theme files are unchanged.

### Task 2: Migrate the live Organization Explorer path

**Description:** Replace the slash-joined `OrgBreadcrumb` nav with
`BreadcrumbTrail`, pass indexed hierarchy levels, and let ancestor crumbs return
the explorer to the selected column level.

**Acceptance criteria:**

- [ ] The selected hierarchy is represented by individual list items.
- [ ] Clicking an ancestor removes only columns after that ancestor.
- [ ] The current organization is non-clickable and announced as current.
- [ ] Existing mobile one-level-back behavior remains keyboard accessible.

**Verification:**

- [ ] Update `OrganizationExplorer.test.tsx` for list semantics, active crumb,
      and ancestor navigation.
- [ ] Add focused `OrgBreadcrumb` coverage if the feature wrapper remains.
- [ ] Manually verify root, drill-down, deep URL restoration, search-result
      restoration, leaf, and mobile states.

**Dependencies:** Task 1

**Files likely touched:**

- `work/geds-career-atlas/src/features/org-walk/OrgBreadcrumb.tsx`
- `work/geds-career-atlas/src/features/org-walk/OrganizationExplorer.tsx`
- `work/geds-career-atlas/src/features/org-walk/OrganizationExplorer.test.tsx`

**Estimated scope:** Medium

### Task 3: Migrate the Team Profile canonical path

**Description:** Replace the profile drawer's slash-joined `canonical_path`
paragraph with the shared static breadcrumb mode.

**Acceptance criteria:**

- [ ] Every canonical-path segment renders as an individual breadcrumb item.
- [ ] The final segment is current; earlier segments remain honest,
      non-interactive text because the profile response does not provide
      navigable IDs for each ancestor.
- [ ] Profile facts, people, roles, related teams, source link, and issue-report
      behavior are unchanged.

**Verification:**

- [ ] Update `TeamProfile.test.tsx` for landmark, list, and current crumb.
- [ ] Verify no profile path renders a slash-joined text string.
- [ ] Manually inspect the profile drawer in light/dark and narrow layouts.

**Dependencies:** Task 1

**Files likely touched:**

- `work/geds-career-atlas/src/features/profile/TeamProfile.tsx`
- `work/geds-career-atlas/src/features/profile/TeamProfile.test.tsx`

**Estimated scope:** Small

### Task 4: Migrate the legacy OrgWalk path

**Description:** Replace the legacy component's header nav with the shared
static breadcrumb mode while leaving its virtualized hierarchy tree intact.

**Acceptance criteria:**

- [ ] `OrgWalk` no longer contains slash-joined breadcrumb markup.
- [ ] Its virtualized tree, roving focus, item count, and current treeitem
      behavior remain unchanged.
- [ ] The breadcrumb and tree retain distinct accessible names and roles.

**Verification:**

- [ ] Update `OrgWalk.test.tsx` for breadcrumb semantics.
- [ ] Retain and run the long-list virtualization assertions.

**Dependencies:** Task 1

**Files likely touched:**

- `work/geds-career-atlas/src/features/org-walk/OrgWalk.tsx`
- `work/geds-career-atlas/src/features/org-walk/OrgWalk.test.tsx`

**Estimated scope:** Small

### Checkpoint: All breadcrumb views migrated

- [ ] Organization Explorer, Team Profile, and `OrgWalk` use
      `BreadcrumbTrail`.
- [ ] No feature or control has been removed.
- [ ] No new package or build dependency has been introduced.

### Task 5: Remove obsolete breadcrumb styles

**Description:** Remove selectors that only supported the former joined-string
markup and retain the mobile back-button layout without conflicting with the new
component.

**Acceptance criteria:**

- [ ] No stale `.org-breadcrumb nav` or joined-string-specific style remains.
- [ ] New breadcrumb selectors are namespaced and use existing color/focus
      tokens.
- [ ] Mobile back button retains its minimum 44px target.
- [ ] Breadcrumbs wrap without clipping or horizontal page overflow.

**Verification:**

- [ ] Repository search confirms every path view uses `BreadcrumbTrail`.
- [ ] Desktop and <=700px checks cover short, medium, and deep hierarchies.
- [ ] High-contrast/focus-visible states remain distinguishable.

**Dependencies:** Tasks 2-4

**Files likely touched:**

- `work/geds-career-atlas/src/styles/org-walk-virtual.css`
- `work/geds-career-atlas/src/styles/premium.css`
- `work/geds-career-atlas/src/styles/theme-overrides.css`
- `work/geds-career-atlas/src/styles/breadcrumb.css`

**Estimated scope:** Medium

### Task 6: Run full regression and accessibility verification

**Description:** Verify the shared component and all migrated surfaces without
expanding the dependency or build footprint.

**Acceptance criteria:**

- [ ] Unit suite, typecheck, and production build pass.
- [ ] Playwright accessibility checks pass on explorer and profile states.
- [ ] No console errors, focus regression, clipping, or unexpected style change
      appears on affected surfaces.
- [ ] Package manifest and lockfile have no migration-related diff.

**Verification:**

- [ ] `npm test`
- [ ] `npm run typecheck`
- [ ] `npm run build`
- [ ] `npm run test:e2e -- tests/e2e/accessibility.spec.ts tests/e2e/org-walk.spec.ts`
- [ ] Targeted desktop/mobile screenshots for explorer and profile drawer.
- [ ] `git diff --check`
- [ ] `git diff -- work/geds-career-atlas/package.json work/geds-career-atlas/package-lock.json`

**Dependencies:** Tasks 1-5

**Files likely touched:**

- `work/geds-career-atlas/tests/e2e/accessibility.spec.ts`
- `work/geds-career-atlas/tests/e2e/org-walk.spec.ts`

**Estimated scope:** Small

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Custom component accidentally recreates incomplete breadcrumb semantics | High | Fix the DOM contract first and enforce nav/list/current/separator behavior with focused tests |
| Button crumbs look like navigation but truncate the wrong explorer level | High | Use stable array indices from the current column model and add an ancestor-click regression test |
| Static profile ancestors are presented as fake links | Medium | Render text spans unless a real navigation callback exists |
| Deep government hierarchy paths overflow on mobile | Medium | Keep all items in the DOM, allow wrapping, and test real deep paths at <=700px |
| Untitled-inspired styling conflicts with existing premium/theme CSS | Medium | Use existing CSS tokens and a single namespaced component class loaded before narrow feature overrides |
| Legacy `OrgWalk` is unused and may drift silently | Low | Migrate and keep its isolated unit tests rather than deleting it in this scope |
| Existing user work overlaps target files | High | Re-check worktree and overlapping diffs before editing; preserve unrelated hunks |

## Open Questions

No blocking question. The selected visual direction is the Untitled UI
"Breadcrumbs text" family, implemented independently with the current GEDS
design tokens. Account/avatar variants, React Aria, Tailwind, dropdown collapse,
and primary sidebar navigation are explicitly out of scope.

## Definition of Done

- [x] Every current breadcrumb/path presentation uses the local
      `BreadcrumbTrail`.
- [x] No new runtime, dev, CLI, CSS-framework, or icon dependency was added.
- [x] Navigation honesty, current-page semantics, responsive wrapping, focus
      visibility, and theme behavior meet the acceptance criteria.
- [x] Full verification passes and no unrelated user changes are overwritten.
- [x] Human approval was received before implementation began.
