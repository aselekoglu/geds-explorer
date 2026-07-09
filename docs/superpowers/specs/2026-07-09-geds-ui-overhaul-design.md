# GEDS UI Overhaul Design

Date: 2026-07-09

## Status

Approved design direction. Implementation has not started.

## Problem

The current GEDS crawl control UI exposes useful functionality, but its information architecture is overloaded. Tables, active database context, crawler controls, coverage state, schedules, and snapshot inspection appear too close together. This makes the page hard to scan even for the project owner.

The redesign must preserve the current functionality while making the UI immediately understandable. On first load, an operator should be able to answer:

- Are crawlers running?
- Is anything broken or stale?
- What coverage needs attention?
- What is scheduled next?
- Where do I inspect database/snapshot details?

## Design Goal

Create a professional, calm, dark-themed GEDS operator console with a clear separation between operational monitoring, planning, and database exploration.

The selected direction is **Command Center Rail**:

- A persistent left navigation rail on desktop.
- Three top-level workspaces: Operate, Plan, Explore Data.
- Exception-first overview.
- Progressive disclosure for creation and scheduling flows.
- Snapshot/database controls isolated to the data exploration workspace.

## Information Architecture

### Operate

Used for live operational work.

- Overview
- Crawlers
- Run History

### Plan

Used for coverage and recurring work.

- Coverage
- Schedules

### Explore Data

Used for snapshot, table, and database inspection.

- Snapshot Data
- Table browser
- Row/detail inspection

## Global Layout

### Desktop

- Left rail is always visible.
- Main content uses a clear page header, one sentence of screen context, then task-specific sections.
- Secondary inspector panels may appear on the right when useful, but they must not compete with primary content.
- A compact global security warning remains visible because the local UI/control plane is unauthenticated.

### Tablet

- Rail can collapse.
- Secondary panels stack under the main task area.
- Primary actions remain near the top of each screen.

### Mobile

- Navigation becomes a drawer or bottom navigation.
- Large tables switch to card/list views.
- Details are expandable.
- Header and navigation must not overlap or clip.
- Data density is reduced; primary actions remain easy to reach.

## Screen Designs

### Overview

The overview answers "what needs attention right now?"

Content:

- Compact system status strip:
  - connection status
  - active crawlers
  - coverage health
  - failed or blocked items
- Attention Queue:
  - overlap
  - failed run
  - stale schedule
  - missing coverage
  - other actionable exceptions
- Live Activity:
  - active crawlers
  - latest runs
  - req/sec
  - progress
- Coverage summary:
  - covered
  - missing
  - overlap
  - stale
- Next schedules summary.

Database and snapshot details should not dominate this screen. They may appear only as light context when directly relevant.

### Crawlers

The crawler screen focuses on running and starting crawlers.

Content:

- Active Runs as the primary section.
- Run History as a secondary, filterable panel.
- Start Crawler as the primary action.
- Start Crawler opens a guided drawer or modal instead of showing a large embedded form.

Start Crawler flow:

1. Select target or department.
2. Review estimate.
3. Configure crawl options.
4. Confirm and start.

Risky actions require clear labels and confirmation.

### Run History

Run History is available as its own Operate screen and as a secondary panel from Crawlers.

Requirements:

- Filter by status, target, and date where data allows.
- Show duration, processed count, failures, and final status.
- Link from a failed or attention item to the relevant run detail.

### Coverage

Coverage should not default to an undifferentiated table wall.

Content:

- Summary cards:
  - covered
  - missing
  - overlap
  - stale
- Filter chips:
  - All
  - Needs attention
  - Missing
  - Overlap
  - Stale
- Main table remains available.
- Default view emphasizes problem rows.
- Rows can expand to reveal:
  - department
  - source
  - last crawl
  - issue reason
  - recommended next action when available

### Schedules

Schedules should make recurring work understandable without forcing cron syntax first.

Content:

- Schedule list:
  - enabled or disabled
  - target
  - cadence
  - next run
  - last run
  - status
- New Schedule guided flow:
  1. Select target.
  2. Select cadence.
  3. Review next run preview.
  4. Optionally open advanced cron controls.
- Empty state explains why schedules matter and provides a clear create action.

Cron remains supported, but it is advanced configuration.

### Explore Data / Snapshot Data

Explore Data owns database and snapshot inspection.

Content:

- Active DB selector as the top context control.
- Snapshot metrics as summary cards.
- Main DB/table browser.
- Search and filtering.
- Row detail inspector.
- Export/debug information where existing functionality supports it.

Active DB and snapshot metrics must not visually dominate Operate or Plan.

## Functionality Mapping

| Existing capability | New location |
| --- | --- |
| Active DB selection | Explore Data context bar |
| Snapshot metrics | Explore Data summary cards |
| Main DB/table inspection | Explore Data table browser |
| Active crawlers | Operate > Crawlers and Overview live activity |
| Start crawler | Operate > Crawlers > Start crawler drawer |
| Department picker | Start crawler flow |
| Crawl estimates | Start crawler flow after target selection |
| Run history | Operate > Run History and Crawlers secondary panel |
| Coverage table | Plan > Coverage |
| Coverage problems | Overview Attention Queue and Coverage filters |
| Schedules | Plan > Schedules |
| Cron/schedule setup | Schedules guided flow, advanced section |
| Security warning | Global compact persistent banner |

## State Model

Global state is limited to data that is truly global:

- connection status
- current workspace
- active runs count
- attention count
- unauthenticated-local warning

Explore Data state:

- selected database
- selected table
- search/filter state
- selected row/detail

Operate state:

- active crawler polling
- selected run
- run filters
- start crawler draft

Plan state:

- coverage filters
- selected coverage row
- schedule editor draft

This separation is a core design requirement. The current UI feels confusing because operational, planning, and database inspection states are mixed.

## Data Refresh

- Overview refreshes frequently because it is a live status screen.
- Active crawler panels refresh frequently.
- Coverage, schedules, and snapshot data refresh more deliberately.
- Manual refresh controls should be available where automatic refresh would be surprising or expensive.
- Refresh must not cause layout jumping.
- Loading states should reserve space using skeletons or stable placeholders.
- Errors should appear at the panel that failed rather than taking over the whole page.

## URL and Navigation State

Use hash routes where feasible:

- `#/operate/overview`
- `#/operate/crawlers`
- `#/operate/history`
- `#/plan/coverage`
- `#/plan/schedules`
- `#/explore/snapshot`

This makes the LAN UI easier to use from another device and lets the user reopen a specific screen directly.

## Visual System

The existing dark identity stays, but hierarchy becomes stricter.

- Background uses dark navy/black with two or three clear surface levels.
- Green remains the primary brand/accent color, but usage is controlled.
- Status colors:
  - green: healthy/running
  - amber: attention/stale
  - red: failed/blocked
  - blue: informational/scheduled
- Cards must have clear titles, concise descriptions, and one dominant metric or action.
- Tables use subtle row separation, hover state, selected row state, and sticky headers where useful.
- Attention items get the strongest emphasis.
- Non-actionable metrics should not visually compete with problems.

## Typography and Spacing

- Page titles are short: Operate, Crawlers, Coverage, Schedules, Snapshot Data.
- Each screen has a one-sentence explanation.
- Metric typography is large enough to scan but not oversized.
- Form labels are direct.
- Helper text appears only when it reduces ambiguity.
- Spacing follows an 8px grid.
- Reusable classes/components replace scattered inline styling where practical.

## Accessibility

Requirements:

- Every interactive element has a visible focus state.
- Status is communicated with text or labels, not color alone.
- Buttons, tabs, drawers, modals, filters, inputs, and menus are keyboard usable.
- Drawers and modals manage focus when opened and closed.
- Form validation errors appear beside the relevant input.
- Dark theme contrast remains readable.
- Loading, empty, error, and partial-data states have accessible text.

## Empty, Error, Loading, and Partial States

Each main screen needs explicit states:

- Empty: what is missing, why it matters, and what the user can do.
- Error: what failed, where it failed, and how to retry.
- Loading: stable layout with reserved space.
- Partial data: show available data and label the unavailable panel.

## Implementation Boundaries

The initial implementation should be a focused UI overhaul, not a product rewrite.

In scope:

- Reorganize the UI template, script, and style in `work/geds-crawler/src/geds_crawler/ui_server.py`.
- Preserve existing API endpoints.
- Preserve existing crawler, coverage, schedule, run history, and snapshot inspection functionality.
- Improve layout, grouping, display hierarchy, interaction flows, responsive behavior, and accessibility.
- Add small client-side mapping or presentation helpers when needed.

Out of scope for the first implementation:

- Large framework migration.
- Replacing the backend.
- Removing existing functionality.
- Production auth hardening beyond preserving the current visible unauthenticated-local warning.

If the file size and mixed responsibilities make the change too risky, the implementation plan may include a controlled split of CSS/JS/template helpers. Any split must stay focused on this UI overhaul.

## Acceptance Criteria

- First load answers these questions within five seconds:
  - Are crawlers running?
  - Is anything broken or stale?
  - What coverage needs attention?
  - What is scheduled next?
- Active DB, snapshot metrics, and table browsing are visually centered in Explore Data, not Operate or Plan.
- Start Crawler works as a guided flow rather than a large always-visible form.
- Coverage defaults to problem-oriented scanning while preserving access to the full table.
- Schedules show next-run context and treat cron as advanced configuration.
- Desktop layout is stable and uncluttered.
- Mobile layout does not overlap, clip, or require reading giant tables.
- Keyboard focus is visible.
- Empty, loading, error, and partial-data states are understandable.
- Existing API-backed functionality remains available.

## Verification Plan

Implementation should be verified with:

- Existing Python tests, especially:
  - `work/geds-crawler/tests/test_ui_server.py`
  - relevant control/API tests
- Local HTTP smoke:
  - `/` returns 200
  - primary UI script loads without console-breaking errors
  - core API requests still work
- Screenshot/browser audit:
  - desktop overview
  - crawlers
  - coverage
  - schedules
  - explore data
  - mobile overview
- Visual regression checks:
  - no nav/header overlap
  - tables are readable
  - drawer/modal behavior works
  - primary actions are visible
- Accessibility smoke:
  - tab navigation reaches main controls
  - focus ring is visible
  - status labels do not rely on color alone

## Subagent-Driven Implementation Plan

The user requested subagent-driven work. Subagents will be used after the written spec is approved and after an implementation plan exists.

Proposed roles:

- UX implementation agent: layout/component refactor.
- State/API mapping agent: preserve endpoint usage and state separation.
- QA/a11y agent: responsive, accessibility, and smoke testing.
- Review agent: regression and functionality-loss review.

Subagents should not start implementation until the implementation plan is written and approved.
