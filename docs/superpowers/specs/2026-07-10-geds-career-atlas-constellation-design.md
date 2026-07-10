# GEDS Career Atlas and Government Constellation Design

Date: 2026-07-10

## Status

Product direction approved. This document is the reviewable design contract for
the public-facing explorer. Product implementation starts only after this
written specification is approved and converted into an implementation plan.

## Vision

Turn the Government of Canada directory from a database that must be searched
into a place that can be explored.

The product is for people who want a public-service career but do not yet know
the government's internal vocabulary, which institutions contain relevant
work, how teams relate to one another, or who may be appropriate for a career
conversation. It should make the federal government feel legible without
pretending that directory data is a jobs board or that an inferred contact is a
hiring manager.

The core product is **Career Atlas**. Its memorable discovery and sharing
surface is **Government Constellation**. A structured top-down **Org Walk** and
evidence-rich **Team Profile** make discoveries useful. A verified jobs layer
may be added later through a separate GC Jobs integration.

## Primary user and problem

The primary user is an early-career candidate in Ottawa or elsewhere in Canada
who:

- is interested in a field such as AI, data, cybersecurity, policy, finance, or
  software but does not know the corresponding government terminology;
- cannot name all institutions or branches that employ people in that field;
- finds current government directories and job sites fragmented and difficult
  to navigate;
- wants to understand a team's mandate and reporting chain before applying or
  requesting a career conversation;
- needs trustworthy guidance about what the data proves and what is only an
  inference.

The product must help that user move from a broad interest to a defensible map
of relevant institutions, teams, observed roles, and official sources.

## Product principles

1. **Explore before querying.** Users should be able to discover unfamiliar
   branches and job families without knowing an exact title.
2. **Overview, zoom, filter, details.** Every large-scale visual starts with a
   manageable overview and progressively reveals detail.
3. **Explain every match.** Relevance, contact suggestions, and vacancy signals
   expose the evidence and confidence behind them.
4. **Directory evidence is not recruitment evidence.** An observed title is
   not an open job, a recorded vacant directory slot is not a live competition,
   and an inferred lead is not necessarily the hiring manager.
5. **The visual spectacle must remain useful.** Constellation is a real
   navigation and explanation surface, not a decorative graph.
6. **One canonical data truth.** Public exploration never silently combines
   partial or contradictory run selections.
7. **Private-by-default enrichment.** Do not store phone numbers or email
   addresses, enable bulk contact export, or automate outreach.

## Product shape

### Career Atlas

Career Atlas is the default public-facing workspace. A user enters an interest,
role family, skill, or phrase. The system translates it into a transparent set
of bilingual concepts and highlights relevant institutions and branches.

The result answers:

- Where in government does this work appear?
- Which teams are the strongest and most explainable matches?
- Which related teams or role names would I not have known to search for?
- What roles have actually been observed in each team?
- Where does the team sit in the government hierarchy?
- Which official GEDS source can I inspect next?

### Government Constellation

Constellation is a required showcase experience in the first major product
release. It presents the federal organization as a navigable spatial map:

- institutions are major systems;
- branches and directorates form nested clusters;
- node size represents a selected measure such as people count or descendant
  count;
- color represents institution or user-selected career domain;
- intensity represents match strength;
- halos or badges communicate data quality, partial coverage, or a vacancy
  signal without implying a verified opening.

Typing `AI`, `policy`, `cybersecurity`, or `software` lights up the relevant
parts of the government. Selecting a cluster focuses it, updates the breadcrumb
and detail panel, and preserves a shareable URL. Semantic zoom replaces dense
labels with aggregate shapes at wide zoom and reveals organization names,
counts, role families, and people only when the scale can support them.

Constellation is never the only navigation method. The same state is available
through an accessible list, Org Walk, search results, keyboard controls, and a
screen-reader-friendly tree representation.

### Org Walk

Org Walk is the precise top-down browser. It uses a multi-column hierarchy view
on desktop because the data contains deep paths, thousands of leaf nodes, and
parents with hundreds of children.

- Column 1 lists institutions.
- Each selection opens its children in the next column.
- A pinned breadcrumb shows the full canonical path.
- Counts and small relevance indicators summarize descendants without opening
  them.
- Search can reveal a matched path and its ancestors without expanding the
  entire tree.
- Large sibling lists are virtualized, searchable, and sortable.
- Mobile uses a drill-in stack with a persistent back path rather than squeezed
  columns.

### Team Profile

A team profile is the evidence page for an organization node. It shows:

- canonical organizational chain;
- institution and organization names;
- observed people count and direct/descendant organization counts;
- observed role families and representative titles;
- why the team matched the active interest;
- related teams based on taxonomy and organizational proximity;
- directory freshness and quality warnings;
- official GEDS organization and person source links;
- career-conversation leads only when a defensible rule produces them.

The profile does not invent a mandate from a title alone. Any generated summary
must be visibly labelled as an inference and list the organization/title
evidence used.

## Information architecture

The existing crawl control plane remains an operator product. Career Atlas is a
separate public-facing product surface with the following navigation:

- **Discover** — Career Atlas search, recommended domains, and featured tours.
- **Constellation** — spatial government map synchronized with filters.
- **Organizations** — Org Walk and organization search.
- **Roles** — role-family and title exploration.
- **Saved Map** — local bookmarks, comparisons, and shareable view links.
- **About the Data** — provenance, freshness, limitations, and methodology.

Operator routes continue to own crawler controls, coverage, run history, and
raw snapshot inspection. Public routes never expose crawler mutation controls.

## Canonical data prerequisite

Career Atlas must not launch on the current combined UI selection. The product
reads one validated canonical snapshot and reports its as-of time.

Before product indexing:

1. Normalize pagination lifecycle vocabulary so a successful `finished`
   organization is accepted as successful by the canonical resolver, or change
   producer and consumer together to one tested vocabulary.
2. Resolve the four currently failed pagination organizations explicitly.
   Until recrawled successfully, retain their validated base rows and attach a
   partial-overlay warning; never treat missing overlay rows as departures.
3. Build parentage from the decoded LDAP DN suffix. Do not trust the stored
   `parent_dn` or stored `org_path` for product navigation. Validation of the
   current crawl found 6,609 incorrect stored internal parent relationships,
   8,936 nodes participating in stored-graph cycles, and 6,785 incorrect stored
   paths. DN-derived parentage produces 156 roots, no missing parents, no
   cycles, and a maximum depth of 12.
4. Deduplicate people by stable source identity according to the canonical
   snapshot rules. Preserve source lineage and quality state.
5. Publish the snapshot only after aggregate, hierarchy, coverage, and
   referential-integrity checks pass.

The currently reconstructed safe view is approximately 193,163 people across
156 institutions and 26,421 organization nodes. These are analysis findings,
not hard-coded UI values; the product always reads counts from the active
canonical manifest.

## Career taxonomy and noisy-data matching

Exact matching is insufficient. The current data contains bilingual names,
abbreviations, repeated organization labels, inconsistent capitalization,
spelling variants, extremely broad titles, and more than 41,000 normalized
unique title strings. Matching therefore uses a reproducible, multi-stage
analysis pipeline.

### Normalization

Index both the original text and normalized forms for titles, organization
names, and canonical ancestor paths:

- Unicode normalization and diacritic-aware search;
- case and punctuation normalization;
- tokenization that preserves meaningful phrases such as `machine learning`,
  `artificial intelligence`, and `science des données`;
- English/French equivalents and common GoC abbreviations;
- conservative spelling aliases recorded in a versioned dictionary;
- stop words that are field-specific rather than globally discarded.

Original text is always displayed. Normalization changes retrieval, not source
records.

### Multi-label taxonomy

Create a versioned bilingual taxonomy of career domains and role families. An
item may belong to multiple categories. Initial domains include:

- software and digital delivery;
- data, analytics, AI, and research;
- cybersecurity, IT operations, and infrastructure;
- policy, programs, and regulation;
- communications and public affairs;
- finance, audit, procurement, and administration;
- legal, enforcement, and investigations;
- science, engineering, environment, and health;
- human resources and organizational services;
- executive, management, and coordination roles.

Each category stores preferred labels, synonyms, exclusions, bilingual terms,
abbreviations, and example positive/negative titles. Categories are product
metadata under version control, not opaque model output.

### Evidence and ranking

Each match collects weighted evidence:

1. direct role-title phrase;
2. direct organization-name phrase;
3. title tokens and controlled synonyms;
4. organization tokens and controlled synonyms;
5. ancestor-path evidence;
6. optional semantic similarity used only as a recall or reranking aid after
   the explainable lexical/rule layer.

Title evidence is strongest for a person or observed role. Direct organization
evidence is strongest for a team. Ancestor-only evidence receives a lower
weight so an entire department does not become an AI team merely because one
descendant contains that term. Exact phrases outrank loose token overlap.
Exclusion rules suppress known ambiguous terms.

Every result returns:

- matched categories;
- numeric score mapped to high, medium, or exploratory confidence;
- the fields and phrases that contributed;
- any exclusion or uncertainty warning;
- taxonomy version.

The UI phrases this as `Matched because...`, not as an unexplained relevance
number.

### MVP and later semantic layer

The first implementation uses deterministic full-text search, controlled
synonyms, weighted fields, and a versioned rules taxonomy. It does not require
an embedding service. After a labelled evaluation set exists, local embeddings
or a reranker may improve recall for unfamiliar phrasing. Semantic results must
still be grounded in displayed source text, may not override hard exclusions,
and must be independently disableable for comparison.

### Evaluation

Build a stratified review set spanning major institutions, common and rare
titles, English and French, ambiguous terms, and deep organization paths.
Measure precision at the top results, missed relevant teams, and confidence
calibration per career domain. Store reviewer decisions separately from source
data and use them to update taxonomy versions. Search changes must pass a fixed
regression set before release.

## Vacancy signals and the later Opportunity Engine

Current data analysis found 17 unique directory records whose displayed name,
title, or path contains `vacant`, including roles such as Architectural
Technologist, Senior Structural Engineer, Executive Assistant, Committee
Coordinator, and Director. Some values are inconsistent, numbered, bilingual,
or misspelled. This makes the signal useful but not trustworthy enough to be an
opening.

The product models two separate concepts:

### Recorded vacancy signal

- Derived from explicit placeholder language in the current GEDS record.
- Labelled `Recorded as vacant in GEDS`, with source and snapshot date.
- Carries a confidence based on which field contains the marker and whether the
  title and organization are populated.
- Never displays `Apply`, an application deadline, or an assumption that an
  external candidate can fill it.
- May be filtered or shown as a subtle team-profile signal, but does not drive
  primary ranking by default.

### Verified job opportunity

- Requires a current authoritative job advertisement and its closing date,
  classification, location, eligibility, and application URL.
- Will come from a separately designed GC Jobs connector or another authorized
  official source.
- Is explicitly deferred until after Career Atlas, Org Walk, Team Profile, and
  Constellation are working and evaluated.

The future Opportunity Engine may join verified advertisements to the
organizational map. It must never silently promote a GEDS placeholder into a
live job.

## Contact and career-conversation guidance

The product distinguishes three contact contexts:

1. **Official application contact** — shown only when a verified job
   advertisement provides one.
2. **Likely team lead** — an explainable, confidence-labelled inference based
   on a leadership title and position in the canonical hierarchy.
3. **Career conversation lead** — a person whose observed role is relevant and
   who may be appropriate for an informational conversation, without implying
   hiring authority.

Rules for inferred leads:

- Require a direct organization relationship or clearly relevant parent
  relationship.
- Use a versioned bilingual leadership-title dictionary with exclusions for
  assistants, advisors to leaders, and similarly ambiguous titles.
- Show title, organization, source date, official GEDS link, evidence, and
  confidence.
- Say `Possible team lead` or `Career conversation lead`, never `Hiring
  manager` unless an official source verifies that role for a live process.
- Provide short etiquette guidance and remind users that official applications
  and merit requirements still apply.
- Do not store or display scraped email/phone fields, enable mass outreach, or
  export contact lists.

## Core user journeys

### Journey 1: broad interest to government map

1. User enters `AI`.
2. Career Atlas expands the query into the active bilingual category and shows
   the interpretation as editable chips.
3. Constellation lights up matching institutions and clusters, while a ranked
   list provides an accessible equivalent.
4. User selects a cluster and sees `Matched because` evidence.
5. User opens its Team Profile, inspects observed roles and the canonical path,
   then saves or shares the view.

### Journey 2: precise top-down exploration

1. User opens Organizations.
2. User selects an institution and walks across branch columns.
3. Counts and relevance markers reveal promising branches without expanding
   every leaf.
4. User filters titles or role families within the selected subtree.
5. User opens an official GEDS source for verification.

### Journey 3: career conversation research

1. User opens a matched team.
2. Team Profile shows observed role families and possible leads.
3. User examines why a lead was suggested and follows the official source.
4. The product explains that this is networking context, not an application or
   a verified hiring relationship.

### Journey 4: recorded vacancy discovery

1. User enables the `Recorded vacancy signal` filter.
2. A result shows the exact GEDS placeholder and snapshot date.
3. The UI explains that no live competition is verified.
4. The user may inspect the team or official source; there is no application
   action until a later verified jobs integration supplies one.

## Interaction and visual system

The operator console's dark visual identity can inform the product, but the
Career Atlas should feel more open, spatial, and editorial.

- Dark navy space provides continuity with the control plane.
- Institution colors remain stable across Constellation, Org Walk, breadcrumbs,
  and profiles.
- Career-domain overlays use accessible patterns or outlines in addition to
  color.
- Motion explains focus, expansion, and reparenting; it is never continuous
  ambient noise.
- Reduced-motion mode replaces flight/zoom transitions with immediate state
  changes.
- Labels use plain language first and official source strings second where an
  explanation is necessary.
- Large metrics are used for orientation, not decoration.

Constellation may use a packed hierarchy, radial partition, or hybrid cluster
layout after prototype comparison. The selected renderer must support stable
node placement, incremental disclosure, hit testing, keyboard-equivalent
actions, and acceptable performance with 26,000-plus organizations. A single
force-directed hairball is not acceptable.

## Search, filtering, and URL state

Filters apply consistently across list, Constellation, Org Walk, and profiles:

- career domain and role family;
- institution;
- organization subtree;
- title phrase;
- language evidence;
- confidence threshold;
- recorded vacancy signal;
- data quality and freshness.

Every view state is serializable in a URL using stable identifiers rather than
display names. A shared URL restores query interpretation, filters, selected
node, visualization mode, and camera/focus state where practical. Public share
links contain no private notes or inferred contact exports.

## Architecture boundaries

### Canonical data layer

- resolves and validates the single current snapshot;
- exposes canonical organizations, people, titles, source lineage, freshness,
  and quality flags;
- derives parent and path from DN;
- never depends on client-side hierarchy repair.

### Career index and taxonomy engine

- builds normalized title, organization, and ancestor fields;
- versions taxonomy, aliases, rules, and evaluation results;
- returns matches, evidence, confidence, and aggregate facets;
- can add semantic recall later behind a tested interface.

### Explorer API

- supports ranked search, hierarchy children/ancestors, subtree facets, team
  profiles, constellation aggregates, and share-state resolution;
- paginates or streams bounded result sets;
- returns aggregate nodes for wide zoom and detailed nodes only on demand;
- does not return contact fields that the crawler intentionally excludes.

### Career Atlas web application

- owns Discover, Constellation, Organizations, Roles, Saved Map, and About;
- synchronizes one selection/filter state across visual and accessible views;
- virtualizes large lists and avoids rendering the complete graph in the DOM;
- remains deployable separately from the unauthenticated crawler control plane.

### Future GC Jobs connector

- is a separate ingestion, validation, expiry, and entity-linking boundary;
- never changes directory evidence into opportunity evidence;
- is excluded from the initial implementation plan unless a later approved
  design explicitly adds it.

## Performance strategy

- Precompute canonical child counts, descendant counts, direct/descendant people
  counts, taxonomy facets, and low-zoom constellation aggregates.
- Fetch children and profile detail on demand.
- Virtualize large sibling and result lists.
- Use WebGL or canvas for the dense spatial layer if prototype measurements
  show SVG cannot meet the target; keep accessible controls in semantic HTML.
- Keep node identifiers and layout seeds stable so repeat visits do not produce
  a completely rearranged map.
- Move expensive taxonomy/index construction to snapshot publication rather
  than browser runtime.
- Cache immutable snapshot-versioned responses and invalidate by canonical
  snapshot ID.

Targets for the representative 26,000-organization snapshot:

- initial useful overview within 2.5 seconds on a typical modern laptop after
  static assets are cached;
- filter/search feedback within 150 milliseconds for indexed local queries or
  an immediate pending state followed by results;
- focus/zoom interaction at a visually smooth frame rate;
- no API response that accidentally returns the entire person dataset.

## Accessibility, bilingualism, and responsive behavior

- All discovery and navigation functions are possible without the spatial
  canvas.
- Keyboard users can search, change filters, move through hierarchy results,
  focus a node, open a profile, and copy a share link.
- Screen readers receive hierarchy level, parent context, match evidence, and
  collapsed/expanded state.
- Status and relevance never rely on color alone.
- High contrast and reduced motion are supported.
- English and French source strings remain intact. Product taxonomy and core UI
  labels are bilingual from the data model onward rather than translated as an
  afterthought.
- Mobile prioritizes search, ranked results, drill-in hierarchy, and profile
  evidence. Constellation remains available as an overview but does not block a
  complete mobile journey.

## Loading, empty, partial, and stale states

- **Loading:** reserve layout and identify whether the snapshot, taxonomy, or
  detail panel is loading.
- **No matches:** show the interpreted concepts, removable constraints, related
  terms, and a path back to broad exploration.
- **Partial data:** display available results and name the affected institutions
  or overlay warnings. Never treat incomplete coverage as zero activity.
- **Stale data:** show the canonical snapshot date and a clear freshness notice.
- **Taxonomy uncertainty:** show exploratory results separately rather than
  mixing them into high-confidence matches.
- **Visualization failure:** fall back to the synchronized ranked list and Org
  Walk without losing filters or selection.
- **Source removed or unavailable:** retain the observed record with its
  snapshot provenance and label the external link state.

## Privacy, fairness, and trust

- The product uses public professional directory records but minimizes further
  aggregation of contact details.
- People are contextual evidence for organizational exploration, not targets
  for automated campaigning.
- Search ranking must be based on work evidence, not demographic inference.
- No protected or sensitive traits are inferred.
- Confidence labels and methodology are public and versioned.
- Users can report a stale or incorrect mapping without directly rewriting the
  canonical source record.
- Featured tours and domain defaults are editorially reviewable so they do not
  invisibly privilege only large or well-known institutions.

## Delivery phases

### Phase 0: trustworthy foundation

- Repair and test canonical promotion status handling.
- Resolve failed-overlay fallback and warnings.
- Derive and validate DN-based hierarchy.
- Publish the initial canonical snapshot and career-index inputs.

### Phase 1: Career Atlas spine

- Add bilingual taxonomy, normalization, explainable ranking, facets, and
  evaluation harness.
- Build Discover, ranked results, Org Walk, and Team Profile.
- Add stable URL state and data-methodology surfaces.

### Phase 2: required Constellation showcase

- Prototype candidate hierarchical layouts against real data.
- Implement semantic zoom, aggregate/detail loading, synchronized selection,
  reduced motion, and accessible alternate views.
- Add shareable views and a small set of curated career-domain tours.

### Phase 3: career guidance

- Add explainable likely-team-lead and career-conversation suggestions.
- Add saved comparisons and local research notes without bulk contact export.
- Add recorded-vacancy signals with explicit non-job wording.

### Phase 4: hardening and public presentation

- Validate performance, accessibility, bilingual UX, data provenance, privacy,
  and failure states.
- Separate and secure the public explorer from the local control plane.
- Produce a polished demo path suitable for Ottawa technology and public-service
  audiences.

GC Jobs integration and verified Opportunity Engine work require a later design
and are not part of these phases.

## Acceptance criteria

The implementation plan is complete only when all of the following are
verified:

- A user can enter a broad interest and discover relevant institutions and
  teams without knowing an exact government title.
- Search handles controlled bilingual synonyms and noisy titles, and every
  result explains its match.
- A user can explore all 156 institutions top-down through canonical,
  cycle-free hierarchy paths.
- Org Walk remains responsive for a parent with hundreds of children.
- Team Profile shows observed roles, counts, provenance, quality, and official
  source links without inventing a mandate or job opening.
- Constellation is implemented as a required, performant discovery surface with
  semantic zoom, synchronized filters, stable shareable state, reduced motion,
  and an accessible non-canvas equivalent.
- Recorded vacancy signals are distinguishable from verified opportunities and
  never produce an application action.
- Contact suggestions are evidence-labelled and never claim unverified hiring
  authority.
- Public routes cannot start crawlers or expose private control-plane actions.
- Empty, stale, partial, and visualization-failure states preserve a useful
  journey.
- Representative search-quality, API, hierarchy, UI, accessibility, and
  performance tests pass against the canonical dataset.

## Verification strategy

- Unit tests for DN parent derivation, lifecycle status normalization,
  taxonomy normalization, bilingual aliases, exclusions, scoring, confidence,
  and vacancy-marker parsing.
- Canonical-data tests for coverage, cycles, missing parents, deduplication,
  failed-overlay fallback, and atomic publication.
- Search regression tests from the reviewed labelled set.
- API tests for bounded pagination, stable identifiers, evidence payloads,
  subtree facets, aggregates, and privacy field exclusions.
- Browser tests for the four core journeys, URL restoration, keyboard use,
  reduced motion, mobile drill-in, and canvas fallback.
- Visual and performance checks using the full 26,000-plus organization graph
  rather than a toy fixture alone.
- Manual trust review of all wording around inferred leads, partial data, and
  vacancy signals.

## Explicit non-goals

- Replacing GC Jobs or allowing applications inside the product.
- Treating a directory placeholder as an active vacancy.
- Identifying a hiring manager without authoritative evidence.
- Scraping or exporting email addresses and phone numbers.
- Automated outreach, mass messaging, or candidate ranking.
- Displaying the entire hierarchy as one force-directed network.
- Mixing public exploration with unauthenticated crawler controls.
- Reconstructing false history from partial past snapshots.

## Durable continuation protocol

This design is attached to a durable Codex goal whose completion condition is
the verified implementation of the eventual approved plan, not merely the
creation of that plan. Because the work will span multiple quota windows, each
continuation must recover state from the repository rather than relying on chat
memory alone.

At the start of each continuation:

1. Read this specification, the approved implementation plan, and the current
   repo-local handoff/progress record.
2. Inspect `git status` and preserve user-owned or unrelated changes.
3. Re-check current tests and data prerequisites relevant to the next
   incomplete phase.
4. Implement the smallest coherent plan slice, verify it, and update durable
   progress evidence before the session ends.
5. Never push, deploy, open a pull request, or contact external parties unless
   the user explicitly authorizes that action.

The goal may be marked complete only when every required plan item and the
acceptance criteria above have current verification evidence. If a quota window
ends, the active goal remains the continuation mechanism; exact wake timing is
owned by the Codex product and is not implemented through a repository-local
timer.
