# GEDS Crawl Control Plane UI/UX Audit

Audit date: 2026-07-09  
Target: `http://127.0.0.1:8765/`  
Desktop viewport: 1440 × 1000  
Mobile viewport: 390 × 844  
Capture method: Playwright 1.61.1 with system Chrome

## Audit scope

This audit covers the current operator workflow across Overview, Crawlers,
Coverage, Schedules, and Snapshot Data. It evaluates information architecture,
task clarity, interaction density, system-status visibility, responsive
behavior, and screenshot-visible accessibility risks.

The operator's primary goals are:

1. Understand crawl health and important exceptions at a glance.
2. Inspect and control active crawlers without confusing them with archived runs.
3. Inspect coverage and snapshot data without losing operational context.
4. Create jobs and schedules through focused, error-resistant flows.

## Evidence and step health

| Step | Screen | Health | Evidence |
| --- | --- | --- | --- |
| 1 | Overview | Needs restructuring | `01-overview.png` |
| 2 | Crawlers | Critical information-density problem | `02-crawlers.png` |
| 3 | Coverage | Critical findability and scale problem | `03-coverage.png` |
| 4 | Schedules | Needs clearer guidance and empty state | `04-schedules.png` |
| 5 | Snapshot Data | Functional but contextually overloaded | `05-snapshot-data.png` |
| 6 | Mobile Overview | Broken responsive hierarchy | `06-overview-mobile.png` |

## Strengths

- The persistent development-security warning is prominent.
- Status colors are restrained and mostly consistent.
- Core operational functions are present and reachable.
- Snapshot tables include search, department filtering, page sizing, and pagination.
- Current crawl progress, traffic, counts, and run controls are exposed rather than hidden.
- The UI uses semantic forms, tables, labels, and some ARIA labels.

## Structural UX risks

### 1. Global snapshot context leaks into every task

The active database selector, one crawl's progress, and eight snapshot metrics
appear above Crawlers, Coverage, Schedules, and Snapshot Data. This makes the
page hierarchy imply that every screen is subordinate to the selected database,
even where the content is controller-wide.

This violates task grouping and proximity: global control-plane state, selected
snapshot state, and page-local content are visually merged.

Recommendation: separate the product into three explicit workspaces:

- **Operate**: overview and crawler control.
- **Plan**: coverage and schedules.
- **Explore data**: database/snapshot selection and tables.

The database selector and snapshot metrics should exist only inside Explore
data. Controller-wide health should remain in Operate.

### 2. Overview reports counts but does not answer "what needs attention?"

The first viewport shows two metric blocks with twelve values, but no exception
summary, active-run list, failed/stale heartbeat indicator, or next action. The
operator must remember what normal values mean and navigate elsewhere.

Recommendation: make Overview an exception-first command center:

- top status strip: running, queued, failed, aggregate RPS;
- active crawl rows with progress, ETA, heartbeat, and one primary action;
- attention queue for overlap, failures, stale heartbeat, and coverage gaps;
- secondary links to schedules and data exploration.

### 3. Crawlers combines creation, selection, estimates, live operation, and history

The screen contains a large job-creation form, a scrollable 156-department
picker, estimates, a start action, active runs, completed runs, and unmanaged
runs in one continuous page. The current active crawler is visually buried
below the creation workflow.

This increases cognitive load and weakens the most important safety distinction:
observing an active process versus configuring and starting a new one.

Recommendation:

- default screen: active and queued runs first;
- separate **Jobs** and **Run history** views;
- open **New crawler** as a focused multi-step drawer or dedicated flow;
- use steps: scope → crawl settings → traffic/safety → review and start;
- keep department selection searchable with bulk filters and a persistent
  selected-count summary;
- require a final review that spells out institutions, estimated load, policy,
  output, and schedule before mutation.

### 4. Coverage is an unfiltered 156-row wall

The full list is technically complete but has no visible summary, search,
status filter, job filter, grouping, or exception-first default. The one overlap
is nearly invisible inside a seven-screen-long table.

Recommendation:

- summary counts for covered, stale, unassigned, overlapping, and failed;
- default to **Needs attention** when exceptions exist;
- search plus status/job filters;
- compact table with sticky controls and pagination or virtualization;
- row detail drawer for assignment and crawl history;
- explicit remediation action for overlap and unassigned states.

### 5. Schedules exposes implementation syntax before operator intent

The main field asks for cron or magic preset strings in the same text box.
There is no visible explanation of Toronto time, next occurrence preview,
overlap-policy consequences, validation feedback, or useful empty state.

Recommendation:

- start with preset controls: once, hourly, daily, weekly, advanced;
- show timezone and next three run times before save;
- explain overlap policy inline;
- reveal raw cron only under Advanced;
- use a purposeful empty state with a clear create action.

### 6. Snapshot Data is a separate product mode disguised as another tab

It adds a second tab system (Org Units, People, Queue, Errors) inside the global
tabs while retaining controller navigation, database selection, progress, and
metrics above it. The data table itself is usable, but its context is mixed with
operations.

Recommendation: make Explore data a distinct workspace with:

- a compact dataset/run selector in its own header;
- one-line dataset metadata;
- table tabs and filters directly adjacent to the data;
- optional column controls and row-detail inspection;
- no controller-wide cards unless linked as a concise context breadcrumb.

## Visual and interaction risks

- Most sections use the same white bordered container, so priority is expressed
  through position rather than a clear hierarchy.
- The page relies heavily on small uppercase labels and 10–11 px supporting
  text, which is difficult to scan.
- Active, completed, unmanaged, and creation states are not separated strongly
  enough.
- Full-page tables create extreme document lengths: Coverage reached 7016 px;
  Snapshot Data reached 5444 px.
- There is no visible keyboard focus treatment in the stylesheet.
- The only captured console error is a missing `/favicon.ico` request; no page
  JavaScript exception was observed.

## Mobile accessibility and responsive risks

The 390 px capture shows:

- product title, update timestamp, and Refresh control overlapping;
- horizontal navigation clipped after the first items without a clear overflow
  affordance;
- the database label wrapping into a narrow four-line column;
- metric labels and values compressed into four narrow columns;
- very small supporting text.

The document does not report horizontal page overflow, but visible clipping and
overlap still make the layout unusable. A no-overflow assertion alone is not a
valid responsive-quality check.

Recommended responsive behavior:

- compact mobile header with title plus overflow menu;
- workspace navigation becomes a clearly scrollable tab rail or menu;
- database selector stacks label above control;
- metrics become two columns, then one column where needed;
- tables become contained horizontal scrollers with frozen key columns or
  switch to list/detail presentation;
- controls should keep at least 44 px touch targets.

## Screenshot-visible accessibility risks

- No explicit `:focus-visible` treatment was found.
- Several controls use small text and 32–36 px heights.
- Status meaning relies heavily on badge color and terse labels.
- Sortable table headers are clickable but do not visibly expose button
  semantics or sort state.
- Dense tables and long org paths create difficult reading and zoom behavior.
- Empty tables provide little guidance or recovery action.

These are risks, not a WCAG compliance determination. Keyboard order, screen
reader output, contrast ratios, zoom at 200–400%, reduced-motion behavior, and
live-region announcements still require implementation-level testing.

## Overhaul direction

Adopt an operator-console information architecture with persistent workspace
navigation and three task modes:

1. **Operate**
   - Overview
   - Crawlers
   - Run history
2. **Plan**
   - Coverage
   - Schedules
3. **Explore data**
   - Snapshot tables
   - Dataset/run context

Use progressive disclosure for creation and scheduling, exception-first
defaults for operations and coverage, and table-first layouts for data
inspection. Preserve every current capability, but remove repeated global
snapshot blocks from unrelated screens.

## Evidence limits

- The audit used current live data and read-only navigation between tabs.
- No crawler was started, stopped, resumed, deleted, or scheduled.
- Mutation validation, destructive confirmations, and error recovery were not
  exercised because they would change live operational state.
- Accessibility observations are limited to rendered screenshots, DOM
  structure, and stylesheet inspection.
