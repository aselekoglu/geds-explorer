# Career Atlas Search-First Layout and Grouped Team Profiles

**Date:** 2026-07-13  
**Status:** Approved for implementation planning  
**Surface:** Public, read-only GEDS Career Atlas only

## Goal

Replace the current vertically stacked public experience with a focused workspace where users can search GEDS records, browse a selected institution, open Organization Walk as a first-class view, and inspect a compact team profile without repeated or empty role noise.

The redesign must preserve the public/private boundary. Crawl controls, health, history, scheduling, and other operator functions remain exclusive to the private Admin Console.

## Confirmed Problems

1. Selecting an institution changes the filter and URL but does not change the bubble data when no text query is active.
2. A stale organization focus can remain selected after the institution changes, so the bubble highlight and Team Profile can describe the previous institution.
3. The filter row becomes visually nested at desktop widths. Minimum confidence and recorded-vacancy filters add complexity without enough useful data.
4. Constellation, Organization Walk, guided tours, and About are stacked into one long document, forcing excessive scrolling and making the product feel unfinished.
5. The empty Team Profile permanently consumes a large part of the viewport.
6. Observed roles repeat the same title many times and include blank titles without useful grouping.
7. Leaf-team people are shown as a flat table, separating people from the titles that explain their relationship to the team.

## Information Architecture

The public application has three primary views in the existing left navigation:

- **Discover:** search, institution scope, results, constellation, and the selected Team Profile drawer.
- **Organization Walk:** a dedicated hierarchy browser using the currently selected institution as its starting scope.
- **About the data:** the existing methodology and limitations content.

Remove Constellation and Tours as separate navigation destinations. Constellation remains a visualization inside Discover. Remove guided exploration cards and saved-tour content from the rendered public journey. No crawl or admin navigation is introduced.

Navigation uses client-owned view state and stable URL state. The selected view is represented by the hash (`#discover`, `#explorer`, or `#about`) so links remain shareable and browser back/forward behavior remains meaningful.

## Discover Workspace

### Header and search

The command header contains:

- one global search field;
- result-type controls: `All`, `Topics`, `Teams`, and `People`;
- the existing Light/Dark/System theme control;
- the existing English/French language control.

Search is the primary action. The current domain dropdown is removed from the persistent filter rail. Topic discovery is performed through the same query and result-type control instead of a separate taxonomy-first filter.

The backend search remains deterministic and source-derived. `Teams` displays organization entities and `People` displays person entities from the existing search response. `Topics` displays only taxonomy categories and interpretation evidence already returned for the query; it is not a synthetic third entity type. `All` combines the available topic summary, team results, and person results. The frontend does not invent semantic matches.

### Institution scope

The institution selector is the only persistent Discover scope control. The data-quality indicator remains visible as contextual metadata but is not an interactive filter.

When a user selects an institution:

1. resolve the selected department name to its `department_id` from `/api/departments`;
2. clear any selected organization focus that is outside the new institution;
3. request `/api/constellation/slice` with the institution ID as `root_id`;
4. render that institution and its immediate hierarchy slice;
5. give Organization Walk the same institution root;
6. update the URL without retaining confidence or vacancy parameters.

Selecting `All institutions` restores the government-wide root slice.

Minimum-confidence and recorded-vacancy controls are removed from the public application, including nested role exploration. Legacy `confidence` and `vacancy` URL parameters are ignored and removed the next time public search state is written.

### Main canvas

Discover uses the full available main width while no Team Profile is open. The constellation is sized to the available viewport rather than forcing a fixed long page. Search results appear as a compact, scrollable results region associated with the query instead of pushing every other section downward.

The constellation retains keyboard-accessible list fallback behavior. Selecting a bubble opens the corresponding Team Profile. Selecting `Explore branch` changes the current constellation root without changing the institution selector.

## Organization Walk

Organization Walk is rendered only when its navigation item is active. It is not mounted as a section below Discover.

The initial column is:

- the selected institution and its children when an institution scope exists;
- the existing government-wide top-level list when no institution is selected.

Selecting a row updates the shared organization focus and opens the Team Profile drawer. Drilling through columns does not reset the institution scope. Browser back/forward restores the view and selected organization.

## Team Profile Drawer

The empty placeholder panel is removed. No third column is reserved until an organization is selected.

On desktop, selecting an organization opens a right-side drawer over the workspace. On smaller screens it becomes a full-screen sheet. It has a clear close control, preserves keyboard focus, and returns focus to the invoking bubble or row when closed.

The drawer keeps organization path, counts, snapshot warning, official organization link, related teams, correction report, and privacy-safe conversation leads where data exists.

## Grouped Roles and Leaf-Team People

### Title normalization

Observed titles are grouped using a display-safe normalization rule:

- trim surrounding whitespace;
- collapse repeated internal whitespace;
- use `No title recorded` when the normalized value is empty;
- compare titles case-insensitively for grouping while preserving the first non-empty observed spelling for display.

No linguistic or semantic title inference is performed.

### Role summary

Replace the repeated flat role list with title groups sorted by:

1. non-empty groups alphabetically;
2. `No title recorded` last.

Each heading displays the record count, for example `Senior HR Assistant · 4`. The no-title group displays its count and is collapsed by default. Non-leaf teams show counts only because descendant people must not be presented as direct team members.

### People in leaf teams

For `child_count === 0`, load direct-team people from the existing privacy-safe people endpoint and place each person under their normalized title group. Each person row displays:

- display name;
- conservatively observed `EC`, `CO`, `IT`, or legacy `CS` classification badge when present;
- `Open in GEDS` link when the stored source URL is an official GEDS HTTPS URL.

Names are never shown as descendant members of a non-leaf organization. Email, phone, fax, address, and other contact fields remain excluded.

The leaf profile keeps lightweight person-name search and classification filtering. Sorting controls are removed because title grouping defines the presentation order.

## Removed Public Features

- minimum-confidence controls and filtering;
- recorded-vacancy-only controls and filtering;
- persistent domain dropdown;
- guided AI, software-delivery, cybersecurity, policy, and data-career tour cards;
- saved-tour section in the main journey;
- repeated flat observed-role list;
- nested Role Explorer filters;
- permanently open empty Team Profile column.

Existing backend fields and endpoints may remain for compatibility unless removal is required to simplify frontend contracts. Admin Console functionality is unchanged.

## Loading, Empty, and Error States

- Institution change immediately clears stale focus and shows a loading state in the constellation canvas.
- An institution with no child nodes shows a compact empty state with a link to Organization Walk or official GEDS.
- A search with no matches states that no source-derived records matched and suggests changing the query or institution scope.
- A leaf team with no people records shows a single empty message.
- Failed profile, people, or constellation requests retain retry behavior and never leave data from the previous institution visible.

## Accessibility and Responsive Behavior

- Primary navigation exposes the active view with `aria-current="page"`.
- Search result-type controls are a labelled single-selection group.
- Drawer focus is trapped while open; Escape closes it; focus returns to the trigger.
- Title groups use real headings and disclosure controls where collapsed.
- Counts are included in accessible names, not communicated by color alone.
- At narrow widths the side navigation becomes a compact top/bottom navigation, the canvas uses the viewport width, and the drawer becomes a full-screen sheet.
- Existing reduced-motion behavior remains effective.

## Testing Strategy

### State and regression tests

- Selecting an institution resolves its ID, requests the corresponding constellation root, clears stale focus, and updates Organization Walk.
- `All institutions` restores the government-wide slice.
- Legacy confidence/vacancy URL state does not render controls or affect results.
- Switching navigation views mounts only the selected primary view.
- The closed Team Profile does not reserve layout width.

### Search tests

- A single query displays team and person results.
- `Topics` displays only categories/evidence returned by deterministic query interpretation.
- Type controls filter the rendered result kinds without inventing new records.
- Institution scope is included in displayed search results.
- Empty and failed searches have explicit states.

### Grouping tests

- repeated titles render once with the correct count;
- whitespace and case variants group together;
- blank titles appear once as `No title recorded` and sort last;
- leaf-team people appear under their title with classification and official links;
- non-leaf profiles never display descendant names.

### Completion checks

- full Vitest suite;
- TypeScript typecheck;
- production Vite build;
- backend pytest suite if frontend contracts or API behavior change;
- desktop and narrow viewport browser verification for institution switching, navigation, drawer behavior, grouped profiles, both themes, and back/forward state.

## Acceptance Criteria

1. Institution selection visibly changes the bubbles to the selected institution and never leaves an unrelated focus/profile selected.
2. Discover, Organization Walk, and About are distinct views rather than vertically stacked sections.
3. The main workspace uses the full width until a team is selected.
4. Minimum confidence, recorded vacancy, domain filter, guided tours, and nested role filters are absent from the public UI.
5. Users can search across keywords/topics, teams, and people from one query surface and narrow by result type.
6. Repeated and empty titles are grouped and counted instead of repeated line by line.
7. Leaf-team profiles show names underneath titles with observed classifications and official GEDS links.
8. Non-leaf profiles do not expose descendant names as if they were direct members.
9. About the Data remains available and unchanged in meaning.
10. Public Career Atlas remains read-only and contains no Admin Console controls or crawl state.
