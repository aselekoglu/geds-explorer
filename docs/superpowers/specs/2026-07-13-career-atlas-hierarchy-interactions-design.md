# Career Atlas Hierarchy-First Interactions

**Date:** 2026-07-13
**Status:** Approved interaction design, pending written-spec review
**Surface:** Public, read-only Career Atlas

## Goal

Make both hierarchy surfaces behave like hierarchy browsers. Clicking an organization row or bubble drills into its children; opening Team Profile becomes an explicit secondary action. Replace the persistent constellation evidence panel with a compact hover/focus card, improve labels, add one-level Back navigation, and make observed-role clicks filter the user's current view.

## Interaction Contract

Every organization node exposes two distinct actions:

1. **Primary hierarchy action:** clicking the row or bubble drills into that node when it has children.
2. **Secondary detail action:** a small, labelled detail button opens Team Profile without changing the hierarchy root.

These actions must not be nested interactive elements. Organization Walk renders a row button and a sibling detail button inside one visual card. The constellation bubble is the primary SVG button; its hover/focus card contains the separate Team Profile button. A sibling information affordance is exposed for coarse-pointer/touch input so detail access never depends on hover.

For a leaf node, the primary action selects the leaf and shows a compact `No child teams` state without opening Team Profile. The explicit detail button remains the only profile-opening action.

## Organization Walk

Each organization card contains the name and existing team/people summary plus a compact detail icon button with an accessible name such as `Open Chairperson's Office profile`.

- Clicking the card body or pressing Enter/ArrowRight opens the next hierarchy column.
- Clicking the detail button calls the shared profile-selection callback only.
- Clicking a leaf card advances the breadcrumb selection and renders `No child teams` in the next column.
- The detail button is reachable independently by keyboard and does not trigger the card action.

`OrganizationExplorer` therefore receives separate `onDrill`-internal behavior and `onProfile(orgId)` callback semantics. App profile state is no longer updated by the row's primary action.

## Discover Constellation

### Drill and Back

Clicking a bubble with children pushes its organization ID onto a root-history stack and requests the next bounded constellation slice. It does not open Team Profile.

A `Back` button appears at the left edge of the Discover heading whenever the stack contains a deeper root. Each press removes exactly one root and restores the previous slice. The button is hidden at the selected institution root and at the government-wide root.

Changing Institution clears root history, hover state, selected leaf state, and any stale Team Profile. Browser-visible query state continues to preserve the selected institution and view; hierarchy history remains lightweight view state for this iteration.

Clicking a leaf bubble records the leaf as selected and exposes `No child teams` through the hover/focus card. It does not push an empty slice and does not open Team Profile.

### Hover and Focus Card

The fixed `constellation-evidence` panel and `Explore branch` button are removed.

Hovering or keyboard-focusing a bubble shows a small anchored card near that bubble. The card contains:

- full organization name;
- people directly in this organization;
- total people in this organization and descendants;
- immediate child-team count;
- a compact `Open profile` button;
- `No child teams` when applicable.

The card stays open while the bubble or card has hover/focus. It repositions inside the stage bounds so it does not cover the viewport edge. On touch devices, tapping the bubble still drills; tapping its separate information affordance opens the same facts card, whose explicit detail button opens the profile.

To avoid one request per hover, `direct_people_count` is added to the existing public `OrgNode` payload. The canonical organization table already stores this source-derived count. No contact or admin fields are added.

## Bubble Labels and Abbreviations

The government-wide top level uses a short organization label inside each sufficiently large bubble and exposes the full name in the hover/focus card and SVG accessible name.

Short labels are deterministic display abbreviations, not claimed to be official acronyms:

- use a small reviewed mapping for common Government of Canada institutions where the conventional abbreviation is known, including `CRTC`, `CRA`, `ESDC`, `SSC`, `ISED`, `PSPC`, `DFO`, and `TBS`;
- otherwise derive initials after dropping connector words and cap the result at six characters;
- if no useful abbreviation can be derived, use the first compact word segment.

Below the government-wide level, full names are preferred. SVG text wraps across multiple centered lines when the bubble has enough area. Text is never replaced with an ellipsis. Small bubbles omit internal text and rely on hover/focus plus the accessible list fallback.

## View-Aware Role Query

Every non-empty Observed Role heading becomes a button. Clicking it writes the normalized role title into the shared Career interest query without changing the active hash view, then closes Team Profile.

### From Discover

The existing Discover query flow filters search results and matching constellation nodes. The view remains `#discover`.

### From Organization Walk

The view remains `#explorer`. Organization Walk requests the existing deterministic `/api/search?q=...` results, scopes them to the selected institution, deduplicates organization IDs, and renders a `Matching teams` result lane above the hierarchy columns.

Each result has the same two-action contract:

- the primary result action restores that organization's ancestor path and opens its hierarchy position;
- the secondary detail button opens Team Profile.

Clearing the shared query removes the result lane and restores the current unfiltered hierarchy columns. Empty and failed search states are explicit. Search results never expose contact fields.

## Component Boundaries

- `App`: owns shared query, active public view, institution scope, and Team Profile ID; exposes `applyRoleQuery(title)` that preserves the current view.
- `OrganizationExplorer`: owns hierarchy columns and filtered result-lane state; never opens a profile from a primary row click.
- `OrgColumn`: renders sibling primary and detail controls and retains tree keyboard navigation.
- `ConstellationPage`: owns root-history stack, hover/selected leaf state, slice loading, and Back behavior.
- `Constellation`: renders wrapped/abbreviated labels and reports drill intent and hover/focus node separately.
- `ConstellationHoverCard`: renders bounded node facts and the explicit profile action.
- `GroupedRoles`: renders role-query buttons through an `onRoleQuery(title)` callback.
- `CareerRepository`: includes `direct_people_count` in public organization nodes.

## Accessibility

- Row, bubble, detail, Back, and role-query actions have distinct accessible names.
- The hover card also appears on keyboard focus and is associated with its bubble through ARIA description.
- Wrapped SVG labels do not replace full accessible organization names.
- Detail buttons are never nested inside another button.
- Escape continues to close Team Profile and returns focus to the invoking detail button when available.
- Reduced-motion rules apply to hover-card transitions.

## Error and Empty States

- Failed child-slice loads retain the current root and show a retryable status rather than an empty canvas.
- Leaf drill attempts show `No child teams` without issuing an unnecessary slice request.
- A role query with no matching teams shows one empty result-lane message and leaves the hierarchy navigable.
- A search failure shows an error in the result lane and leaves existing hierarchy columns intact.
- Unknown abbreviations fall back to deterministic compact initials; the full name is always available.

## Testing Strategy

1. Organization Walk card click opens children but does not call `onProfile`; detail click calls `onProfile` but does not load children.
2. Bubble click pushes a child root without opening profile; hover/focus exposes facts; detail click opens profile.
3. Back pops one root at a time and disappears at the institution/government root.
4. Leaf clicks do not request an empty slice and announce `No child teams`.
5. Top-level labels use reviewed/fallback abbreviations; lower-level large bubbles render untruncated wrapped names.
6. `direct_people_count` is present in organization and constellation API payloads with repository/API regression coverage.
7. Role click updates shared query, closes the drawer, and preserves `#discover` or `#explorer`.
8. Organization Walk role queries display institution-scoped, deduplicated matching teams and restore paths from a result.
9. Desktop, dark/light, narrow viewport, pointer hover, touch selection, and keyboard focus are browser-verified.

## Acceptance Criteria

1. Primary organization interactions drill into hierarchy and never open Team Profile.
2. Team Profile opens only from a dedicated compact detail control.
3. Discover provides one-level Back navigation through drilled roots.
4. The persistent `Explore branch` evidence panel is absent.
5. Hover/focus cards show direct people, total branch people, child teams, full name, and profile action without blocking the canvas.
6. Lower-level bubble names are not ellipsized; top-level bubbles use abbreviations with full names on hover/focus.
7. Observed Role clicks filter the current Discover or Organization Walk view without navigating between them.
8. Leaf and empty states are explicit and accessible.
9. Public data remains read-only and privacy-safe.
