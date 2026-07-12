# GEDS Career Atlas acceptance ledger

Audit date: 2026-07-11

Canonical snapshot: `edd5d0f4269da97163b33a5cf7dd8c850ad51331a913721e0ce7a07e1977fce5`

Scale: 156 root institutions, 26,421 organization units, 193,163 current people records.
Status vocabulary: **Proven** means current source plus a scope-matched automated or rendered/runtime check establishes the requirement; **Pending** means stronger evidence is still required.

| Acceptance criterion | Implementing evidence | Automated evidence | Real-data / rendered evidence | Status |
| --- | --- | --- | --- | --- |
| Broad interest discovers relevant institutions and teams without exact titles | `career_taxonomy.py`, `career_index.py`, `DiscoverPage.tsx`, `ConstellationPage.tsx` | taxonomy/matcher/repository tests; `discover.spec.ts` | Real `AI`, software, cybersecurity, policy, and data queries exercised against the canonical DB | Proven |
| Controlled bilingual synonyms and noisy titles; every result explains its match | versioned taxonomy, `InterpretationChips.tsx`, `MatchCard.tsx`, evidence payloads | taxonomy collision/exclusion/alias tests; Discover interpretation/evidence tests | `/api/search?q=AI` returns category, expansions, confidence, and field-level evidence from real source strings | Proven |
| Explore all 156 institutions through canonical cycle-free paths | canonical resolver/projector; bounded org APIs; Organization Explorer | canonical coverage/cycle/missing-parent tests; repository/API org tests | root slice contains the 156 canonical institutions; shared deep focus rebuilds its ancestor path | Proven |
| Org Walk remains responsive for hundreds of siblings | `OrgColumn.tsx` using TanStack Virtual | 348-sibling virtualization and keyboard tests | mobile/desktop E2E completes hierarchy drill-down without page overflow | Proven |
| Team Profile shows observed roles, counts, provenance, quality, and official source without inventing mandate/job | `TeamProfile.tsx`, `RoleExplorer.tsx`, profile/roles APIs | profile trust-language, source, related-team, report-copy, and role filter tests | real profile journey verifies official sources, non-claiming copy, leads, and observed roles | Proven |
| Required Constellation is performant, synchronized, shareable, reduced-motion aware, and has a semantic alternative | deterministic `layout.ts`, SVG spatial layer, synchronized list, URL focus/history, failure boundary | layout determinism, focus/filter/fallback tests; constellation/accessibility/performance E2E | real medians: root 0.62ms-class, 2,000 nodes 8–13ms; list-first mobile and semantic map verified | Proven |
| Vacancy signals are distinct from verified opportunities and never create Apply | `vacancy_signals`, vacancy API/cards and dotted semantics | parser/index/API/privacy tests; vacancy E2E | real vacancy journey states unverified/no live competition; no Apply control | Proven |
| Contact suggestions are evidence-labelled and never claim hiring authority | deterministic lead rules/inference, `CareerConversationLeads.tsx` | lead exclusions/ranking/privacy tests; career research E2E | real profiles expose title/org/source reasons without names/contact fields or hiring-manager claims | Proven |
| Public routes cannot start crawlers or expose control-plane actions | separate `create_career_app`, GET-only routes, bounded schemas | public API method/control-route/security tests | E2E confirms no complete people endpoint and bounded 2,000-node response | Proven |
| Empty, stale/partial, and visualization/source failure states preserve a useful journey | no-match, quality notes, About limitations, `ConstellationBoundary`, Organization Walk fallback | unit fallback/no-match tests; resilience E2E | no-match, partial overlay, constellation failure, and unavailable profile journeys rendered | Proven |
| Representative search, API, hierarchy, UI, accessibility, and performance gates pass on canonical data | backend/full frontend/Playwright release gates | 204 Python tests; 23 Vitest files/42 tests; typecheck/build; 18 Playwright tests | Chrome + axe, real DB, 360/768/1280/1600 responsive inspections; exact current rerun recorded in progress | Proven |

## Deliberate boundaries

- GC Jobs integration and verified opportunity status remain deferred; no placeholder is promoted into a live competition.
- No email, phone, fax, address, personal display-name, demographic, protected-trait, candidate-ranking, outreach, crawler-control, or application capability is part of the public product.
- Automated axe/keyboard/reduced-motion/accessibility-tree coverage is proven. A listening session with NVDA, JAWS, or VoiceOver remains a recommended human release check, not falsely represented as automated evidence.

## Rendered-screen audit

Current Chrome inspection used the live canonical server on `0.0.0.0:8780` plus the real snapshot above.

| Surface/state | Current evidence and finding |
| --- | --- |
| Desktop Discover | AI query rendered 20 responsive evidence cards, taxonomy interpretation/related terms, five functional filters, partial-quality badge, and no horizontal overflow at 1920px. The first inspection exposed a filter-rail overflow and ungrouped results; grid constraints and `discover.css` were added, rebuilt, and re-inspected. |
| Constellation | 156-institution circle pack rendered with stable scale, selected cyan focus, evidence inspector, branch exploration, quality outline, and synchronized semantic list. Interest mode shares Discover filters. |
| Org Walk | desktop multi-column and 360px single-column/breadcrumb journeys are covered by rendered E2E; deep shared focus reconstructs Department / Branch / Team state. |
| Team Profile and Roles | real `Analytics Services & Data Science` profile exposed canonical chain, counts, source, freshness, issue-copy action, role-family grouping, institution/team/confidence/vacancy filters, related teams, and non-claiming leads. |
| Tours / Saved Map | five bilingual tours showed validated stop availability; current map can be saved locally; About immediately follows with snapshot/quality context. |
| About | canonical date, snapshot ID, 193,163 people records, 26,421 units, 156 institutions, lineage, matching, privacy, vacancy semantics, and limitations rendered. |
| French Discover | `lang=fr` set the document language and rendered `Découvrir`, `Explorer le gouvernement`, and the French no-match journey while preserving URL state. |
| Mobile Discover / Org Walk | 360x800 inspection rendered persistent horizontal nav, stacked command/filter controls, single-column cards, and no page-level overflow (`scrollWidth 345 <= viewport 360`). Mobile Constellation remains list-first. |
| Reduced motion | Playwright emulation proves navigation remains usable and animation duration becomes zero. |
| No-match / partial / source unavailable / visual failure | French no-match, real `partial_overlay`, unknown-profile 404, constellation API failure, and visual-boundary semantic-list fallback are covered by unit plus resilience E2E. No state removes the alternate Organization Walk journey. |
