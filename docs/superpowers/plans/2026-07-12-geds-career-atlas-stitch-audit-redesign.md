# GEDS Career Atlas Stitch Audit and Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create and visually verify one Google Stitch project containing a five-screen GEDS Career Atlas audit-to-redesign story.

**Architecture:** Treat Stitch as the external design runtime and the approved repo spec plus three accepted screenshots as the source of truth. Generate each screen inside one Stitch project, inspect every result before continuing, and use narrow refinement prompts when a screen violates the state, privacy, responsive, or visual constraints. Do not modify Career Atlas source code or export generated frontend code in this plan.

**Tech Stack:** Google Stitch at `https://stitch.withgoogle.com`, the user's signed-in Chrome session, Stitch text and image inputs, Codex Browser screenshot inspection, and the existing GEDS Career Atlas audit evidence.

## Global Constraints

- Project title: `GEDS Career Atlas - UX Audit and Redesign`.
- Produce exactly five accepted screens in this order: audit overview, desktop Discover and Constellation, desktop Organization Walk, mobile discovery and team profile, before-and-after summary.
- Preserve the existing dark civic-tech identity: deep navy surfaces, restrained cyan selection, warm amber partial-data signals, and white primary text.
- Use one 8 px spacing system, 8-12 px control radii, and three restrained surface levels.
- Every interactive control exposes a pointer target of at least 44 by 44 CSS pixels; proportional constellation marks may remain visually smaller only with a transparent 44 px hit area.
- Normal text and links must meet WCAG AA contrast; state must not rely on colour alone.
- Use representative aggregate values already present in the audit, including July 9, 2026, 193,163 people records, 26,421 organization units, and 156 institutions.
- Do not expose names, email addresses, phone numbers, other contact fields, crawler controls, job application actions, or claims that observed leaders are hiring managers.
- Do not add stock illustrations, avatars, generic dashboard charts, glassmorphism, heavy gradients, or invented Government of Canada branding.
- Do not edit repo UI code or export Stitch-generated code during this plan.

## Source Material

- Approved design spec: `docs/superpowers/specs/2026-07-12-geds-career-atlas-stitch-audit-redesign-design.md`.
- Desktop mismatch evidence: `C:/Users/asele/.codex/visualizations/2026/07/12/019f53ee-4b6f-79d3-9e9a-90b7b4043d24/02-filter-focus-mismatch.jpg`.
- Mobile evidence: `C:/Users/asele/.codex/visualizations/2026/07/12/019f53ee-4b6f-79d3-9e9a-90b7b4043d24/03-mobile-panel-open.jpg`.
- Organization Walk evidence: `C:/Users/asele/.codex/visualizations/2026/07/12/019f53ee-4b6f-79d3-9e9a-90b7b4043d24/04-explorer-anchor-1280.jpg`.
- Official Stitch capability reference: Google Stitch accepts natural-language and image inputs and supports iterative variants; verify the current surface at execution time before relying on a particular control label.

---

### Task 1: Validate Inputs and Open Stitch

**Files:**
- Read: `docs/superpowers/specs/2026-07-12-geds-career-atlas-stitch-audit-redesign-design.md`
- Read: the three image files under `C:/Users/asele/.codex/visualizations/2026/07/12/019f53ee-4b6f-79d3-9e9a-90b7b4043d24/`
- Modify: none

**Interfaces:**
- Consumes: the approved spec and three accepted JPEG screenshots.
- Produces: one claimed Chrome tab showing the authenticated Stitch home or project-creation surface.

- [ ] **Step 1: Verify the three evidence files exist and are non-empty**

Run:

```powershell
Get-Item -LiteralPath `
  'C:\Users\asele\.codex\visualizations\2026\07\12\019f53ee-4b6f-79d3-9e9a-90b7b4043d24\02-filter-focus-mismatch.jpg', `
  'C:\Users\asele\.codex\visualizations\2026\07\12\019f53ee-4b6f-79d3-9e9a-90b7b4043d24\03-mobile-panel-open.jpg', `
  'C:\Users\asele\.codex\visualizations\2026\07\12\019f53ee-4b6f-79d3-9e9a-90b7b4043d24\04-explorer-anchor-1280.jpg' |
  Select-Object Name, Length
```

Expected: three rows and every `Length` is greater than zero.

- [ ] **Step 2: Inspect each screenshot before upload**

Open each image with the local image viewer. Accept only images showing, respectively, the filter/profile mismatch, the 390 px mobile header/filter state, and the Organization Walk column state. Do not upload a blank, cropped, or incorrect image.

- [ ] **Step 3: Open Stitch in the existing Chrome session**

Open `https://stitch.withgoogle.com` in Chrome, read the current DOM, and claim the Stitch tab. Confirm the page title and meaningful product content before acting.

Expected: Stitch home, project list, or project-creation surface renders without a browser error page.

- [ ] **Step 4: Resolve authentication if needed**

If Stitch shows a Google sign-in wall, stop and ask the user to sign in in the claimed Chrome tab. Continue only after the signed-in project surface is visible. Do not inspect cookies, profiles, or account storage.

- [ ] **Step 5: Record the preflight result**

Capture one viewport screenshot of the authenticated Stitch start surface for internal verification. Do not create a project until the image and prompt inputs are ready.

### Task 2: Create the Project and Establish the Shared Theme

**Files:**
- Read: `docs/superpowers/specs/2026-07-12-geds-career-atlas-stitch-audit-redesign-design.md`
- Modify: none

**Interfaces:**
- Consumes: the authenticated Stitch surface from Task 1.
- Produces: one Stitch project named `GEDS Career Atlas - UX Audit and Redesign` with a shared design brief.

- [ ] **Step 1: Start one new Stitch project**

Use the current Stitch project-creation control exposed by the DOM. Name the project exactly:

```text
GEDS Career Atlas - UX Audit and Redesign
```

Expected: one project workspace opens and the project title is visible.

- [ ] **Step 2: Submit the shared visual-system brief**

Use this exact project brief:

```text
Design a coherent five-screen UX audit and redesign story for GEDS Career Atlas, a public read-only explorer of Government of Canada organization and observed career data. Preserve the existing dark civic-tech identity: deep navy surfaces, restrained cyan for selection and links, warm amber only for partial-data warnings, and high-contrast white text. Use an 8 px spacing system, 8-12 px control radii, three restrained surface levels, and calm information hierarchy. Do not add stock illustrations, avatars, generic dashboard charts, glassmorphism, heavy gradients, invented Government of Canada branding, contact fields, crawler controls, job application actions, or claims that anyone is hiring. Use real product terminology and representative aggregate values: July 9, 2026; 193,163 people records; 26,421 organization units; 156 institutions. Every state must be understandable without colour alone, all links must be high contrast, and interactive targets must be at least 44 by 44 CSS pixels.
```

Expected: Stitch accepts the brief without replacing the product with a generic analytics dashboard.

- [ ] **Step 3: Inspect the generated theme before generating screens**

Check surface colours, text contrast, control radii, spacing density, typography hierarchy, and absence of forbidden imagery. If the generated theme introduces purple gradients, glass cards, avatars, or decorative charts, submit this refinement:

```text
Remove decorative dashboard styling. Return to a restrained civic information explorer: flat deep-navy surfaces, subtle borders, cyan only for selection and links, amber only for partial-data warnings, no avatars, no stock art, no charts, no glassmorphism, and no purple gradient.
```

Expected: the visual system matches the approved constraints before Screen 1 is accepted.

### Task 3: Generate Screen 1 - Current-State Audit Overview

**Files:**
- Upload: `02-filter-focus-mismatch.jpg`
- Upload: `03-mobile-panel-open.jpg`
- Upload: `04-explorer-anchor-1280.jpg`
- Modify: none

**Interfaces:**
- Consumes: the shared project theme and three audit screenshots.
- Produces: accepted Screen 1 named `01 Current-State Audit`.

- [ ] **Step 1: Upload the three audit screenshots**

Use Stitch image input and upload only the three files listed above. Confirm each thumbnail shows the expected Career Atlas state before submitting the generation prompt.

- [ ] **Step 2: Generate the audit overview**

Submit this exact prompt with the three images attached:

```text
Create a desktop design-review screen titled "GEDS Career Atlas UX Audit" using the attached screenshots as evidence. Keep the screenshots readable and place no more than six numbered callouts: 1 Institution filter and selected organization disagree. 2 Team profile can remain stale after a fast selection change. 3 Active navigation remains on Discover. 4 Filters button has no visible outcome. 5 Mobile team profile is unavailable. 6 Nested scrolling and low-contrast links obscure the journey. Add a compact priority strip: P0 Trust, P1 Navigation, P1 Responsive, P2 Density. Add five health rows: Entry and filtering - Critical; Constellation selection - At risk; Organization Walk - Functional but high-friction; Team Profile - Critical stale-state risk; Mobile journey - Incomplete. Include one sentence only for the design response: "Fix state trust before visual polish." Do not invent additional findings or solutions.
```

- [ ] **Step 3: Inspect Screen 1**

Verify all three screenshots are present, callout numbers match the correct evidence, no personal data appears, and the audit remains readable at a desktop viewport. Reject the screen if screenshots are replaced by fabricated mockups.

- [ ] **Step 4: Refine only if acceptance fails**

Use one narrow correction prompt naming the failed item. Example for excessive text:

```text
Keep the same evidence and findings, but reduce the audit annotations to the six approved numbered callouts and five health rows. Do not add paragraphs or new recommendations.
```

- [ ] **Step 5: Rename and capture**

Rename the accepted screen `01 Current-State Audit`. Capture a screenshot showing the complete accepted screen.

### Task 4: Generate Screen 2 - Desktop Discover and Constellation

**Files:**
- Use as image reference: `02-filter-focus-mismatch.jpg`
- Modify: none

**Interfaces:**
- Consumes: the shared theme and current desktop evidence.
- Produces: accepted Screen 2 named `02 Desktop Discover and Constellation` at approximately 1440 x 1024.

- [ ] **Step 1: Generate the redesigned desktop screen**

Submit this exact prompt with `02-filter-focus-mismatch.jpg` attached:

```text
Redesign this GEDS Career Atlas desktop screen at approximately 1440 x 1024 while preserving its dark civic-tech identity and real terminology. Use a 216 px sticky left navigation, a flexible main workspace at least 720 px wide, and a 360 px sticky independently scrollable team profile. Keep Career interest as the dominant input. Replace the always-open filter row with a compact active-filter summary and a real Filters disclosure with visible expanded/collapsed state. Show the current scope sentence "Exploring all government". In the constellation, keep circle area equal to people indexed, label only the selected node and largest meaningful neighbours, show a visible synchronized organization list, give small circles a transparent 44 px hit target, and place the evidence card so it does not cover core clusters. Show one consistent selection: Employment and Social Development Canada across filter scope, selected circle, breadcrumb, and profile. Keep profile name, canonical path, observed people, people in branch, child teams, snapshot July 9, 2026, partial-data warning, and official GEDS source above the fold. Summarize repeated titles as "Senior Analyst x24" and "IT Analyst x18" with a "View all observed titles" action. Use high-contrast cyan links and visible focus states. Do not show conflicting institutions, stale profile content, contact data, or job application actions.
```

- [ ] **Step 2: Inspect state consistency**

Read the visible institution filter, scope sentence, selected constellation node, breadcrumb, and profile title. All must name Employment and Social Development Canada or an organization inside that same hierarchy. Reject any mixed Canadian Museum/ESDC/CRTC state.

- [ ] **Step 3: Inspect layout and accessibility**

Verify sticky regions are visually distinct, main content is not squeezed below 720 px, links are cyan rather than browser-default blue, small circles have clear interaction affordance, and no dead Filters button is depicted.

- [ ] **Step 4: Correct only observed failures**

For a state mismatch, use:

```text
Correct the state contract without changing the layout: every institution label, selected constellation node, breadcrumb, and profile must belong to Employment and Social Development Canada. Remove all Canadian Museum and CRTC references from this screen.
```

- [ ] **Step 5: Rename and capture**

Rename the accepted screen `02 Desktop Discover and Constellation`. Capture a screenshot of the complete accepted screen.

### Task 5: Generate Screen 3 - Desktop Organization Walk

**Files:**
- Use as image reference: `04-explorer-anchor-1280.jpg`
- Modify: none

**Interfaces:**
- Consumes: the shared theme and Organization Walk evidence.
- Produces: accepted Screen 3 named `03 Desktop Organization Walk` at approximately 1440 x 1024.

- [ ] **Step 1: Generate the redesigned Organization Walk**

Submit this exact prompt with `04-explorer-anchor-1280.jpg` attached:

```text
Redesign the GEDS Career Atlas Organization Walk desktop screen at approximately 1440 x 1024. Preserve the dark civic-tech theme and multi-column hierarchy model. Keep the 216 px left navigation and 360 px selected team profile visible and sticky. Pin a full canonical breadcrumb below the command bar. Show three useful hierarchy columns with sticky parent headings, virtualized vertical lists, a clearly selected row, and explicit previous/next column controls. Opening a child should visually bring the new column into view. Avoid a raw horizontal scrollbar as the primary navigation affordance and avoid a second vertical scroll around the entire column set. Use one consistent path: Employment and Social Development Canada / Deputy Minister of Employment and Social Development / Innovation, Information and Technology Branch / Enterprise Digital Solutions Directorate / IT Services. In the profile, show IT Services with counts, July 9, 2026 snapshot, partial-data warning, official GEDS link, grouped observed roles, and related teams. Distinguish active column and selected row with border, icon, and text treatment rather than colour alone.
```

- [ ] **Step 2: Inspect hierarchy continuity**

Verify the breadcrumb, selected row, newest column heading, and profile title all describe the same IT Services path. Reject duplicated, skipped, or unrelated hierarchy levels.

- [ ] **Step 3: Inspect scroll ownership**

Confirm each hierarchy column visually owns its vertical list, the whole column set has no competing outer vertical scrollbar, and previous/next column controls are visible.

- [ ] **Step 4: Correct only observed failures**

For an obscured profile or navigation region, use:

```text
Keep the approved content and hierarchy, but make the left navigation, canonical breadcrumb, and right team profile visibly sticky while the centre hierarchy columns scroll independently.
```

- [ ] **Step 5: Rename and capture**

Rename the accepted screen `03 Desktop Organization Walk`. Capture a screenshot of the complete accepted screen.

### Task 6: Generate Screen 4 - Mobile Discovery and Team Profile

**Files:**
- Use as image reference: `03-mobile-panel-open.jpg`
- Modify: none

**Interfaces:**
- Consumes: the shared theme and mobile evidence.
- Produces: accepted Screen 4 named `04 Mobile Discovery and Profile` at approximately 390 x 844.

- [ ] **Step 1: Generate the redesigned mobile screen**

Submit this exact prompt with `03-mobile-panel-open.jpg` attached:

```text
Redesign GEDS Career Atlas for a 390 x 844 mobile viewport. Preserve the dark civic-tech identity. Replace the clipped horizontal navigation with a compact app bar containing the GEDS Career Atlas brand, current section label, and one 44 px navigation-menu button. Stack Career interest and primary actions in one column. Show a compact active-filter summary and an accessible full-width Filters sheet affordance. Make the visible semantic organization list the primary mobile constellation experience and place the spatial overview below it as optional context. Show the selected team in an open full-height modal profile sheet with a persistent 44 px close/back control. The sheet must show IT Services, canonical path, observed people, people in branch, child teams, snapshot July 9, 2026, partial-data warning, high-contrast official GEDS link, grouped observed roles, related teams, and career-conversation leads. Do not hide profile content on mobile, do not use a separate mobile route, and do not use a horizontally scrolling navigation strip.
```

- [ ] **Step 2: Inspect mobile completeness**

Verify the app bar is not clipped, the profile sheet is visibly open, the close/back control is persistent, and profile content is reachable within the mobile design.

- [ ] **Step 3: Inspect touch and reading order**

Confirm controls are at least 44 px, filter state appears before results, team selection leads to the profile sheet, and warning/source content appears before long role and lead lists.

- [ ] **Step 4: Correct only observed failures**

For hidden or truncated profile content, use:

```text
Keep the same mobile design, but make the selected IT Services profile a full-height modal sheet inside the 390 x 844 viewport. Keep the close/back control pinned and make every profile section vertically reachable without switching to desktop.
```

- [ ] **Step 5: Rename and capture**

Rename the accepted screen `04 Mobile Discovery and Profile`. Capture a screenshot of the complete accepted screen.

### Task 7: Generate Screen 5 - Before-and-After Decision Summary

**Files:**
- Read: the four accepted Stitch screens.
- Modify: none

**Interfaces:**
- Consumes: accepted Screens 1-4.
- Produces: accepted Screen 5 named `05 Before and After Summary`.

- [ ] **Step 1: Generate the summary screen**

Submit this exact prompt:

```text
Create a concise final decision screen titled "GEDS Career Atlas - Audit to Redesign" using the same visual system as the previous screens. Show a five-row mapping table with these exact relationships: Filter and focus mismatch -> One URL-backed selection and scope contract -> Every surface names the same institution and team. Stale profile -> Clear previous data and guard request order -> Rapid A-to-B selection never renders A under B. Wrong active navigation -> Hash and section-aware navigation state -> Visible section and active navigation agree. Profile hidden on mobile -> Full-height mobile profile sheet -> Complete profile journey at 390 px. Nested scroll and density -> Sticky shell, guided columns, grouped roles -> Profile remains visible and scroll ownership is clear. End with three implementation phases: 1 State trust and loading correctness. 2 Responsive shell and Organization Walk. 3 Density, contrast, hit targets, and visual regression coverage. Keep the screen concise and do not add new findings or roadmap items.
```

- [ ] **Step 2: Inspect mapping accuracy**

Compare every row against the approved spec. Reject rewritten claims that weaken the verification target or introduce unapproved features.

- [ ] **Step 3: Inspect project continuity**

Confirm Screen 5 uses the same typography, navy surfaces, cyan/amber semantics, spacing, and control radii as Screens 1-4.

- [ ] **Step 4: Rename and capture**

Rename the accepted screen `05 Before and After Summary`. Capture a screenshot of the complete accepted screen.

### Task 8: Final Visual QA and Handoff

**Files:**
- Read: all five Stitch screens.
- Create outside repo: five final screenshots in the active Codex visualization directory.
- Modify: none

**Interfaces:**
- Consumes: the complete five-screen Stitch project.
- Produces: verified Stitch project URL plus five final screenshots and a concise QA report.

- [ ] **Step 1: Verify screen inventory and order**

Confirm the project contains exactly these accepted screen names in order:

```text
01 Current-State Audit
02 Desktop Discover and Constellation
03 Desktop Organization Walk
04 Mobile Discovery and Profile
05 Before and After Summary
```

- [ ] **Step 2: Run the cross-screen state ledger**

For Screens 2-4, record the visible institution, selected organization, breadcrumb/path, and profile title. Expected: no screen mixes ESDC, Canadian Museum, and CRTC state; Screens 3-4 consistently use IT Services inside ESDC.

- [ ] **Step 3: Run the privacy and trust ledger**

Search visible screen text for email-like strings, phone numbers, personal names, `Apply`, `Start crawler`, and claims that a lead is hiring. Expected: none appear. Confirm partial-data and official-source language remains visible.

- [ ] **Step 4: Run the visual-system ledger**

Compare all screens for consistent navy surfaces, cyan selection/links, amber warnings, white text, spacing, typography, radii, and absence of forbidden decorative styling.

- [ ] **Step 5: Capture accepted screenshots**

Save one screenshot per accepted screen in the active Codex visualization directory with filenames:

```text
01-stitch-current-state-audit.jpg
02-stitch-desktop-constellation.jpg
03-stitch-desktop-org-walk.jpg
04-stitch-mobile-profile.jpg
05-stitch-decision-summary.jpg
```

Open and inspect every saved file. Reject blank, cropped, loading, or wrong-screen captures.

- [ ] **Step 6: Preserve the Stitch project for handoff**

Leave the Stitch project tab open as a deliverable and record its current URL and visible project title. Do not export code or paste to Figma.

- [ ] **Step 7: Report the result**

Return the Stitch project URL first, state whether all five screens passed the state/privacy/visual ledgers, list any remaining Stitch limitations, and render the five final screenshots consecutively at the end of the report.
