# GEDS Career Atlas UI/UX Audit

**Date:** 2026-07-12  
**Evidence:** July 9, 2026 snapshot UI, desktop explorer, Organization Walk, narrow/mobile state, and the first Google Stitch redesign pass.  
**Scope:** Visual hierarchy, interaction trust, responsive behavior, accessibility, and information density. This review does not validate the underlying GEDS data pipeline.

## Executive finding

The product has a credible dark civic-tech visual foundation, but the current interaction model can show mutually inconsistent scope, selection, breadcrumb, profile, and source-link states. That makes state trust the primary usability problem. The next release should fix selection ownership and request ordering before spending effort on visual polish.

The first Stitch pass validates the proposed shell and hierarchy direction, but it is not an accepted design: Stitch renamed the product to **Civic Explorer**, fabricated organizations and metrics, introduced an avatar and decorative office image, and replaced the supplied current-state evidence with generic mockups. Those deviations must be corrected before design handoff.

## Severity summary

| Priority | Finding | User impact | Acceptance target |
| --- | --- | --- | --- |
| P0 | Institution, URL, selected node, path, and profile can disagree | Users cannot know which organization they are inspecting | One URL-backed selection contract drives every surface |
| P0 | Profile/source link can remain stale after rapid selection | A valid-looking profile can belong to the previous team | A-to-B selection never renders A under B; stale requests are ignored |
| P0 | Official GEDS organization link can point to an unrelated hierarchy | Users are sent to the wrong authoritative record | Link DN/source URL is derived from the same selected organization ID |
| P1 | Navigation can remain on Discover while the user is in Explorer | Location and back/forward behavior are unclear | Active navigation follows the visible hash/section |
| P1 | Filters has no visible open/closed result | Primary control appears broken | Disclosure state, active-filter summary, and clear/reset actions are visible |
| P1 | Mobile/narrow layout clips navigation and competes with the profile | Core discovery-to-profile journey is incomplete | 390 px flow uses a compact app bar and full-height profile sheet |
| P1 | Organization Walk has ambiguous scroll ownership | Deep paths become slow and disorienting | Sticky shell plus independently scrolling hierarchy columns and explicit previous/next controls |
| P2 | Raw repeated titles create very long lists | Important counts, warnings, and related teams are buried | Group duplicate titles and expose a deliberate “View all” action |
| P2 | Low-contrast/default-blue links and tiny nodes reduce accessibility | Links and small constellation targets are difficult to perceive/use | WCAG AA text/link contrast and 44 px pointer targets |

## Evidence-backed findings

### 1. Scope and selection are not one state

The institution control can show Canadian Museum of Immigration at Pier 21 or Canadian Food Inspection Agency while the selected path and team profile remain in CRTC or ESDC. The URL query can also retain one institution while the focused organization belongs to another.

This is not a copy problem. It indicates multiple state owners: URL parameters, filter controls, hierarchy focus, constellation selection, and profile data are updating independently.

**Fix:** define a single canonical selection object containing institution ID, organization ID, ancestor path, source URL, and snapshot ID. Derive the filter label, scope sentence, selected node, breadcrumb, profile, related teams, and official-source link from that object.

### 2. Profile updates are not transaction-safe

Fast focus changes can leave the previous profile visible under a new selection. The UI does not clearly preserve previous data, show loading, or suppress out-of-order responses.

**Fix:** key profile queries by organization ID and snapshot ID; cancel or ignore superseded requests; preserve previous content only under an explicit “Updating…” state; commit focus and profile atomically when the response belongs to the latest request.

### 3. Official-source trust is vulnerable

The IT Services and Dispute Resolution states expose the same official GEDS organization DN in the inspected UI, even though the organizations are unrelated. Because the link is presented as authoritative, this is a trust-critical defect.

**Fix:** remove hard-coded/fallback organization URLs from the profile component. Generate the link from the selected canonical organization record, and add an invariant test that the source DN/URL resolves to the same selected organization.

### 4. The shell does not communicate location reliably

The active navigation remains on Discover while Explorer content is visible. The command/filter region also consumes a large horizontal band without clearly communicating what is active, collapsed, or scoped.

**Fix:** derive navigation state from the visible route/hash; use a compact active-filter summary; give Filters a real disclosure state; keep the current scope sentence visible.

### 5. Constellation and semantic list need equal status

Large circles dominate the viewport and labels truncate, while small circles are hard to target. The synchronized list exists in the accessibility tree but is visually secondary. The evidence card can cover useful clusters.

**Fix:** treat the constellation as a spatial overview and the organization list as the precise selection surface. Label only the selected and largest meaningful nodes, give every node a 44 px transparent hit target, keep the list synchronized, and dock evidence outside core clusters.

### 6. Organization Walk exposes hierarchy but not progress

The desktop walk shows several columns, yet ancestry is difficult to scan and the layout leaves large unused regions. The newest child column can appear off-screen, and nested scrolling obscures which region owns navigation.

**Fix:** pin the canonical breadcrumb; use three useful sticky-headed columns; scroll lists inside each column; provide explicit previous/next column controls; move the newly opened child into view; keep the team profile sticky.

### 7. Mobile parity is incomplete

At narrow widths, the navigation/filter area clips and the right profile competes with the main content. The desktop constellation is not an effective primary control at 390 px.

**Fix:** replace the horizontal navigation with a compact app bar; stack search and primary actions; open filters as a full-width sheet; make the semantic organization list primary; open the selected team in a full-height modal profile with a persistent 44 px close/back control.

### 8. Profile density hides meaning

Observed roles repeat dozens of times, while snapshot date, partial-data warning, official source, related teams, and career-conversation context compete for attention.

**Fix:** keep identity, canonical path, counts, snapshot, warning, and official source above the fold. Group titles, for example “Senior Analyst ×24” and “IT Analyst ×18”, then offer “View all observed titles”. Preserve the disclaimer that titles are observed records, not open jobs.

## What to preserve

- Deep navy surfaces, restrained cyan selection, warm amber warnings, and white primary text.
- Read-only, evidence-first framing and explicit snapshot/partial-data language.
- Synchronized visual and semantic organization representations.
- Canonical paths, related teams, observed roles, and official GEDS source links.
- Privacy limits: no contact fields, inferred protected traits, hiring claims, or application actions.

## Stitch design review

### Direction worth keeping

- Sticky left navigation, main workspace, and right profile shell.
- Dedicated active-filter summary instead of an always-open dense filter row.
- Three-column Organization Walk with a pinned breadcrumb and profile.
- Full-height mobile profile concept.
- Concise audit-to-fix decision matrix.

### Rejected deviations

- Product renamed to **Civic Explorer**.
- Invented Analytics, Registry, Snapshots, Settings, “New Unit”, “Admin Access”, user avatar, and export-report actions.
- Invented organizations such as Operations Division and Predictive Modeling, plus fabricated headcount, FTE, budget, and role metrics.
- Decorative office image and avatar despite the no-stock-art/no-avatar constraint.
- Current-state audit screenshots replaced by fabricated gray mockups.
- Screen 2 uses Canadian Museum scope with unrelated invented profile content instead of a single ESDC state.
- Screen 3 does not use the required ESDC / IITB / Enterprise Digital Solutions / IT Services path.

## Implementation plan

### Phase 1 — State trust and source correctness

1. Introduce the canonical selection contract and make URL/history the durable representation.
2. Derive every visible scope, focus, path, profile, and source link from that contract.
3. Add request IDs or abort signals to profile/branch loading and ignore stale responses.
4. Add explicit loading, updating, empty, error, and partial-data states.
5. Add invariant tests for institution/organization ancestry and official GEDS URL identity.

**Exit gate:** automated A-to-B rapid-selection tests never show A data under B, and every state surface names the same institution/team.

### Phase 2 — Responsive shell and hierarchy navigation

1. Implement the desktop 216 px / flexible ≥720 px / 360 px sticky shell.
2. Convert Filters to a disclosure with active-filter summary and clear/reset actions.
3. Rework Organization Walk to three sticky-headed, independently scrolling columns with explicit previous/next controls.
4. Implement the 390 px app bar, filter sheet, semantic-first organization list, and full-height team-profile modal.
5. Preserve URL/back-forward behavior across selection, filter, and profile open/close.

**Exit gate:** Playwright visual and interaction tests pass at 390, 768, 1280, and 1440 px with no clipped primary control or competing page-level scroll.

### Phase 3 — Density, accessibility, and regression protection

1. Group repeated roles and progressive-disclose long lists.
2. Raise link/text contrast to WCAG AA and replace browser-default blue links.
3. Enforce 44 px pointer targets, including transparent constellation hit areas.
4. Add visible focus, selected, loading, warning, and error treatments that do not rely on color alone.
5. Add visual regression snapshots for the trusted desktop state, deep Organization Walk, and open mobile profile.

**Exit gate:** keyboard traversal is complete, axe/contrast checks pass, and approved visual snapshots are stable.

## Verification matrix

| Scenario | Expected result |
| --- | --- |
| Change institution while a team is focused | Focus resets or resolves inside the new institution; no cross-institution profile remains |
| Select A then B before A returns | B stays selected and only B profile/source link renders |
| Open Explorer hash directly | Explorer is the active navigation item |
| Open/close Filters | Disclosure state and active-filter summary are visible and URL state is preserved |
| Traverse a five-level path | Breadcrumb, selected row, newest column, and profile describe the same organization |
| Open a team at 390 px | Full-height profile is complete, close/back stays pinned, and all sections are reachable |
| Inspect official GEDS link | Link belongs to the selected organization, not a fallback or previous selection |
| Review repeated titles | Grouped counts are readable; full raw list is opt-in |

