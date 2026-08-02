"""Export conservative Turkish-name signals from the canonical GEDS directory.

This script finds name-list matches only. It must not be used to assert a
person's nationality, citizenship, ethnicity, ancestry, or identity.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sqlite3
import sys
import unicodedata
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "outputs" / "master" / "geds-master.sqlite"
DEFAULT_SOURCES = ROOT / "analysis" / "turkish_name_sources.json"
DEFAULT_CSV = ROOT / "analysis" / "geds_turkish_name_signals.csv"
DEFAULT_SUMMARY = ROOT / "analysis" / "geds_turkish_name_signals_summary.json"


def normalize(value: str) -> str:
    """Return a case-insensitive, diacritic-free ASCII lookup key."""
    value = value.strip().casefold().translate(str.maketrans({"\u0131": "i"}))
    value = unicodedata.normalize("NFKD", value)
    return "".join(char for char in value if char.isascii() and char.isalnum())


def csv_name_ranks(path: Path, column: str) -> dict[str, int]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return {
            normalize(row[column]): rank
            for rank, row in enumerate(reader, start=1)
            if row.get(column) and normalize(row[column])
        }


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_sources(path: Path) -> dict[str, Any]:
    source_data = json.loads(path.read_text(encoding="utf-8"))
    files = source_data["sources"]["trnames"]["files"]
    male_path = ROOT / files["male_first"]
    female_path = ROOT / files["female_first"]
    surname_path = ROOT / files["surnames"]

    male_ranks = csv_name_ranks(male_path, "name")
    female_ranks = csv_name_ranks(female_path, "name")
    source_data["first_name_ranks"] = {
        key: min(rank for rank in (male_ranks.get(key), female_ranks.get(key)) if rank is not None)
        for key in male_ranks.keys() | female_ranks.keys()
    }
    source_data["surname_ranks"] = csv_name_ranks(surname_path, "lastname")
    source_data["corpus_metadata"] = {
        "first_name_count": len(source_data["first_name_ranks"]),
        "surname_count": len(source_data["surname_ranks"]),
        "file_sha256": {
            "male_first": file_sha256(male_path),
            "female_first": file_sha256(female_path),
            "surnames": file_sha256(surname_path),
        },
    }
    return source_data


def name_token_groups(display_name: str) -> tuple[list[str], list[str]] | None:
    """Return (given-name tokens, surname tokens) for GEDS and fallback forms."""
    if "," in display_name:
        surname_part, given_part = display_name.split(",", 1)
        surname_tokens = [token for token in surname_part.split() if normalize(token)]
        given_tokens = [token for token in given_part.split() if normalize(token)]
        return (given_tokens, surname_tokens) if surname_tokens and given_tokens else None

    tokens = [token for token in display_name.split() if normalize(token)]
    return ([tokens[0]], [tokens[-1]]) if len(tokens) >= 2 else None


def best_match(tokens: list[str], ranks: dict[str, int]) -> tuple[str, int] | None:
    matches = [(token, ranks[normalize(token)]) for token in tokens if normalize(token) in ranks]
    return min(matches, key=lambda pair: pair[1]) if matches else None


def export_signals(
    *, db_path: Path, source_path: Path, csv_path: Path, summary_path: Path
) -> dict[str, Any]:
    if not db_path.is_file():
        raise FileNotFoundError(f"Canonical database not found: {db_path}")

    sources = load_sources(source_path)
    connection = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    try:
        snapshot_row = connection.execute(
            """
            SELECT s.snapshot_id, s.as_of_at, s.quality_status
            FROM canonical_state c
            JOIN canonical_snapshots s ON s.snapshot_id = c.current_snapshot_id
            WHERE c.singleton = 1
            """
        ).fetchone()
        records = connection.execute(
            """
            SELECT source_url, display_name, title, org_path, org_dn, department_dn,
                   department_name, org_unit, canonical_path_json, last_seen_at,
                   snapshot_id, missing_streak, presence_status
            FROM people_current
            WHERE presence_status = 'present'
            ORDER BY display_name COLLATE NOCASE, source_url
            """
        ).fetchall()
    finally:
        connection.close()

    matches: list[dict[str, str | int]] = []
    for row in records:
        token_groups = name_token_groups(row["display_name"])
        if token_groups is None:
            continue
        given_tokens, surname_tokens = token_groups
        first_match = best_match(given_tokens, sources["first_name_ranks"])
        surname_match = best_match(surname_tokens, sources["surname_ranks"])
        if first_match is None or surname_match is None:
            continue
        first_name, first_name_rank = first_match
        surname, surname_rank = surname_match
        matches.append(
            {
                **dict(row),
                "matched_first_name": first_name,
                "matched_surname": surname,
                "first_name_corpus_rank": first_name_rank,
                "surname_corpus_rank": surname_rank,
                "match_tier": "corpus_both_ascii_normalized",
                "match_basis": "trnames first-name corpus + trnames surname corpus; exact ASCII-normalized tokens",
            }
        )

    urls = [str(row["source_url"]) for row in matches]
    if len(urls) != len(set(urls)):
        raise ValueError("Output has duplicate GEDS source URLs")

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "source_url", "display_name", "title", "department_name", "department_dn",
        "org_unit", "org_dn", "org_path", "canonical_path_json", "last_seen_at",
        "snapshot_id", "missing_streak", "presence_status", "matched_first_name",
        "matched_surname", "first_name_corpus_rank", "surname_corpus_rank",
        "match_tier", "match_basis",
    ]
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(matches)

    by_department = Counter(str(row["department_name"]) for row in matches)
    summary = {
        "generated_on": date.today().isoformat(),
        "canonical_database": str(db_path.relative_to(ROOT)),
        "canonical_snapshot_id": snapshot_row["snapshot_id"] if snapshot_row else None,
        "canonical_snapshot_as_of": snapshot_row["as_of_at"] if snapshot_row else None,
        "canonical_snapshot_quality": snapshot_row["quality_status"] if snapshot_row else None,
        "input_present_people": len(records),
        "candidate_records": len(matches),
        "unique_geds_urls": len(set(urls)),
        "match_tier_counts": Counter(str(row["match_tier"]) for row in matches),
        "top_departments": [
            {"department_name": name, "candidates": count}
            for name, count in by_department.most_common(20)
        ],
        "source_file": str(source_path.relative_to(ROOT)),
        "corpus_metadata": sources["corpus_metadata"],
        "output_csv": str(csv_path.relative_to(ROOT)),
        "limitation": sources["matching_rule"],
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--sources", type=Path, default=DEFAULT_SOURCES)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    args = parser.parse_args()
    result = export_signals(
        db_path=args.db.resolve(),
        source_path=args.sources.resolve(),
        csv_path=args.csv.resolve(),
        summary_path=args.summary.resolve(),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, default=dict))


if __name__ == "__main__":
    main()
