# Career Atlas Hierarchy-First Interactions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Discover and Organization Walk drill through organization hierarchy on their primary action, reserve Team Profile for an explicit detail action, and let role titles filter whichever view the user is currently using.

**Architecture:** `App` continues to own the public query, institution, hash view, and profile drawer. `ConstellationPage` owns a lightweight root-history stack and hovered node; `OrganizationExplorer` owns hierarchy columns plus an institution-scoped search lane. Public organization nodes gain one source-derived `direct_people_count` field so hover facts need no additional request.

**Tech Stack:** React 19, TypeScript 6, D3 pack layout, Vitest + Testing Library, FastAPI, SQLite, pytest.

## Global Constraints

- Public Career Atlas remains GET-only and exposes no contact or admin data.
- Primary row/bubble actions drill; only a sibling or hover-card detail action opens Team Profile.
- Interactive controls must never be nested inside another interactive control.
- Leaf drill attempts do not request an empty slice and show `No child teams`.
- Government-wide nodes use deterministic abbreviations; lower-level labels never use an ellipsis.
- Role clicks preserve the current `#discover` or `#explorer` view.
- Institution changes reset hierarchy history, hover/leaf state, and stale Team Profile.
- Preserve both light and dark themes and the existing English/French localization structure.

## File Map

- `work/geds-crawler/src/geds_crawler/career_api_models.py`: public `OrgNode` contract.
- `work/geds-crawler/src/geds_crawler/career_repository.py`: populate direct and descendant people counts in every organization-node query.
- `work/geds-career-atlas/src/api/types.ts`: mirror the public organization-node contract.
- `work/geds-career-atlas/src/features/constellation/labels.ts`: deterministic institution abbreviations and wrapped label lines.
- `work/geds-career-atlas/src/features/constellation/Constellation.tsx`: bubble drill, hover/focus, wrapped labels, and touch info affordance.
- `work/geds-career-atlas/src/features/constellation/ConstellationHoverCard.tsx`: bounded facts card and explicit profile action.
- `work/geds-career-atlas/src/features/constellation/ConstellationPage.tsx`: root history, Back, leaf state, and slice loading.
- `work/geds-career-atlas/src/features/org-walk/OrgColumn.tsx`: sibling drill/profile controls.
- `work/geds-career-atlas/src/features/org-walk/OrganizationExplorer.tsx`: hierarchy path and institution-scoped matching-team lane.
- `work/geds-career-atlas/src/features/profile/GroupedRoles.tsx`: role-title query buttons.
- `work/geds-career-atlas/src/features/profile/TeamProfile.tsx`: forward role query action.
- `work/geds-career-atlas/src/features/profile/TeamProfileLoader.tsx`: forward role query action through loader state.
- `work/geds-career-atlas/src/app/App.tsx`: view-preserving role query and explicit profile callbacks.
- `work/geds-career-atlas/src/i18n/en.ts`, `fr.ts`: localized labels and status copy.
- `work/geds-career-atlas/src/styles/constellation.css`, `org-walk.css`, `roles.css`: new layout and interaction styling.

---

### Task 1: Publish Direct People Counts on Organization Nodes

**Files:**
- Modify: `work/geds-crawler/src/geds_crawler/career_api_models.py`
- Modify: `work/geds-crawler/src/geds_crawler/career_repository.py`
- Modify: `work/geds-crawler/tests/test_career_repository.py`
- Modify: `work/geds-crawler/tests/test_career_api.py`
- Modify: `work/geds-career-atlas/src/api/types.ts`

**Interfaces:**
- Produces: `OrgNode.direct_people_count: int` in Python and `direct_people_count: number` in TypeScript.
- Preserves: `descendant_people_count` as the branch total.

- [ ] **Step 1: Add failing repository and API assertions**

Add assertions proving child, ancestor, and constellation nodes expose a numeric direct count distinct from the descendant count:

```python
assert isinstance(result.items[0].direct_people_count, int)
assert "direct_people_count" in response.json()["nodes"][0]
```

- [ ] **Step 2: Run the focused backend tests and confirm RED**

Run: `py -m pytest -q tests/test_career_repository.py tests/test_career_api.py`

Expected: FAIL because `OrgNode` has no `direct_people_count` attribute or serialized field.

- [ ] **Step 3: Extend every organization-node query and model**

Add the field to `OrgNode`, select `direct_people_count` alongside `descendant_people_count`, and construct nodes with named arguments to prevent positional-field drift:

```python
OrgNode(
    org_id=str(row["org_id"]),
    name=str(row["name"]),
    parent_id=row["parent_id"],
    depth=int(row["depth"]),
    child_count=int(row["child_count"]),
    direct_people_count=int(row["direct_people_count"]),
    descendant_people_count=int(row["descendant_people_count"]),
)
```

Mirror the required field in the frontend `OrgNode` type.

- [ ] **Step 4: Run focused tests and confirm GREEN**

Run: `py -m pytest -q tests/test_career_repository.py tests/test_career_api.py`

Expected: all selected tests PASS.

- [ ] **Step 5: Commit the contract change**

```powershell
git add work/geds-crawler/src/geds_crawler/career_api_models.py work/geds-crawler/src/geds_crawler/career_repository.py work/geds-crawler/tests/test_career_repository.py work/geds-crawler/tests/test_career_api.py work/geds-career-atlas/src/api/types.ts
git commit -m "feat: expose direct organization people counts"
```

### Task 2: Add Deterministic Bubble Labels

**Files:**
- Create: `work/geds-career-atlas/src/features/constellation/labels.ts`
- Create: `work/geds-career-atlas/src/features/constellation/labels.test.ts`
- Modify: `work/geds-career-atlas/src/features/constellation/Constellation.tsx`
- Modify: `work/geds-career-atlas/src/features/constellation/Constellation.test.tsx`

**Interfaces:**
- Produces: `institutionAbbreviation(name: string): string`.
- Produces: `wrapBubbleLabel(name: string, maxCharacters: number, maxLines?: number): string[]`.
- Consumes: `topLevel: boolean` on `Constellation`.

- [ ] **Step 1: Write failing pure-function and rendering tests**

Cover reviewed labels and fallback behavior:

```ts
expect(institutionAbbreviation("Canadian Radio-television and Telecommunications Commission")).toBe("CRTC")
expect(institutionAbbreviation("Employment and Social Development Canada")).toBe("ESDC")
expect(institutionAbbreviation("Example Office for Public Programs")).toBe("EOPP")
expect(wrapBubbleLabel("Chairperson's Office", 12)).toEqual(["Chairperson's", "Office"])
```

Render a lower-level large node and assert that no SVG text contains `...`.

- [ ] **Step 2: Run the label tests and confirm RED**

Run: `npm.cmd test -- src/features/constellation/labels.test.ts src/features/constellation/Constellation.test.tsx`

Expected: FAIL because the helpers and `topLevel` behavior do not exist.

- [ ] **Step 3: Implement reviewed mapping, fallback initials, and tspan wrapping**

Use a constant mapping for `CRTC`, `CRA`, `ESDC`, `SSC`, `ISED`, `PSPC`, `DFO`, and `TBS`. Drop connector words (`and`, `of`, `the`, `for`, French equivalents), cap fallback initials at six, and return centered SVG `<tspan>` lines only when radius permits.

```tsx
<text aria-hidden="true">
  {lines.map((line, index) => <tspan key={line} x={x} dy={index ? "1.1em" : startDy}>{line}</tspan>)}
</text>
```

Always retain the full name in the bubble's accessible label and native `<title>`.

- [ ] **Step 4: Run the focused frontend tests and confirm GREEN**

Run: `npm.cmd test -- src/features/constellation/labels.test.ts src/features/constellation/Constellation.test.tsx`

Expected: all selected tests PASS.

- [ ] **Step 5: Commit label behavior**

```powershell
git add work/geds-career-atlas/src/features/constellation/labels.ts work/geds-career-atlas/src/features/constellation/labels.test.ts work/geds-career-atlas/src/features/constellation/Constellation.tsx work/geds-career-atlas/src/features/constellation/Constellation.test.tsx
git commit -m "feat: add readable constellation labels"
```

### Task 3: Split Organization Walk Drill and Profile Actions

**Files:**
- Modify: `work/geds-career-atlas/src/features/org-walk/OrgColumn.tsx`
- Modify: `work/geds-career-atlas/src/features/org-walk/OrgColumn.test.tsx`
- Modify: `work/geds-career-atlas/src/features/org-walk/OrganizationExplorer.tsx`
- Modify: `work/geds-career-atlas/src/features/org-walk/OrganizationExplorer.test.tsx`
- Modify: `work/geds-career-atlas/src/styles/org-walk.css`
- Modify: `work/geds-career-atlas/src/styles/org-walk-virtual.css`
- Modify: `work/geds-career-atlas/src/i18n/en.ts`
- Modify: `work/geds-career-atlas/src/i18n/fr.ts`

**Interfaces:**
- `OrgColumn` consumes `onDrill(org: OrgNode): void` and `onProfile(orgId: string): void`.
- `OrganizationExplorer` consumes `onProfile?: (orgId: string) => void`; primary actions stay internal.

- [ ] **Step 1: Write failing action-separation tests**

Assert that clicking the card body loads children without calling `onProfile`, while clicking `Open Chairperson's Office profile` calls `onProfile` without adding a column. Assert a leaf click renders `No child teams` and does not request children.

- [ ] **Step 2: Run Organization Walk tests and confirm RED**

Run: `npm.cmd test -- src/features/org-walk/OrgColumn.test.tsx src/features/org-walk/OrganizationExplorer.test.tsx`

Expected: FAIL because the current row click also invokes the profile callback and there is no sibling detail button.

- [ ] **Step 3: Render sibling controls and explicit leaf state**

Render one visual card container with two sibling buttons:

```tsx
<div className="org-card">
  <button type="button" role="treeitem" onClick={() => onDrill(item)}>...</button>
  <button type="button" className="org-card__profile" aria-label={t("orgWalk.openProfile", { name: item.name })} onClick={() => onProfile(item.org_id)}>i</button>
</div>
```

Keep ArrowRight/Enter on the primary button, update breadcrumb selection on leaves, and render a next-column status instead of fetching children when `child_count === 0`.

- [ ] **Step 4: Run Organization Walk tests and confirm GREEN**

Run: `npm.cmd test -- src/features/org-walk/OrgColumn.test.tsx src/features/org-walk/OrganizationExplorer.test.tsx`

Expected: all selected tests PASS.

- [ ] **Step 5: Commit the split actions**

```powershell
git add work/geds-career-atlas/src/features/org-walk work/geds-career-atlas/src/styles/org-walk.css work/geds-career-atlas/src/styles/org-walk-virtual.css work/geds-career-atlas/src/i18n/en.ts work/geds-career-atlas/src/i18n/fr.ts
git commit -m "feat: separate hierarchy and profile actions"
```

### Task 4: Add Constellation Drill History, Back, and Leaf Handling

**Files:**
- Modify: `work/geds-career-atlas/src/features/constellation/Constellation.tsx`
- Modify: `work/geds-career-atlas/src/features/constellation/ConstellationPage.tsx`
- Modify: `work/geds-career-atlas/src/features/constellation/ConstellationPage.test.tsx`
- Modify: `work/geds-career-atlas/src/i18n/en.ts`
- Modify: `work/geds-career-atlas/src/i18n/fr.ts`

**Interfaces:**
- `Constellation` consumes `onDrill(node: ConstellationNode): void`, `onInspect(node, anchor): void`, and `topLevel: boolean`.
- `ConstellationPage` consumes `onProfile?: (orgId: string) => void` instead of profile-opening `onFocus`.
- `ConstellationPage` owns `rootHistory: Array<string | undefined>` and derives `rootId` from its last entry.

- [ ] **Step 1: Write failing history and leaf tests**

Verify bubble click for a child-bearing node requests its ID, does not call `onProfile`, and reveals Back. Verify Back restores exactly the prior root. Verify a leaf click causes no new API call and displays `No child teams`.

- [ ] **Step 2: Run ConstellationPage tests and confirm RED**

Run: `npm.cmd test -- src/features/constellation/ConstellationPage.test.tsx`

Expected: FAIL because bubble selection currently opens the profile and navigation depends on the fixed evidence panel.

- [ ] **Step 3: Replace root state with history and remove fixed evidence panel**

Use functional history updates:

```ts
function drill(node: ConstellationNode) {
  setLocalFocus(node.id)
  if (node.child_count > 0) setRootHistory(history => [...history, node.id])
  else setSelectedLeaf(node.id)
}
function goBack() {
  setRootHistory(history => history.length > 1 ? history.slice(0, -1) : history)
}
```

Reset history, inspection, leaf state, and local focus when `rootOrgId` changes. Retain the current slice with a retry status on request failure.

- [ ] **Step 4: Run ConstellationPage tests and confirm GREEN**

Run: `npm.cmd test -- src/features/constellation/ConstellationPage.test.tsx`

Expected: all selected tests PASS and `Explore branch` is absent.

- [ ] **Step 5: Commit hierarchy navigation**

```powershell
git add work/geds-career-atlas/src/features/constellation/Constellation.tsx work/geds-career-atlas/src/features/constellation/ConstellationPage.tsx work/geds-career-atlas/src/features/constellation/ConstellationPage.test.tsx work/geds-career-atlas/src/i18n/en.ts work/geds-career-atlas/src/i18n/fr.ts
git commit -m "feat: drill and back through constellation roots"
```

### Task 5: Add Anchored Hover and Focus Facts Card

**Files:**
- Create: `work/geds-career-atlas/src/features/constellation/ConstellationHoverCard.tsx`
- Create: `work/geds-career-atlas/src/features/constellation/ConstellationHoverCard.test.tsx`
- Modify: `work/geds-career-atlas/src/features/constellation/Constellation.tsx`
- Modify: `work/geds-career-atlas/src/features/constellation/ConstellationPage.tsx`
- Modify: `work/geds-career-atlas/src/styles/constellation.css`

**Interfaces:**
- Produces: `InspectedNode = { node: ConstellationNode; anchor: { x: number; y: number } }`.
- `ConstellationHoverCard` consumes node facts, bounded anchor, `onProfile`, `onStayOpen`, and `onLeave`.

- [ ] **Step 1: Write failing hover/focus/profile tests**

Assert hover and keyboard focus display full name, direct people, total branch people, child teams, and a dedicated Open profile button. Assert the explicit button calls `onProfile`; bubble click still only drills. Assert an info affordance can show the card without hover.

- [ ] **Step 2: Run focused hover-card tests and confirm RED**

Run: `npm.cmd test -- src/features/constellation/ConstellationHoverCard.test.tsx src/features/constellation/ConstellationPage.test.tsx`

Expected: FAIL because the hover card and direct count rendering do not exist.

- [ ] **Step 3: Implement bounded anchored card and focus retention**

Position within the stage with clamped coordinates:

```ts
const left = Math.min(Math.max(12, anchor.x + 16), stageWidth - cardWidth - 12)
const top = Math.min(Math.max(12, anchor.y - cardHeight / 2), stageHeight - cardHeight - 12)
```

Use pointer/focus enter and leave timers so moving from bubble to card keeps it visible. Add `aria-describedby`, full SVG `<title>`, and a separate coarse-pointer info control. Add reduced-motion styling.

- [ ] **Step 4: Run hover-card tests and confirm GREEN**

Run: `npm.cmd test -- src/features/constellation/ConstellationHoverCard.test.tsx src/features/constellation/ConstellationPage.test.tsx`

Expected: all selected tests PASS.

- [ ] **Step 5: Commit the facts card**

```powershell
git add work/geds-career-atlas/src/features/constellation work/geds-career-atlas/src/styles/constellation.css
git commit -m "feat: add constellation node facts card"
```

### Task 6: Make Observed Roles Apply a View-Preserving Query

**Files:**
- Modify: `work/geds-career-atlas/src/features/profile/GroupedRoles.tsx`
- Modify: `work/geds-career-atlas/src/features/profile/GroupedRoles.test.tsx`
- Modify: `work/geds-career-atlas/src/features/profile/TeamProfile.tsx`
- Modify: `work/geds-career-atlas/src/features/profile/TeamProfileLoader.tsx`
- Modify: `work/geds-career-atlas/src/app/App.tsx`
- Modify: `work/geds-career-atlas/src/app/App.test.tsx`
- Modify: `work/geds-career-atlas/src/styles/roles.css`

**Interfaces:**
- `GroupedRoles` consumes `onRoleQuery?: (title: string) => void`.
- `TeamProfile` and `TeamProfileLoader` forward the same optional callback.
- `App.applyRoleQuery(title: string)` updates `q`, retains the current hash, clears `focus`, and closes the drawer.

- [ ] **Step 1: Write failing role-button and App navigation tests**

Assert each non-empty grouped role title is a button; blank titles remain a count-only `No title` group. In App tests, click a role while at `#discover` and `#explorer` and assert the hash is unchanged, `q` is set, and the profile closes.

- [ ] **Step 2: Run role/App tests and confirm RED**

Run: `npm.cmd test -- src/features/profile/GroupedRoles.test.tsx src/app/App.test.tsx`

Expected: FAIL because role headings are not buttons and the existing query update redirects explorer searches to Discover.

- [ ] **Step 3: Thread the callback and implement `applyRoleQuery`**

```ts
function applyRoleQuery(title: string) {
  const normalized = title.trim()
  setQuery(normalized)
  setSelectedOrgId(null)
  writeUrl(params => {
    normalized ? params.set("q", normalized) : params.delete("q")
    params.delete("focus")
  }, location.hash || "#discover")
}
```

Render the visible title as the button label and retain the grouped count beside it.

- [ ] **Step 4: Run role/App tests and confirm GREEN**

Run: `npm.cmd test -- src/features/profile/GroupedRoles.test.tsx src/app/App.test.tsx`

Expected: all selected tests PASS.

- [ ] **Step 5: Commit view-aware role filtering**

```powershell
git add work/geds-career-atlas/src/features/profile work/geds-career-atlas/src/app/App.tsx work/geds-career-atlas/src/app/App.test.tsx work/geds-career-atlas/src/styles/roles.css
git commit -m "feat: filter current view from observed roles"
```

### Task 7: Filter Organization Walk with Matching Teams

**Files:**
- Modify: `work/geds-career-atlas/src/features/org-walk/OrganizationExplorer.tsx`
- Modify: `work/geds-career-atlas/src/features/org-walk/OrganizationExplorer.test.tsx`
- Modify: `work/geds-career-atlas/src/app/App.tsx`
- Modify: `work/geds-career-atlas/src/styles/org-walk.css`
- Modify: `work/geds-career-atlas/src/i18n/en.ts`
- Modify: `work/geds-career-atlas/src/i18n/fr.ts`

**Interfaces:**
- `OrganizationExplorer` consumes `query?: string`, `institutionName?: string`, and a client with `search(query, signal)` plus `ancestors(orgId, signal)`.
- Produces a deduplicated `OrgNode`-like result list keyed by `org_id`.

- [ ] **Step 1: Write failing scoped-result tests**

Provide duplicate search hits across two institutions. Assert only selected-institution organization IDs appear once under `Matching teams`. Assert primary result click restores the ancestor path without opening profile; its detail button only opens profile. Assert empty/failure status leaves hierarchy columns visible.

- [ ] **Step 2: Run OrganizationExplorer tests and confirm RED**

Run: `npm.cmd test -- src/features/org-walk/OrganizationExplorer.test.tsx`

Expected: FAIL because Organization Explorer does not consume the shared query or search endpoint.

- [ ] **Step 3: Add abortable search lane and path restoration**

Fetch only for `query.trim()`, filter by `department_name === institutionName`, deduplicate by `org_id`, and render result cards with sibling drill/profile actions. On primary result action, call `ancestors`, restore columns from root to the result, and do not change profile state. Clear results and statuses when the query clears.

- [ ] **Step 4: Run OrganizationExplorer tests and confirm GREEN**

Run: `npm.cmd test -- src/features/org-walk/OrganizationExplorer.test.tsx`

Expected: all selected tests PASS.

- [ ] **Step 5: Commit Organization Walk search**

```powershell
git add work/geds-career-atlas/src/features/org-walk/OrganizationExplorer.tsx work/geds-career-atlas/src/features/org-walk/OrganizationExplorer.test.tsx work/geds-career-atlas/src/app/App.tsx work/geds-career-atlas/src/styles/org-walk.css work/geds-career-atlas/src/i18n/en.ts work/geds-career-atlas/src/i18n/fr.ts
git commit -m "feat: filter organization walk by career query"
```

### Task 8: Integrate, Localize, and Browser-Verify the Hierarchy Experience

**Files:**
- Modify: `work/geds-career-atlas/tests/e2e/constellation.spec.ts`
- Modify: `work/geds-career-atlas/tests/e2e/org-walk.spec.ts`
- Modify: `work/geds-career-atlas/tests/e2e/career-research.spec.ts`
- Modify: `docs/superpowers/evidence/geds-career-atlas-acceptance.md`

**Interfaces:**
- Consumes all prior tasks as the complete public hierarchy interaction contract.

- [ ] **Step 1: Add end-to-end acceptance cases**

Cover bubble drill/Back, full hover facts, explicit profile opening, Organization Walk card drill/detail split, and a role query that remains in Organization Walk.

- [ ] **Step 2: Run full automated verification**

Run in `work/geds-career-atlas`:

```powershell
npm.cmd test
npm.cmd run typecheck
npm.cmd run build
```

Run in `work/geds-crawler`:

```powershell
py -m pytest -q tests
```

Expected: frontend unit tests, TypeScript build, production bundle, and backend suite all PASS.

- [ ] **Step 3: Serve and verify the real public UI**

Serve on `0.0.0.0:8780`, then verify in Chrome at desktop and narrow widths in light and dark themes:

- institution change resets to that institution's hierarchy;
- bubble body drills and Back returns one level;
- hover/focus card stays within the canvas and opens profile only from its detail button;
- top-level abbreviations and lower-level wrapped labels are readable;
- Organization Walk body/detail actions differ;
- role click filters the current view;
- keyboard focus and Escape behavior remain usable.

- [ ] **Step 4: Record evidence and run whitespace validation**

Update the acceptance document with commands, results, browser URLs, and observed interaction checks.

Run: `git diff --check`

Expected: no whitespace errors.

- [ ] **Step 5: Commit acceptance evidence**

```powershell
git add work/geds-career-atlas/tests/e2e docs/superpowers/evidence/geds-career-atlas-acceptance.md
git commit -m "test: verify hierarchy-first Career Atlas interactions"
```

## Self-Review

- Spec coverage: primary/secondary actions, leaf state, Back stack, institution reset, fixed-panel removal, hover/focus/touch facts, direct counts, abbreviations, full labels, view-preserving role query, Organization Walk search lane, accessibility, and error states each map to Tasks 1-8.
- Placeholder scan: no deferred implementation markers or unspecified test steps remain.
- Type consistency: `direct_people_count`, `onProfile`, `onRoleQuery`, `rootHistory`, `institutionAbbreviation`, and `wrapBubbleLabel` use the same names across producer and consumer tasks.
