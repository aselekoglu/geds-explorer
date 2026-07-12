# GEDS Public Career Atlas and Private Admin Experience Design

**Date:** 2026-07-12
**Status:** Implemented and verified on `codex/public-admin-experience`
**Replaces:** `2026-07-12-geds-career-atlas-stitch-audit-redesign-design.md`
**Public surface:** `work/geds-career-atlas`
**Private surface:** `work/geds-crawler`

## Decision Summary

GEDS Career Atlas and the crawler Admin Console are separate products with a
narrow publication boundary. Both products support light and dark themes, but
they do not share routes, navigation, permissions, or operational actions.

The public Career Atlas uses the approved red-and-white light direction as its
default. Its dark theme is a purpose-designed companion palette rather than a
mechanical color inversion. The private Admin Console uses the same semantic
theme foundation so the products feel related, while retaining a denser,
operator-oriented layout.

Career Atlas exposes the people observed in a selected leaf team. A person row
shows the observed display name, observed title, an explicitly observed
classification when available, and a link to the person's official GEDS record.
Career Atlas does not reproduce phone, email, address, or other contact fields.

## Product Boundary

### Public Career Atlas

Career Atlas is a public, read-only discovery experience. Its allowed surfaces
are:

- Discover and career-interest search.
- Government Explorer and Organization Walk.
- Constellation.
- Guided Tours.
- Team profiles, observed people, observed roles, related teams, and career
  conversation leads.
- About the data, including canonical snapshot date, methodology, aggregate
  coverage, and public-facing quality limitations.
- Links to official GEDS organization and person records.

Career Atlas must not expose:

- Crawler health, heartbeats, queues, throughput, errors, or logs.
- Run history, schedules, retry controls, or crawl configuration.
- Start, stop, resume, delete, promote, or publish actions.
- Raw database paths, source pickers, staging state, or canonical-promotion
  diagnostics.
- Contact fields copied from GEDS.
- Claims that an observed person is a hiring manager or associated with a live
  competition.

All public application requests remain GET-only. The public frontend must never
call an `/api/control/*` route.

### Private Admin Console

The Admin Console is an authenticated operator product. Its allowed surfaces
are:

- Operational overview and health.
- Crawlers and active runs.
- Run history and error details.
- Coverage and completeness diagnostics.
- Schedules and crawl configuration.
- Snapshot Data, staging inspection, canonical promotion, and publication.
- Start, stop, resume, retry, delete, and other authorized mutations.

Production access requires authentication, authorization, TLS, and CSRF
protection for state-changing browser requests. A prominent `Private admin`
identifier remains visible in both themes.

### Publication Boundary

The Admin Console validates and promotes a canonical snapshot. Career Atlas
reads the published canonical representation through a read-only repository or
API. It does not read live queues or staging databases.

```text
Crawler runs and overlays
          |
          v
Private validation and canonical promotion
          |
          v
Immutable published snapshot / read-only API
          |
          v
Public Career Atlas
```

Publication failure leaves the previously published canonical snapshot active.
Career Atlas displays the active snapshot's date and quality status; it does not
display failed promotion internals.

## Theme System

### Shared Semantic Foundation

Both products use semantic tokens for:

- Page, surface, elevated surface, and inset surface.
- Primary and secondary text.
- Border and divider.
- Brand accent and accent interaction states.
- Information, success, warning, and danger.
- Focus ring, selected state, and disabled state.

Components consume semantic tokens rather than hard-coded light or dark colors.
Each product may tune density and component composition without redefining token
meaning.

### Light Theme

- Default theme for Career Atlas.
- Uses the approved Stitch red-and-white direction: white and soft-neutral
  surfaces, dark neutral text, and restrained red for primary actions, current
  navigation, and selection.
- Warning amber remains distinct from brand red.
- Large red fills are reserved for decisive actions and selected states; normal
  content remains calm and readable.
- Government of Canada wordmarks, signatures, flags, or official identifiers
  are used only when an approved source asset and permission exist. The palette
  alone must not imply that Career Atlas is an official Government of Canada
  service.

### Dark Theme

- Available in both Career Atlas and the Admin Console.
- Uses deep neutral or navy surfaces with warm off-white text and a red-family
  accent derived from the light direction.
- Does not reuse the current bright cyan as the dominant brand accent.
- Selected, warning, error, and link states remain distinguishable without
  relying on color alone.
- Surface hierarchy is created with tone, spacing, and limited borders; it is
  not a literal inversion of the light palette.

### Theme Behaviour

- Both applications expose a visible theme control with `Light`, `Dark`, and
  `System` choices.
- The user's explicit choice is persisted per application.
- If no explicit choice exists, Career Atlas starts in light mode and the Admin
  Console follows the system preference.
- Theme changes do not alter available routes, data, or permissions.
- Both themes must meet WCAG AA contrast for normal text, controls, links, and
  focus indicators.

## Information Architecture

### Career Atlas Navigation

- Discover.
- Government Explorer.
- Constellation.
- Tours.
- About the data.

### Admin Console Navigation

- Overview.
- Crawlers.
- Run History.
- Coverage.
- Schedules.
- Snapshot Data.

Public navigation contains no Admin link. Admin navigation contains an explicit
link that opens the public Career Atlas in a separate context, but Career Atlas
does not provide a reciprocal discovery link to the private console.

## Organization Walk and People Experience

### Hierarchy Journey

Organization Walk follows the canonical hierarchy:

```text
Institution -> Branch -> Directorate -> Division -> Team -> People in this team
```

The exact labels are data-driven; not every institution contains every named
level. The interface shows the available hierarchy without manufacturing
missing levels.

Selecting an organization synchronizes:

- URL focus state.
- Canonical breadcrumb.
- Active hierarchy row and column.
- Constellation selection where applicable.
- Team or organization profile.

A leaf team is an organization with no indexed child organizations. Selecting
it reveals its direct people. For a non-leaf organization, the profile shows
aggregate branch counts and offers an explicit `Include descendant teams`
control rather than silently mixing direct and descendant people.

### People in This Team

The leaf-team profile contains a `People in this team` section after the team's
summary and quality notice. Desktop uses a compact responsive table; narrow
screens use stacked rows with the same information order.

Each person row contains:

1. Observed display name.
2. Observed title, preserved verbatim apart from whitespace normalization.
3. Observed classification badge when the source text supports it.
4. Observed team name when context requires disambiguation.
5. `View in official GEDS` external link.

The section provides:

- Search by display name or observed title.
- Filter by observed classification when at least two classifications exist in
  the current result set.
- Sort by name or title.
- Result count and a clear empty state.
- Pagination or virtualization for large teams without creating competing page
  scroll regions.

Names are public directory observations, not application candidates. The UI
states that records come from the named snapshot and may be stale, duplicated,
or misplaced. The official GEDS link is the route to current contact details.

### Observed Classification

The current canonical `people_current` model stores `display_name`, `title`,
organization lineage, and `source_url`; it does not contain a separate,
authoritative classification field. Classification is therefore optional and
provenance-sensitive.

Rules:

- Prefer a future structured classification field from the official source when
  one becomes available.
- Until then, extract a classification only when an allow-listed occupational
  group and numeric level explicitly occur in the observed title text. The
  initial reviewed allow-list is `EC`, `CO`, `IT`, and legacy `CS`; adding a
  group requires a reviewed configuration entry backed by an official
  classification reference or a future structured source field.
- Accept common separators for display normalization, such as `IT-02`, `IT02`,
  and `IT 02`, while retaining the untouched observed title separately.
- Normalize a single unambiguous match to `GROUP-LEVEL`: levels 1 through 9 use
  two digits (`IT2` becomes `IT-02`), while already multi-digit levels are
  retained.
- When multiple explicit classifications occur, show each observed value in
  source order; do not choose one as current without stronger source evidence.
- Do not derive classification from job-title meaning. For example, `Economist`
  alone must not become `EC`, and `Developer` alone must not become `IT`.
- Do not map legacy groups to new groups automatically. A title containing
  `CS2/IT2` may display both normalized observations; it must not claim a
  conversion.
- Hide the badge when parsing is absent or ambiguous. Never display `Unknown`
  as though it were a classification.
- Expose accessible text such as `Classification observed in title: IT-02` and
  a tooltip explaining that the value is not independently verified.

Current-data verification found examples such as `IT-01`, `Junior Analyst
EC-02`, `Fisheries Management Officer (CO-01)`, `IT02`, and `CS2/IT2`. This
supports conservative extraction but not broad classification inference.

### Privacy and External Links

- Career Atlas returns only display name, observed title, optional observed
  classification, organization context, snapshot metadata, and official source
  URL for public person rows.
- Email, telephone, fax, street address, and other contact fields are neither
  stored in the public person response nor rendered in the UI.
- Official GEDS links open in a new tab with an external-link indicator and safe
  `noopener`/`noreferrer` behaviour.
- Missing or malformed official URLs render as unavailable; the application
  does not generate a guessed person URL.

## Public Data Contract

The public person representation is separate from Admin diagnostic rows:

```text
PublicPerson {
  person_id
  display_name
  observed_title
  observed_classifications[]
  org_id
  organization_name
  snapshot_id
  snapshot_as_of
  source_url
}
```

`person_id` is a stable opaque public identifier and must not expose internal
database paths or credentials. `source_url` is an allow-listed official GEDS
HTTPS URL. Classification parsing occurs in the read model or publication
pipeline so every public client receives the same result.

The team endpoint supports direct-person retrieval by organization ID with
server-side search, classification filter, sort, and pagination. It does not
accept raw SQL, database names, or staging-source parameters.

## Loading, Empty, and Error States

- A team change clears or visibly transitions the previous people result; names
  from Team A must never appear under Team B's heading during a request race.
- Loading uses a team-specific status message and stable skeleton rows.
- A valid team with no direct people displays `No people were observed directly
  in this team in the current snapshot.`
- Partial coverage displays a warning adjacent to the people count without
  disabling official GEDS links.
- Public API failure retains the selected team context and offers retry; it does
  not reveal stack traces, database paths, or crawler state.
- Invalid or non-GEDS source URLs are not clickable and are reported internally
  for data-quality review.

## Stitch Project Separation

Use two Stitch projects to prevent design and information-architecture leakage:

1. `GEDS Career Atlas - Public Experience`
2. `GEDS Crawl Control Plane - Private Admin`

Both projects receive the same semantic light/dark theme brief. The public
project contains only the Career Atlas navigation and read-only journeys. The
private project contains only authenticated operator journeys and a visible
private-admin marker.

The public Stitch project must include:

- Light and dark Discover/Constellation states.
- Light and dark Organization Walk with a selected leaf team.
- `People in this team` desktop and mobile states.
- Classification present, multiple classifications, absent classification,
  no-people, partial-coverage, loading, and public-error examples.

The Admin Stitch project must include:

- Light and dark operational overview.
- Active crawl, run history, coverage, schedule, and snapshot-management states.
- Authentication boundary and mutation confirmation patterns.

Do not reuse the rejected `Civic Explorer` name, invented departments, avatars,
budget/FTE cards, `New Unit`, `Admin Access` inside public screens, or fabricated
analytics.

## Accessibility

- Every interactive target is at least 44 by 44 CSS pixels or has an equivalent
  hit area.
- Name, title, and classification remain understandable without color.
- Table headers are programmatically associated with cells; mobile rows use
  explicit labels.
- Filters, sort controls, theme control, hierarchy columns, and external links
  are fully keyboard operable with visible focus.
- Loading and result-count changes use restrained live-region announcements.
- At 200% zoom, people rows reflow without horizontal page scrolling.
- Reduced-motion preferences disable nonessential constellation and theme
  transitions.

## Verification Strategy

### Contract Tests

- Public routes expose GET operations only and cannot reach `/api/control/*`.
- Public person responses omit contact and Admin-only fields.
- Official source URLs accept only the expected HTTPS GEDS host.
- Direct-team queries never silently include descendants.

### Classification Tests

- Normalize explicit forms such as `IT-02`, `IT02`, `IT 02`, `EC-04`, and
  `CO-01`.
- Preserve the observed title separately.
- Return multiple observed classifications for `CS2/IT2` without mapping them.
- Reject semantic-only guesses such as `Economist` and `Software Developer`.
- Reject ambiguous text and unsupported group codes.

### Interaction Tests

- Selecting a leaf team loads the correct direct people.
- Rapid Team A to Team B selection cannot render Team A people under Team B.
- Search, classification filter, sort, and pagination preserve team scope.
- Missing source URLs are non-interactive.
- Light, dark, and system choices persist independently in both applications.

### Visual and Accessibility Tests

- Compare implemented light and dark screens with the selected Stitch frames at
  matching viewports.
- Check contrast, keyboard order, visible focus, table semantics, mobile
  reflow, 200% zoom, and reduced motion.
- Verify that the public and Admin navigation sets never appear together.

## Delivery Sequence

1. Correct the two Stitch briefs and separate the projects.
2. Define semantic theme tokens and approved light/dark reference frames.
3. Add the public team-people read model and conservative classification parser.
4. Build the leaf-team people experience and official GEDS links.
5. Apply dual themes to Career Atlas.
6. Apply dual themes and production access boundary to the Admin Console.
7. Complete contract, interaction, accessibility, and visual regression checks.

## Acceptance Criteria

- Career Atlas and the Admin Console are independently deployable and have
  disjoint navigation and authorization boundaries.
- Both applications support tested light, dark, and system theme choices.
- Career Atlas defaults to the approved red-and-white light direction.
- The dark direction uses a coordinated red-family accent and does not default
  to the rejected cyan-heavy visual language.
- A leaf team exposes its direct observed people with name and title.
- Explicit classifications such as EC, CO, IT, or other allow-listed groups are
  displayed only when supported by source text or a structured source field.
- Each valid person row links to its official GEDS record for current contact
  information.
- Public responses and screens contain no copied email, telephone, address,
  crawler health, history, configuration, or mutation controls.
- Public organization, profile, people, URL, and snapshot state remain
  synchronized during normal use and rapid selection changes.
- The implementation passes boundary, parsing, interaction, responsive,
  contrast, keyboard, and visual-regression verification.
