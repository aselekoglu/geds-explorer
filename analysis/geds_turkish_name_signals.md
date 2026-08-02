# GEDS Turkish-name signals

## Result

The current canonical GEDS snapshot has **788 public directory records** with
an exact match on both sides of the name after ASCII normalization:

- at least one given-name token matches the Turkish first-name corpus;
- at least one surname token matches the Turkish surname corpus.

The prior three-record result was invalid for the intended use: it relied on
only small top-name lists and did not correctly preserve the broad ASCII corpus.
The revised method normalizes both `Cagatay` and `Cag-atay` style data tokens
against the same key as the Turkish-character form. For example:

```text
normalize("Cagatay") == normalize("Ca-gatay") == "cagatay"
normalize("Gursel") == "gursel"
```

This is still a **name-list signal**, not evidence of nationality,
citizenship, ethnicity, ancestry, or identity. The wide corpus can include
cross-cultural names, so use `first_name_corpus_rank` and
`surname_corpus_rank` to sort or filter the spreadsheet rather than treating
all candidates as equally strong.

The complete output is
[`geds_turkish_name_signals.csv`](geds_turkish_name_signals.csv). It includes
every available current-person field from `people_current`, the GEDS URL, and
the matched tokens, ranks, tier, and basis.

## Method

1. Read only `outputs/master/geds-master.sqlite`, `people_current`, where
   `presence_status = 'present'`. This preserves the canonical one-record-per-
   GEDS-URL grain.
2. Parse normal GEDS `Surname, Given names` display names. Match all tokens on
   either side so multi-part names do not silently lose a valid signal.
3. Fold Unicode diacritics and Turkish dotless-i to an ASCII alphanumeric key.
   The corpus itself is stored in ASCII, so characterless GEDS names are
   intentionally supported.
4. Use the separate name files from the MIT-licensed
   [mkozturk/trnames](https://github.com/mkozturk/trnames) corpus:
   7,427 unique first names and 28,604 surnames. The repository describes the
   corpus as being parsed from 49.6 million people and excludes names observed
   fewer than 100 times.
5. Require an exact normalized match for at least one given name and one
   surname. The CSV saves the corpus rank for both matches.

## Limits

- Snapshot: `edd5d0f4269da97163b33a5cf7dd8c850ad51331a913721e0ce7a07e1977fce5`,
  as of 2026-07-09 07:05 UTC; 193,163 present records; quality
  `partial_overlay`.
- The input does not contain citizenship or ethnicity, and names do not prove
  either attribute.
- Exact token matching avoids fuzzy-match false positives, but may miss unusual
  spelling variants, abbreviations, and some multi-word family names.
- The 788-row broad list favors recall. For a tighter review queue, sort by the
  two rank columns and examine the lowest ranks first.

## Reproduce

```powershell
py analysis\export_turkish_name_signals.py
```

The corpus source manifest is in
[`turkish_name_sources.json`](turkish_name_sources.json), downloaded corpus
files are under [`sources/trnames`](sources/trnames), and run metadata are in
[`geds_turkish_name_signals_summary.json`](geds_turkish_name_signals_summary.json).
