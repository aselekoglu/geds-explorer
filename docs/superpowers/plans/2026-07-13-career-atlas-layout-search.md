# Career Atlas Search-First Layout and Grouped Team Profiles Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Deliver a full-width, search-first public Career Atlas with institution-synchronized bubbles, a dedicated Organization Walk view, an on-demand Team Profile drawer, and title-grouped leaf-team people.

**Architecture:** Keep the existing React/FastAPI contracts and move public view/filter coordination into small frontend state helpers. Institution names resolve to existing department IDs, which become explicit roots for both constellation and hierarchy browsing. Reuse the privacy-safe people endpoint and group its direct-team records with a pure title-normalization utility.

**Tech Stack:** React 19, TypeScript 6, Vite 8, Vitest, Testing Library, CSS custom properties, existing FastAPI read-only Career API.

**Implementation status:** Complete. Tasks 1–6 were delivered in incremental commits; Task 7 was verified against the live canonical snapshot on 2026-07-13. The unified query required a privacy-safe backend extension so person names and direct organization names could be returned alongside taxonomy matches without exposing contact fields.

## Global Constraints

- Public Career Atlas remains GET-only and never calls `/api/control/*`.
- Public and Admin navigation remain disjoint.
- Names appear only for direct members of leaf teams (`child_count === 0`).
- Person payloads and UI contain no email, phone, fax, address, or crawler state.
- Classification badges remain limited to explicit observed `EC`, `CO`, `IT`, and legacy `CS` values returned by the existing endpoint.
- Topic presentation uses only deterministic interpretation categories/evidence returned by the API.
- The existing untracked `docs/ux-audit/career-atlas-2026-07-12.md` is user-owned and must not be staged or modified.

---

### Task 1: Public view state and simplified institution scope

**Files:**
- Create: `work/geds-career-atlas/src/state/publicView.ts`
- Create: `work/geds-career-atlas/src/state/publicView.test.ts`
- Modify: `work/geds-career-atlas/src/features/discover/FilterRail.tsx`
- Modify: `work/geds-career-atlas/src/features/discover/FilterRail.test.tsx`
- Modify: `work/geds-career-atlas/src/app/App.tsx`
- Modify: `work/geds-career-atlas/src/app/App.test.tsx`
- Modify: `work/geds-career-atlas/src/i18n/en.ts`
- Modify: `work/geds-career-atlas/src/i18n/fr.ts`

**Interfaces:**
- Produces: `PublicView = "discover" | "explorer" | "about"`.
- Produces: `readPublicView(hash: string): PublicView` and `publicViewHash(view: PublicView): string`.
- Produces: `DiscoverScope = { department: string }` and an institution-only `<FilterRail>`.

- [x] **Step 1: Write failing state and UI tests**

```ts
it("maps only public hashes to views", () => {
  expect(readPublicView("#explorer")).toBe("explorer")
  expect(readPublicView("#about")).toBe("about")
  expect(readPublicView("#tours")).toBe("discover")
})
```

```tsx
it("renders only institution scope and data quality", () => {
  render(<FilterRail departments={departments} value={{department:""}} qualityStatus="partial_overlay" onChange={vi.fn()} />)
  expect(screen.getByLabelText("Institution")).toBeVisible()
  expect(screen.queryByLabelText(/minimum confidence/i)).not.toBeInTheDocument()
  expect(screen.queryByLabelText(/recorded vacancy/i)).not.toBeInTheDocument()
  expect(screen.queryByLabelText(/career domain/i)).not.toBeInTheDocument()
})
```

```tsx
it("mounts one primary view and does not reserve an empty profile column", async () => {
  history.replaceState(null,"","/#discover")
  const {container}=render(<App />)
  expect(screen.getByRole("link",{name:/organization walk/i})).toBeVisible()
  expect(screen.queryByText(/guided ways/i)).not.toBeInTheDocument()
  expect(container.querySelector(".detail-panel")).not.toBeInTheDocument()
})
```

- [x] **Step 2: Run focused tests and verify RED**

Run: `npm.cmd test -- src/state/publicView.test.ts src/features/discover/FilterRail.test.tsx src/app/App.test.tsx`

Expected: FAIL because `publicView.ts` does not exist and the old domain/confidence/vacancy controls and stacked views are still rendered.

- [x] **Step 3: Implement the minimal view and scope contracts**

```ts
export type PublicView="discover"|"explorer"|"about"
export function readPublicView(hash:string):PublicView {
  return hash==="#explorer"?"explorer":hash==="#about"?"about":"discover"
}
export const publicViewHash=(view:PublicView)=>`#${view}`
```

```tsx
export type DiscoverScope={department:string}
export function FilterRail({departments,value,qualityStatus,onChange}:Props){
  return <div className="institution-scope">
    <label>{t("roles.institution")}<select value={value.department} onChange={event=>onChange({department:event.target.value})}>...</select></label>
    <span className="quality-chip">{t("discover.quality",{status:qualityStatus.replaceAll("_"," ")})}</span>
  </div>
}
```

Refactor `App` so the nav contains only Discover, Organization Walk, and About; render exactly one primary view; remove `SavedMap`; and render the detail aside only when `selectedOrgId` is non-null.

- [x] **Step 4: Run focused tests and verify GREEN**

Run: `npm.cmd test -- src/state/publicView.test.ts src/features/discover/FilterRail.test.tsx src/app/App.test.tsx`

Expected: PASS.

- [x] **Step 5: Commit the view-state slice**

```powershell
git add work/geds-career-atlas/src/state/publicView.ts work/geds-career-atlas/src/state/publicView.test.ts work/geds-career-atlas/src/features/discover/FilterRail.tsx work/geds-career-atlas/src/features/discover/FilterRail.test.tsx work/geds-career-atlas/src/app/App.tsx work/geds-career-atlas/src/app/App.test.tsx work/geds-career-atlas/src/i18n/en.ts work/geds-career-atlas/src/i18n/fr.ts
git commit -m "feat: focus Career Atlas public navigation"
```

### Task 2: Institution-synchronized constellation and Organization Walk

**Files:**
- Modify: `work/geds-career-atlas/src/features/constellation/ConstellationPage.tsx`
- Modify: `work/geds-career-atlas/src/features/constellation/ConstellationPage.test.tsx`
- Modify: `work/geds-career-atlas/src/features/org-walk/OrganizationExplorer.tsx`
- Modify: `work/geds-career-atlas/src/features/org-walk/OrganizationExplorer.test.tsx`
- Modify: `work/geds-career-atlas/src/app/App.tsx`
- Modify: `work/geds-career-atlas/src/app/App.test.tsx`

**Interfaces:**
- Consumes: `DepartmentPage.items` and `DiscoverScope.department`.
- Produces: `<ConstellationPage rootOrgId?: string ...>`.
- Produces: `<OrganizationExplorer rootOrg?: OrgNode ...>`.

- [x] **Step 1: Write failing root synchronization tests**

```tsx
it("reloads from the selected institution root", async () => {
  const constellationSlice=vi.fn().mockResolvedValue({nodes:[],limit:2000,truncated:false,snapshot_id:"s",etag:"e"})
  const {rerender}=render(<ConstellationPage client={{constellationSlice}} rootOrgId="department-a" />)
  await waitFor(()=>expect(constellationSlice).toHaveBeenLastCalledWith("department-a",expect.any(AbortSignal)))
  rerender(<ConstellationPage client={{constellationSlice}} rootOrgId="department-b" />)
  await waitFor(()=>expect(constellationSlice).toHaveBeenLastCalledWith("department-b",expect.any(AbortSignal)))
})
```

```tsx
it("starts Organization Walk inside the selected institution", async () => {
  const rootOrg={org_id:"department-a",name:"Department A",depth:0,child_count:1,descendant_people_count:10}
  const children=vi.fn().mockResolvedValue({items:[{org_id:"team",name:"Team",depth:1,child_count:0,descendant_people_count:2}],snapshot_id:"s",etag:"e"})
  render(<OrganizationExplorer client={{rootChildren:vi.fn(),children}} rootOrg={rootOrg}/>)
  expect(await screen.findByRole("treeitem",{name:/Team/i})).toBeVisible()
  expect(children).toHaveBeenCalledWith("department-a",expect.any(AbortSignal))
})
```

```tsx
it("clears stale profile focus when institution changes", async () => {
  history.replaceState(null,"","/?focus=old-team&department=Department+A#discover")
  render(<App />)
  fireEvent.change(await screen.findByLabelText("Institution"),{target:{value:"Department B"}})
  expect(new URLSearchParams(location.search).has("focus")).toBe(false)
  expect(screen.queryByLabelText(/team profile/i)).not.toBeInTheDocument()
})
```

- [x] **Step 2: Run tests and verify RED**

Run: `npm.cmd test -- src/features/constellation/ConstellationPage.test.tsx src/features/org-walk/OrganizationExplorer.test.tsx src/app/App.test.tsx`

Expected: FAIL because neither explorer accepts an institution root and App retains focus.

- [x] **Step 3: Implement root props and stale-state clearing**

In `App`, resolve the selected department once:

```ts
const selectedDepartment=departments.find(item=>item.name===scope.department)
const institutionRoot=selectedDepartment?{
  org_id:selectedDepartment.department_id,
  name:selectedDepartment.name,
  depth:0,child_count:1,descendant_people_count:0
}:undefined
```

On institution change, delete `focus`, set `selectedOrgId(null)`, and pass `selectedDepartment?.department_id` to `ConstellationPage` plus `institutionRoot` to `OrganizationExplorer`.

In `ConstellationPage`, treat `rootOrgId` as the external base root and reset internal branch root whenever it changes:

```ts
useEffect(()=>{setRootId(rootOrgId);setLocalFocus(undefined)},[rootOrgId])
```

In `OrganizationExplorer`, call `client.children(rootOrg.org_id, signal)` for the initial institution column; otherwise retain `rootChildren` behavior.

- [x] **Step 4: Run tests and verify GREEN**

Run: `npm.cmd test -- src/features/constellation/ConstellationPage.test.tsx src/features/org-walk/OrganizationExplorer.test.tsx src/app/App.test.tsx`

Expected: PASS.

- [x] **Step 5: Commit institution synchronization**

```powershell
git add work/geds-career-atlas/src/features/constellation work/geds-career-atlas/src/features/org-walk work/geds-career-atlas/src/app/App.tsx work/geds-career-atlas/src/app/App.test.tsx
git commit -m "fix: synchronize institution exploration roots"
```

### Task 3: Unified query with Topics, Teams, and People result types

**Files:**
- Modify: `work/geds-career-atlas/src/features/discover/DiscoverPage.tsx`
- Modify: `work/geds-career-atlas/src/features/discover/DiscoverPage.test.tsx`
- Modify: `work/geds-career-atlas/src/app/App.tsx`
- Modify: `work/geds-career-atlas/src/styles/discover.css`
- Modify: `work/geds-career-atlas/src/i18n/en.ts`
- Modify: `work/geds-career-atlas/src/i18n/fr.ts`

**Interfaces:**
- Produces: `SearchKind = "all" | "topics" | "teams" | "people"`.
- Produces: `<DiscoverPage kind department onSelectOrg ...>`.

- [x] **Step 1: Write failing result-type tests**

```tsx
it("switches one deterministic query between topics, teams, and people", async () => {
  render(<DiscoverPage search="policy" kind="all" department="" client={client}/>)
  expect(await screen.findByText("Policy and programs")).toBeVisible()
  expect(screen.getByRole("article",{name:/Policy Team/i})).toBeVisible()
  expect(screen.getByRole("article",{name:/Alex Smith/i})).toBeVisible()
  fireEvent.click(screen.getByRole("radio",{name:"People"}))
  expect(screen.queryByRole("article",{name:/Policy Team/i})).not.toBeInTheDocument()
  expect(screen.getByRole("article",{name:/Alex Smith/i})).toBeVisible()
})
```

```tsx
it("applies institution scope without confidence or vacancy filtering", async () => {
  render(<DiscoverPage search="analyst" kind="all" department="Department B" client={client}/>)
  expect(await screen.findByText("Department B Team")).toBeVisible()
  expect(screen.queryByText("Department A Team")).not.toBeInTheDocument()
})
```

- [x] **Step 2: Run focused search tests and verify RED**

Run: `npm.cmd test -- src/features/discover/DiscoverPage.test.tsx`

Expected: FAIL because `kind` and entity-kind presentation do not exist.

- [x] **Step 3: Implement type controls and deterministic filtering**

```ts
export type SearchKind="all"|"topics"|"teams"|"people"
const visibleItems=items.filter(item=>
  (!department||item.department_name===department)&&
  (kind==="all"||kind==="teams"&&item.entity_kind==="organization"||kind==="people"&&item.entity_kind==="person")
)
const showTopics=kind==="all"||kind==="topics"
```

Render a labelled radio group in the command/search region. `Topics` renders `InterpretationChips` only; Teams and People render source records with distinct labels. Organization results call `onSelectOrg(item.org_id)` when available.

- [x] **Step 4: Run search tests and verify GREEN**

Run: `npm.cmd test -- src/features/discover/DiscoverPage.test.tsx src/app/App.test.tsx`

Expected: PASS.

- [x] **Step 5: Commit unified search**

```powershell
git add work/geds-career-atlas/src/features/discover work/geds-career-atlas/src/app/App.tsx work/geds-career-atlas/src/styles/discover.css work/geds-career-atlas/src/i18n/en.ts work/geds-career-atlas/src/i18n/fr.ts
git commit -m "feat: add unified Career Atlas search"
```

### Task 4: Pure observed-title grouping

**Files:**
- Create: `work/geds-career-atlas/src/features/profile/titleGroups.ts`
- Create: `work/geds-career-atlas/src/features/profile/titleGroups.test.ts`
- Create: `work/geds-career-atlas/src/features/profile/GroupedRoles.tsx`
- Create: `work/geds-career-atlas/src/features/profile/GroupedRoles.test.tsx`
- Modify: `work/geds-career-atlas/src/features/profile/TeamProfile.tsx`
- Modify: `work/geds-career-atlas/src/features/profile/TeamProfile.test.tsx`

**Interfaces:**
- Produces: `normalizeObservedTitle(title: string | null | undefined): string`.
- Produces: `groupObservedTitles(titles: string[]): TitleGroup[]` where `TitleGroup={key:string;label:string;count:number;empty:boolean}`.
- Produces: `<GroupedRoles titles: string[]>`.

- [x] **Step 1: Write failing grouping tests**

```ts
it("groups case and whitespace variants and sorts empty last",()=>{
  expect(groupObservedTitles([" Senior  Analyst ","senior analyst","", "   "])).toEqual([
    {key:"senior analyst",label:"Senior Analyst",count:2,empty:false},
    {key:"",label:"No title recorded",count:2,empty:true},
  ])
})
```

```tsx
it("renders repeated roles once with a count",()=>{
  render(<GroupedRoles titles={["Analyst","Analyst",""]}/>)
  expect(screen.getByRole("heading",{name:/Analyst.*2/i})).toBeVisible()
  expect(screen.getByRole("button",{name:/No title recorded.*1/i})).toHaveAttribute("aria-expanded","false")
  expect(screen.getAllByText("Analyst")).toHaveLength(1)
})
```

- [x] **Step 2: Run grouping tests and verify RED**

Run: `npm.cmd test -- src/features/profile/titleGroups.test.ts src/features/profile/GroupedRoles.test.tsx src/features/profile/TeamProfile.test.tsx`

Expected: FAIL because grouping modules do not exist and TeamProfile renders a flat list.

- [x] **Step 3: Implement normalization and grouped disclosure UI**

```ts
export const normalizeObservedTitle=(title?:string|null)=>(title??"").trim().replace(/\s+/g," ")
export function groupObservedTitles(titles:string[]):TitleGroup[]{
  const groups=new Map<string,TitleGroup>()
  for(const raw of titles){
    const normalized=normalizeObservedTitle(raw)
    const key=normalized.toLocaleLowerCase()
    const current=groups.get(key)
    if(current)current.count+=1
    else groups.set(key,{key,label:normalized||"No title recorded",count:1,empty:!normalized})
  }
  return [...groups.values()].sort((a,b)=>Number(a.empty)-Number(b.empty)||a.label.localeCompare(b.label))
}
```

Replace TeamProfile's raw `<ul>{roles.map(...)}</ul>` and remove nested `RoleExplorer` rendering. The empty group uses a closed `<details>` disclosure; non-empty role headings are rendered once with their counts.

- [x] **Step 4: Run grouping tests and verify GREEN**

Run: `npm.cmd test -- src/features/profile/titleGroups.test.ts src/features/profile/GroupedRoles.test.tsx src/features/profile/TeamProfile.test.tsx`

Expected: PASS.

- [x] **Step 5: Commit role grouping**

```powershell
git add work/geds-career-atlas/src/features/profile
git commit -m "feat: group repeated observed roles"
```

### Task 5: Group leaf-team people underneath titles

**Files:**
- Modify: `work/geds-career-atlas/src/features/people/PeopleInTeam.tsx`
- Modify: `work/geds-career-atlas/src/features/people/PeopleInTeam.test.tsx`
- Modify: `work/geds-career-atlas/src/styles/people.css`
- Modify: `work/geds-career-atlas/src/i18n/en.ts`
- Modify: `work/geds-career-atlas/src/i18n/fr.ts`

**Interfaces:**
- Consumes: `normalizeObservedTitle` and privacy-safe `PeoplePage.items`.
- Produces: title-grouped direct-team people with person search and classification filter.

- [x] **Step 1: Write failing leaf-team grouping tests**

```tsx
it("places direct people under one normalized title group",async()=>{
  render(<PeopleInTeam orgId="leaf" client={clientWith([
    person("Ada","Senior  Analyst","IT-02"),
    person("Grace","senior analyst","IT-03"),
    person("Unknown","",undefined),
  ])}/>)
  expect(await screen.findByRole("heading",{name:/Senior Analyst.*2/i})).toBeVisible()
  expect(screen.getByText("Ada")).toBeVisible()
  expect(screen.getByText("Grace")).toBeVisible()
  expect(screen.getByRole("button",{name:/No title recorded.*1/i})).toHaveAttribute("aria-expanded","false")
  expect(screen.getByRole("link",{name:/View in official GEDS/i})).toHaveAttribute("href",expect.stringContaining("geds-sage.gc.ca"))
})
```

```tsx
it("does not render a sort control",async()=>{
  render(<PeopleInTeam orgId="leaf" client={clientWith([])}/>)
  await screen.findByRole("status")
  expect(screen.queryByLabelText(/sort people/i)).not.toBeInTheDocument()
})
```

- [x] **Step 2: Run people tests and verify RED**

Run: `npm.cmd test -- src/features/people/PeopleInTeam.test.tsx`

Expected: FAIL because the component uses a flat table and exposes sort controls.

- [x] **Step 3: Implement grouped people presentation**

Group returned people by `normalizeObservedTitle(person.observed_title).toLocaleLowerCase()`. Render each non-empty title as a heading with count and a list of names; render the empty title group as a closed disclosure. Keep person search and classification selects, request `sort:"title"`, and render classification badges plus official links inside each person row.

- [x] **Step 4: Run people and profile tests and verify GREEN**

Run: `npm.cmd test -- src/features/people/PeopleInTeam.test.tsx src/features/profile/TeamProfileLoader.test.tsx src/features/profile/TeamProfile.test.tsx`

Expected: PASS and non-leaf TeamProfile tests prove that PeopleInTeam is not mounted when `child_count > 0`.

- [x] **Step 5: Commit grouped people**

```powershell
git add work/geds-career-atlas/src/features/people work/geds-career-atlas/src/styles/people.css work/geds-career-atlas/src/i18n/en.ts work/geds-career-atlas/src/i18n/fr.ts
git commit -m "feat: group leaf team people by title"
```

### Task 6: Full-width workspace and accessible profile drawer

**Files:**
- Create: `work/geds-career-atlas/src/features/profile/ProfileDrawer.tsx`
- Create: `work/geds-career-atlas/src/features/profile/ProfileDrawer.test.tsx`
- Modify: `work/geds-career-atlas/src/app/App.tsx`
- Modify: `work/geds-career-atlas/src/styles/global.css`
- Modify: `work/geds-career-atlas/src/styles/filters.css`
- Modify: `work/geds-career-atlas/src/styles/constellation.css`
- Modify: `work/geds-career-atlas/src/styles/org-walk.css`
- Modify: `work/geds-career-atlas/src/styles/polish.css`
- Modify: `work/geds-career-atlas/src/styles/theme-overrides.css`

**Interfaces:**
- Produces: `<ProfileDrawer open onClose returnFocusRef children>`.

- [x] **Step 1: Write failing drawer behavior tests**

```tsx
it("renders nothing while closed and closes on Escape",()=>{
  const onClose=vi.fn()
  const {rerender}=render(<ProfileDrawer open={false} onClose={onClose}>Profile</ProfileDrawer>)
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
  rerender(<ProfileDrawer open onClose={onClose}>Profile</ProfileDrawer>)
  fireEvent.keyDown(screen.getByRole("dialog"),{key:"Escape"})
  expect(onClose).toHaveBeenCalled()
})
```

```tsx
it("labels the open profile as a modal drawer",()=>{
  render(<ProfileDrawer open onClose={vi.fn()}><h2 id="profile-title">Team</h2></ProfileDrawer>)
  expect(screen.getByRole("dialog")).toHaveAttribute("aria-modal","true")
})
```

- [x] **Step 2: Run drawer tests and verify RED**

Run: `npm.cmd test -- src/features/profile/ProfileDrawer.test.tsx src/app/App.test.tsx`

Expected: FAIL because ProfileDrawer does not exist.

- [x] **Step 3: Implement drawer and responsive workspace CSS**

Render a fixed backdrop and drawer only when open, move focus to the close button, close on Escape, and restore the supplied trigger focus on cleanup. Update `.app-shell` to two columns (`side nav + minmax(0,1fr)`), make `.detail-panel` fixed/overlayed, give Discover a viewport-bounded canvas, and keep Organization Walk/About as standalone scroll regions. At narrow widths, use compact navigation and a full-screen drawer.

- [x] **Step 4: Run drawer tests, typecheck, and build**

Run: `npm.cmd test -- src/features/profile/ProfileDrawer.test.tsx src/app/App.test.tsx && npm.cmd run typecheck && npm.cmd run build`

Expected: PASS and build exits 0.

- [x] **Step 5: Commit layout and drawer**

```powershell
git add work/geds-career-atlas/src/features/profile/ProfileDrawer.tsx work/geds-career-atlas/src/features/profile/ProfileDrawer.test.tsx work/geds-career-atlas/src/app/App.tsx work/geds-career-atlas/src/styles
git commit -m "feat: add full-width Career Atlas workspace"
```

### Task 7: Regression and live visual verification

**Files:**
- Modify if needed: `work/geds-career-atlas/src/**/*.test.ts*`
- Modify: `docs/superpowers/specs/2026-07-13-career-atlas-layout-search-design.md`
- Modify: `docs/superpowers/plans/2026-07-13-career-atlas-layout-search.md`

**Interfaces:**
- Verifies every acceptance criterion without changing public API privacy boundaries.

- [x] **Step 1: Run complete frontend verification**

Run: `npm.cmd test`

Expected: all Vitest files and tests pass.

Run: `npm.cmd run typecheck`

Expected: exit 0 with no TypeScript errors.

Run: `npm.cmd run build`

Expected: Vite production build exits 0.

- [x] **Step 2: Run backend regression verification**

Run: `py -m pytest -q tests`

Working directory: `work/geds-crawler`

Expected: all backend tests pass; no API mutation or privacy contract changed. Targeting `tests` avoids unrelated inaccessible `pytest_temp` directories in the repository root.

- [x] **Step 3: Serve the merged frontend build locally**

Run: `py -m geds_crawler.career_cli serve --master-db ..\..\outputs\master\geds-master.sqlite --frontend-dir ..\geds-career-atlas\dist --host 0.0.0.0 --port 8780`

Working directory: `work/geds-crawler`

Expected: `/`, `/api/meta`, and `/api/departments` return HTTP 200 on localhost and the workstation LAN address.

- [x] **Step 4: Browser-verify critical flows**

Verify at desktop and narrow widths:

1. switch from CRTC to Canadian Transportation Agency and confirm bubble labels/counts visibly change;
2. confirm the previous Team Profile closes on institution change;
3. switch Discover, Organization Walk, and About without scrolling through stacked sections;
4. search a keyword and toggle All/Topics/Teams/People;
5. open a non-leaf profile and confirm counts without descendant names;
6. open a leaf profile and confirm title counts, names under titles, observed classifications, official GEDS links, and collapsed no-title group;
7. confirm light and dark themes and mobile full-screen profile behavior;
8. inspect console for errors.

- [x] **Step 5: Complete docs and diff audit**

Mark implemented acceptance criteria and completed plan checkboxes only after evidence exists.

Run: `git diff --check`

Expected: no whitespace errors and `git status --short` contains only intended tracked changes plus the preserved user-owned UX audit file.

- [x] **Step 6: Commit verified implementation documentation**

```powershell
git add docs/superpowers/specs/2026-07-13-career-atlas-layout-search-design.md docs/superpowers/plans/2026-07-13-career-atlas-layout-search.md
git commit -m "docs: verify Career Atlas layout redesign"
```
