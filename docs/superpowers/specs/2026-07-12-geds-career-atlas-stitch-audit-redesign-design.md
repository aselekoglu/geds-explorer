# GEDS Career Atlas Stitch Audit and Redesign Design

**Date:** 2026-07-12
**Status:** Superseded by `2026-07-12-geds-public-admin-experience-design.md`
**Surface:** `work/geds-career-atlas` public explorer

> This document records the first Stitch audit direction. Its visual and product
> boundary decisions are no longer current. Use the replacement specification
> for the approved public Career Atlas, private Admin Console, theme, and
> team-to-people experience.

## Goal

Create one Google Stitch project that first explains the current Career Atlas UX problems and then presents a coherent desktop and mobile redesign. The output should make every visual change traceable to a validated audit finding while preserving the product's public, read-only, evidence-first purpose.

This is a design artifact, not an implementation change. It must not invent new data, employment claims, contact fields, crawler controls, or application actions.

## Project Story

The Stitch project uses a five-screen sequence:

1. Current-state audit overview.
2. Redesigned desktop Discover and Constellation.
3. Redesigned desktop Organization Walk.
4. Redesigned mobile discovery and team profile.
5. Before-and-after decision summary.

The sequence should read left to right as `problem -> design response -> responsive proof -> decision record`.

## Shared Visual Direction

- Preserve the existing dark civic-tech identity: deep navy surfaces, restrained cyan selection, warm amber data-quality signals, and white primary text.
- Reduce the number of simultaneous borders and panels. Use spacing, surface tone, and typography before adding containers.
- Keep the interface calm and evidence-led. The constellation remains a functional overview, not decorative artwork.
- Use one consistent 8 px spacing system, 8-12 px control radii, and a restrained three-level surface hierarchy.
- Use cyan only for current selection, primary actions, and accessible links. Use amber only for partial-data warnings.
- All normal text and links must meet WCAG AA contrast. Every interactive control must expose a pointer target of at least 44 by 44 CSS pixels; proportional constellation marks may remain visually smaller only when they receive a transparent 44 px hit area.
- Use real product terminology and representative aggregate data already visible in the supplied screenshots. Do not show names, email addresses, phone numbers, or other contact details.

## Screen 1: Current-State Audit Overview

### Purpose

Establish why the redesign is necessary without turning the board into a wall of notes.

### Composition

- Place the accepted desktop filter/profile mismatch screenshot and mobile screenshot side by side.
- Add no more than six numbered callouts:
  1. Institution filter and selected organization disagree.
  2. The profile can show stale data after a fast selection change.
  3. The active navigation state remains on Discover.
  4. The Filters button has no visible outcome.
  5. The mobile profile is unavailable.
  6. Nested scrolling and low-contrast links obscure the journey.
- Add a short priority strip: `P0 Trust`, `P1 Navigation`, `P1 Responsive`, `P2 Density`.
- Keep proposed solutions off this screen except for one sentence: `Fix state trust before visual polish.`

### Health Summary

Show five compact status rows:

- Entry and filtering: Critical.
- Constellation selection: At risk.
- Organization Walk: Functional but high-friction.
- Team Profile: Critical stale-state risk.
- Mobile journey: Incomplete.

## Screen 2: Redesigned Desktop Discover and Constellation

### Layout

- Use a three-region shell at wide desktop sizes:
  - 208-224 px sticky primary navigation.
  - Flexible main workspace with a minimum usable width of 720 px.
  - 340-380 px sticky, independently scrollable team profile.
- Keep the search field as the dominant entry control.
- Replace the always-visible full filter rail with a compact summary row and a real Filters disclosure. Expanded filters appear directly below the search controls and expose their open state.
- Show a visible current-scope sentence such as `Exploring all government` or `Exploring Canadian Museum of Immigration at Pier 21`.

### State Contract

- Institution, focus, constellation root, Organization Walk path, and profile must describe the same organization scope.
- If the user changes institution, an incompatible selected organization is cleared and the constellation returns to the institution root.
- Selecting a team updates the constellation highlight, breadcrumb, URL state, Organization Walk, and profile together.
- During a profile transition, show a loading state for the newly selected team; never retain the previous team's facts as if they belong to the new selection.

### Constellation

- Retain circle area as the people-indexed measure.
- Reduce visual noise by labelling only the selected node and the largest meaningful neighbours.
- Provide a synchronized visible organization list beside or below the visualization, rather than hiding the list until keyboard focus.
- Give small circles a 44 px transparent pointer target without misrepresenting their quantitative radius.
- Keep the evidence card near the selected node but prevent it from obscuring core clusters.

### Profile

- Keep the selected team's name, canonical path, counts, snapshot date, quality warning, and official source above the fold.
- Use high-contrast cyan links with visible focus treatment.
- Summarize repeated observed titles as counts, for example `Senior Analyst x24`, with an explicit action to reveal the full observed list.

## Screen 3: Redesigned Desktop Organization Walk

### Layout

- Keep the desktop multi-column hierarchy model.
- Pin the full canonical breadcrumb below the command bar.
- Keep primary navigation and the selected team profile visible while the user scrolls through the hierarchy.
- Show two or three useful columns depending on available workspace width. Opening a child automatically brings the new column into view.
- Visually distinguish the active column and selected row without relying on color alone.
- Replace the raw native horizontal scrollbar as the primary affordance with visible previous/next column controls; horizontal scrolling may remain as a secondary input.

### Column Behaviour

- Each column may retain a virtualized vertical list, but the page must not introduce another competing vertical scroll region around the column set.
- Column headings name the parent organization and remain visible while their list scrolls.
- Back, Left Arrow, Right Arrow, Enter, typeahead, and pointer interactions all update the same selection state.
- Empty child states explain that the selected organization has no indexed child teams and provide a clear path to its profile.

## Screen 4: Redesigned Mobile Discovery and Team Profile

### Layout

- Use a compact top app bar with brand, current section, and a single navigation-menu control. Do not use a clipped horizontal navigation strip.
- Stack search and primary actions in one column.
- Filters open in an accessible full-width sheet and return a concise active-filter summary after application.
- Use the visible semantic organization list as the primary mobile constellation experience; the spatial map remains an optional overview below it.

### Team Profile

- Selecting a team opens a full-height modal profile sheet with a persistent close/back control. The redesign does not introduce a separate mobile route.
- The sheet announces the selected team and loading transition to assistive technology.
- Facts, quality warning, official source, role summary, related teams, and career-conversation leads remain reachable without switching to desktop.
- No selected profile content may be removed from the accessibility tree solely because the viewport is below 1000 px.

## Screen 5: Before-and-After Decision Summary

Use a compact mapping table with five rows:

| Audit finding | Design response | Verification target |
| --- | --- | --- |
| Filter and focus mismatch | One URL-backed selection/scope contract | Every surface names the same institution and team |
| Stale profile | Clear previous data and guard request order | Rapid A-to-B selection never renders A under B |
| Wrong active navigation | Hash/section-aware navigation state | Visible section and active nav agree |
| Profile hidden on mobile | Full-height mobile profile view | Complete profile journey at 390 px |
| Nested scroll and density | Sticky shell, guided columns, grouped roles | Profile remains visible and scroll ownership is clear |

End with three implementation phases:

1. State trust and loading correctness.
2. Responsive shell and Organization Walk.
3. Density, contrast, hit targets, and visual regression coverage.

## Stitch Production Instructions

- Create a single project titled `GEDS Career Atlas - UX Audit and Redesign`.
- Generate screens in the five-screen order above so Stitch maintains a shared visual system.
- Use the current screenshots as reference images where Stitch supports image input.
- Generate desktop screens at approximately 1440 x 1024 and the mobile screen at approximately 390 x 844.
- Prefer editable UI components and real text over decorative raster treatments.
- Do not add generic dashboard charts, glassmorphism, gradients beyond the existing restrained background glow, stock illustrations, avatars, or invented Government of Canada branding.
- After every generation, compare terminology, selected organization, filter scope, and profile content across the screen before accepting it.

## Acceptance Criteria

- The project contains all five screens in order and uses one consistent visual system.
- The audit screen ties each issue to visible evidence and prioritizes state trust.
- Desktop redesign keeps navigation and profile context visible during Constellation and Organization Walk use.
- Institution, selection, breadcrumb, URL state, and profile are visually consistent.
- Mobile includes a complete, reachable team-profile journey.
- No dead controls are shown.
- Links, warnings, selection, and active navigation do not rely on color alone.
- Repeated roles are summarized without hiding access to observed source titles.
- The artifact does not expose personal contact data or imply that observed leaders are hiring managers.

## Evidence Limits

The design is grounded in the supplied Chrome screenshots and the live audit captures at desktop, 1280 px, and 390 px. It does not claim full WCAG compliance or cross-browser parity. Those claims require implementation-level keyboard, screen-reader, zoom, contrast, and browser verification.
