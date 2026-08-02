# Plan: GEDS Turkish-name signals analysis

## Scope

Produce a reproducible, file-based analysis of the current GEDS canonical
directory. No UI, API, crawler, or database schema changes are in scope.

The deliverable is **not** a statement of nationality, citizenship, ethnicity,
or identity. It is a conservative list of public GEDS directory records whose
displayed names match Turkish name-list signals, with the exact matching basis
recorded for every row.

## Evidence and decisions

- Use `outputs/master/geds-master.sqlite`, table `people_current`, as the
  single canonical input. It is already deduplicated by `source_url` and has
  the requested display name, title, department, organization, path, and URL.
- Use the separate first-name and surname files in the MIT-licensed `trnames`
  corpus, which documents its Turkish population basis. Keep the official NVI
  and TUİK lists as reference sources.
- Normalize whitespace, Unicode diacritics, Turkish dotless-i, apostrophes,
  hyphens, and case to exact ASCII keys. Preserve original database values in
  the output.
- Parse normal GEDS `Surname, Given names` form and inspect every token on each
  side, preserving a matched token and corpus rank for audit.
- Require both a given-name and surname signal. Do not emit first-name-only or
  surname-only matches.
- Emit a CSV with every non-sensitive field available in `people_current` and a
  companion Markdown methods/validation note. No contact data are present in
  this source or requested for output.

## Dependency graph

```text
Canonical people_current
        + trnames separate first-name/surname lists
                    |
          ASCII normalization + both-side token rule
                    |
          deduplicated candidate CSV + methods note
                    |
           row/count/URL/spot-check validation
```

## Tasks

### Task 1: Verify canonical input and source lists

**Acceptance criteria**

- `people_current` has a current snapshot ID and unique `source_url` values.
- Official and secondary sources are saved or pinned with their retrieval URL.

**Verification**

- Query row counts, snapshot metadata, and duplicate URL count read-only.
- Confirm that the source files can be parsed into non-empty normalized sets.

### Task 2: Run the conservative name-signal matcher

**Acceptance criteria**

- Each emitted row has a first-name and surname signal plus an explicit tier.
- Original GEDS fields are preserved; no crawler/UI data changes occur.

**Verification**

- Validate output uniqueness by GEDS URL.
- Recompute output tiers from the saved match evidence.

### Task 3: Document limits and inspect results

**Acceptance criteria**

- Methods note clearly distinguishes naming signal from identity.
- Representative rows and aggregate counts are consistent with the CSV.

**Verification**

- Check CSV header/row count, non-empty URL/title/department rates, and a
  small manual sample against the canonical database.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| A name does not establish Turkish identity or citizenship | Use the label `Turkish-name signal`; do not infer or claim identity. |
| Common cross-cultural names create false positives | Require both first and surname signals and preserve source/tier evidence. |
| Name lists are incomplete or historical | Treat list as a candidate-finding heuristic, record source version/date, and prefer precision over recall. |
| Historical crawl DBs contain duplicate people | Read only canonical `people_current`, keyed by `source_url`. |

## Completion checkpoint

- Candidate list, source data, and methods note exist under `analysis/`.
- Output is reproducible from the saved script and sources.
- Counts and a manual sample pass validation.
