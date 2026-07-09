# GEDS vs TBS 2026 source notes

## Reporting job

- Audience: product stakeholders
- Decision: determine whether the completed GEDS crawl can be used as an employee-count source, and quantify its department-level coverage against the official benchmark
- GEDS snapshot: `2026-07-09T02:40:05.972696+00:00`
- TBS population date: March 31, 2026
- Report mode: MCP app report

## Source definitions

- **TBS controlling benchmark:** Pay System active employees as of March 31, 2026. It includes all employment tenures, Governor-in-Council appointees, deputy ministers, and federal judges, subject to the exclusions documented on the source page.
- **GEDS measure:** unique person source URLs captured from GEDS organization pages on July 8, 2026. This is a directory population, not an active-employee measure, and the crawl shows a hard 25-person ceiling per organization page.
- Official source: `https://www.canada.ca/en/treasury-board-secretariat/services/innovation/human-resources-statistics/population-federal-public-service-department.html`

## Crosswalk

- 88 non-zero TBS organizations were matched by exact normalized name or reviewed alias.
- The matched organizations represent 342,298 of the published 345,282 employees, or 99.14% of the TBS total.
- Five non-zero TBS rows representing 2,984 employees were excluded rather than force-matched:
  - Federal Judges not part of any department
  - Western Economic Diversification Canada
  - Indian Oil and Gas Canada
  - Office of the Superintendent of Financial Institutions Canada
  - Statistical Survey Operations
- The combined TBS information/privacy commissioners row is compared with the sum of the two corresponding GEDS departments.
- National Defence, RCMP, and Global Affairs carry visible definition warnings because the TBS exclusions may differ materially from GEDS directory membership.

## Chart map

1. **Directory ratio by TBS organization size**
   - Question: does GEDS coverage deteriorate for larger employers?
   - Family/type: ordered categorical bar
   - Fields: TBS size band, weighted GEDS/TBS directory ratio
   - Claim: coverage falls from roughly 79-81% for sub-500 organizations to 24.2% for 10,000+ organizations
2. **Largest absolute directory gaps**
   - Question: which organizations account for most missing directory records?
   - Family/type: grouped horizontal bar
   - Fields: organization, source, people
   - Claim: large employers dominate the aggregate gap
3. **Organization coverage distribution**
   - Question: how consistently does GEDS track TBS across organizations?
   - Family/type: ordered categorical bar
   - Fields: directory-ratio band, organization count
   - Claim: only 31 of 88 organizations land between 75% and 99%, while 20 exceed 100%

## Validation

- Parsed 98 TBS rows reconcile exactly to the published total of 345,282.
- Matched rows plus excluded non-zero rows and zero-population rows reconcile to all 98 TBS rows.
- Size-band totals reconcile to 342,298 TBS employees and 145,408 GEDS directory records.
- Ratio-band counts reconcile to all 88 matched organizations.
- Excluding National Defence, RCMP, and Global Affairs definition warnings raises the weighted directory ratio only from 42.48% to 47.68%; definition differences do not explain the main shortfall.
- Spearman correlation between organization size and directory ratio is -0.292, consistent with systematic deterioration as size increases.

## Interpretation limits

- `GEDS people / TBS employees` is a directory coverage ratio, not an accuracy percentage.
- Ratios above 100% demonstrate population-definition, timing, stale-record, or directory-membership differences.
- The three-month reference-date difference can cause legitimate movement.
- The 25-person page ceiling makes GEDS counts lower bounds, especially for large organization units.
- The notebook is structurally valid but unexecuted because Jupyter packages are not installed in the current Python environment.
