from __future__ import annotations

import csv
import json
import math
import re
import sqlite3
import statistics
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[1]
GEDS_SNAPSHOT = ROOT / "analysis" / "geds_analysis_snapshot.json"
TBS_HTML = ROOT / "analysis" / "tbs_population_by_department.html"
OUTPUT_JSON = ROOT / "analysis" / "geds_vs_tbs_2026.json"
OUTPUT_CSV = ROOT / "analysis" / "geds_vs_tbs_2026.csv"
OUTPUT_DB = ROOT / "analysis" / "geds_vs_tbs_2026.sqlite"

TBS_URL = (
    "https://www.canada.ca/en/treasury-board-secretariat/services/"
    "innovation/human-resources-statistics/"
    "population-federal-public-service-department.html"
)

# TBS labels that differ materially from the current GEDS department label.
ALIASES: dict[str, list[str]] = {
    "Department of Finance Canada": ["Finance Canada"],
    "Department of Justice Canada": ["Justice Canada"],
    "Elections Canada": ["Office of the Chief Electoral Officer"],
    "Office of the Governor General's Secretary": [
        "Office of the Secretary to the Governor General"
    ],
    "Offices of the information and Privacy Commissioners of Canada": [
        "Office of the Information Commissioner of Canada",
        "Office of the Privacy Commissioner of Canada",
    ],
    "Patented Medicine Prices Review Board Canada": [
        "Patented Medicine Prices Review Board"
    ],
    "Public Service Commission of Canada": ["Public Service Commission"],
    "RCMP External Review Committee": [
        "Royal Canadian Mounted Police External Review Committee"
    ],
    "Registrar of the Supreme Court of Canada": ["Supreme Court of Canada"],
    "Communications Security Establishment": [
        "Communications Security Establishment Canada"
    ],
    "National Film Board": ["National Film Board of Canada"],
    "Natural Sciences and Engineering Research Canada": [
        "Natural Sciences and Engineering Research Council of Canada"
    ],
    "The Correctional Investigator Canada": [
        "Office of the Correctional Investigator Canada"
    ],
}

# These current non-zero TBS rows have no defensible one-to-one GEDS department
# comparison. They remain visible in the output instead of being force-matched.
EXCLUSIONS: dict[str, str] = {
    "Federal Judges not part of any department": (
        "The TBS row is explicitly outside any department; GEDS has no equivalent "
        "department grain."
    ),
    "Western Economic Diversification Canada": (
        "The legacy organization was split into PrairiesCan and PacifiCan; the "
        "current TBS label cannot be assigned to one current GEDS department "
        "without an authoritative crosswalk."
    ),
    "Indian Oil and Gas Canada": (
        "TBS reports a separate population, while GEDS does not expose it as a "
        "standalone department; mapping it into CIRNAC would mix grains."
    ),
    "Office of the Superintendent of Financial Institutions Canada": (
        "No standalone GEDS department was present in the completed 156-department "
        "catalog."
    ),
    "Statistical Survey Operations": (
        "TBS reports it separately, while GEDS does not expose a separate "
        "department; folding it into Statistics Canada would double-count the TBS "
        "comparison."
    ),
}

DEFINITION_FLAGS: dict[str, str] = {
    "National Defence": (
        "TBS excludes Canadian Armed Forces members; GEDS directory membership "
        "may not apply the same population rule."
    ),
    "Royal Canadian Mounted Police": (
        "TBS includes only RCMP public-service employees and excludes Regular "
        "Force and Civilian Members; GEDS may use a broader directory population."
    ),
    "Global Affairs Canada": (
        "TBS excludes locally engaged employees outside Canada; GEDS may list "
        "people outside that Pay System population."
    ),
}


def normalize_name(value: str) -> str:
    # Remove the bilingual expansion used only in the ISED GEDS display label.
    value = re.sub(r"\s+-\s+Innovation, Sciences.*$", "", value, flags=re.I)
    decomposed = unicodedata.normalize("NFKD", value)
    ascii_text = "".join(
        character
        for character in decomposed
        if not unicodedata.combining(character)
    )
    return re.sub(r"[^a-z0-9]+", " ", ascii_text.casefold()).strip()


def parse_tbs_rows() -> tuple[list[dict[str, Any]], int]:
    soup = BeautifulSoup(TBS_HTML.read_text(encoding="utf-8"), "html.parser")
    table = soup.find("table")
    if table is None:
        raise RuntimeError("TBS population table was not found")

    section: str | None = None
    rows: list[dict[str, Any]] = []
    reported_total: int | None = None
    for table_row in table.find_all("tr"):
        cells = [
            cell.get_text(" ", strip=True)
            for cell in table_row.find_all(["th", "td"])
        ]
        if len(cells) == 1:
            section = cells[0]
            continue
        if len(cells) != 13:
            continue
        if cells[0] == "Department or agency":
            continue
        value = int(cells[-1].replace(",", ""))
        if cells[0] == "Total":
            reported_total = value
            continue
        rows.append(
            {
                "tbs_department": cells[0],
                "tbs_employees_2026": value,
                "tbs_section": section,
            }
        )
    if reported_total is None:
        raise RuntimeError("TBS 2026 total was not found")
    return rows, reported_total


def materialize_sqlite(payload: dict[str, Any]) -> None:
    connection = sqlite3.connect(OUTPUT_DB)
    try:
        connection.executescript(
            """
            DROP TABLE IF EXISTS comparison;
            DROP TABLE IF EXISTS exclusions;
            DROP TABLE IF EXISTS unmatched_geds;
            DROP TABLE IF EXISTS size_bands;
            DROP TABLE IF EXISTS ratio_bands;
            DROP TABLE IF EXISTS summary;
            DROP TABLE IF EXISTS metadata;

            CREATE TABLE comparison (
                tbs_department TEXT PRIMARY KEY,
                geds_departments TEXT NOT NULL,
                tbs_section TEXT,
                tbs_employees_2026 INTEGER NOT NULL,
                geds_people INTEGER NOT NULL,
                difference INTEGER NOT NULL,
                directory_ratio REAL NOT NULL,
                directory_gap_rate REAL NOT NULL,
                match_type TEXT NOT NULL,
                org_units INTEGER NOT NULL,
                orgs_at_people_cap INTEGER NOT NULL,
                people_in_capped_orgs INTEGER NOT NULL,
                definition_flag TEXT
            );
            CREATE TABLE exclusions (
                tbs_department TEXT PRIMARY KEY,
                tbs_employees_2026 INTEGER NOT NULL,
                reason TEXT NOT NULL
            );
            CREATE TABLE unmatched_geds (
                geds_department TEXT PRIMARY KEY,
                geds_people INTEGER NOT NULL
            );
            CREATE TABLE size_bands (
                size_band TEXT PRIMARY KEY,
                sort_order INTEGER NOT NULL,
                organizations INTEGER NOT NULL,
                tbs_employees_2026 INTEGER NOT NULL,
                geds_people INTEGER NOT NULL,
                weighted_directory_ratio REAL NOT NULL,
                median_organization_ratio REAL NOT NULL
            );
            CREATE TABLE ratio_bands (
                ratio_band TEXT PRIMARY KEY,
                sort_order INTEGER NOT NULL,
                organizations INTEGER NOT NULL
            );
            CREATE TABLE summary (
                metric TEXT PRIMARY KEY,
                value REAL NOT NULL
            );
            CREATE TABLE metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        )
        comparison_columns = [
            "tbs_department",
            "geds_departments",
            "tbs_section",
            "tbs_employees_2026",
            "geds_people",
            "difference",
            "directory_ratio",
            "directory_gap_rate",
            "match_type",
            "org_units",
            "orgs_at_people_cap",
            "people_in_capped_orgs",
            "definition_flag",
        ]
        connection.executemany(
            f"""
            INSERT INTO comparison ({", ".join(comparison_columns)})
            VALUES ({", ".join("?" for _ in comparison_columns)})
            """,
            [
                [row.get(column) for column in comparison_columns]
                for row in payload["comparison"]
            ],
        )
        connection.executemany(
            "INSERT INTO exclusions VALUES (?, ?, ?)",
            [
                (
                    row["tbs_department"],
                    row["tbs_employees_2026"],
                    row["reason"],
                )
                for row in payload["excluded_tbs_rows"]
            ],
        )
        connection.executemany(
            "INSERT INTO unmatched_geds VALUES (?, ?)",
            [
                (row["department"], row["geds_people"])
                for row in payload["unmatched_geds_departments"]
            ],
        )
        connection.executemany(
            "INSERT INTO size_bands VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    row["size_band"],
                    row["sort_order"],
                    row["organizations"],
                    row["tbs_employees_2026"],
                    row["geds_people"],
                    row["weighted_directory_ratio"],
                    row["median_organization_ratio"],
                )
                for row in payload["size_bands"]
            ],
        )
        connection.executemany(
            "INSERT INTO ratio_bands VALUES (?, ?, ?)",
            [
                (
                    row["ratio_band"],
                    row["sort_order"],
                    row["organizations"],
                )
                for row in payload["ratio_bands"]
            ],
        )
        connection.executemany(
            "INSERT INTO summary VALUES (?, ?)",
            [
                (key, value)
                for key, value in payload["summary"].items()
                if isinstance(value, (int, float))
            ],
        )
        connection.executemany(
            "INSERT INTO metadata VALUES (?, ?)",
            [
                ("generated_at_utc", payload["metadata"]["generated_at_utc"]),
                ("tbs_source_url", TBS_URL),
                ("tbs_as_of", "2026-03-31"),
                (
                    "geds_snapshot_generated_at_utc",
                    payload["metadata"]["geds_snapshot_generated_at_utc"],
                ),
            ],
        )
        connection.commit()
    finally:
        connection.close()


def main() -> None:
    geds_snapshot = json.loads(GEDS_SNAPSHOT.read_text(encoding="utf-8"))
    geds_rows = {
        row["department"]: row for row in geds_snapshot["departments"]
    }
    normalized_geds: dict[str, list[str]] = {}
    for department in geds_rows:
        normalized_geds.setdefault(normalize_name(department), []).append(department)

    tbs_rows, tbs_reported_total = parse_tbs_rows()
    if sum(row["tbs_employees_2026"] for row in tbs_rows) != tbs_reported_total:
        raise RuntimeError("Parsed TBS rows do not reconcile to the published total")

    comparison: list[dict[str, Any]] = []
    excluded_tbs_rows: list[dict[str, Any]] = []
    zero_population_rows: list[dict[str, Any]] = []
    matched_geds_names: set[str] = set()

    for tbs_row in tbs_rows:
        tbs_name = tbs_row["tbs_department"]
        tbs_count = tbs_row["tbs_employees_2026"]
        if tbs_count == 0:
            zero_population_rows.append(tbs_row)
            continue
        if tbs_name in EXCLUSIONS:
            excluded_tbs_rows.append(
                {**tbs_row, "reason": EXCLUSIONS[tbs_name]}
            )
            continue

        if tbs_name in ALIASES:
            mapped_names = ALIASES[tbs_name]
            match_type = "aggregate_alias" if len(mapped_names) > 1 else "alias"
        else:
            candidates = normalized_geds.get(normalize_name(tbs_name), [])
            if len(candidates) != 1:
                raise RuntimeError(
                    f"Unresolved TBS organization: {tbs_name!r}; candidates={candidates}"
                )
            mapped_names = candidates
            match_type = "exact_normalized"

        missing_aliases = [name for name in mapped_names if name not in geds_rows]
        if missing_aliases:
            raise RuntimeError(
                f"Alias target missing from GEDS snapshot: {missing_aliases}"
            )
        if matched_geds_names.intersection(mapped_names):
            raise RuntimeError(
                f"GEDS department reused across TBS matches: {mapped_names}"
            )
        matched_geds_names.update(mapped_names)

        selected = [geds_rows[name] for name in mapped_names]
        geds_people = sum(row["people"] for row in selected)
        directory_ratio = geds_people / tbs_count
        comparison.append(
            {
                **tbs_row,
                "geds_departments": " + ".join(mapped_names),
                "geds_people": geds_people,
                "difference": geds_people - tbs_count,
                "directory_ratio": round(directory_ratio, 6),
                "directory_gap_rate": round(1 - directory_ratio, 6),
                "match_type": match_type,
                "org_units": sum(row["org_units"] for row in selected),
                "orgs_at_people_cap": sum(
                    row["orgs_at_people_cap"] for row in selected
                ),
                "people_in_capped_orgs": sum(
                    row["people_in_capped_orgs"] for row in selected
                ),
                "definition_flag": DEFINITION_FLAGS.get(tbs_name),
            }
        )

    comparison.sort(key=lambda row: row["tbs_department"])
    matched_tbs_population = sum(
        row["tbs_employees_2026"] for row in comparison
    )
    matched_geds_people = sum(row["geds_people"] for row in comparison)
    ratios = [row["directory_ratio"] for row in comparison]
    ratio_bands = {
        "below_25_percent": sum(ratio < 0.25 for ratio in ratios),
        "25_to_50_percent": sum(0.25 <= ratio < 0.5 for ratio in ratios),
        "50_to_75_percent": sum(0.5 <= ratio < 0.75 for ratio in ratios),
        "75_to_100_percent": sum(0.75 <= ratio < 1 for ratio in ratios),
        "at_or_above_100_percent": sum(ratio >= 1 for ratio in ratios),
    }
    ratio_band_rows = [
        {
            "ratio_band": "Under 25%",
            "sort_order": 1,
            "organizations": ratio_bands["below_25_percent"],
        },
        {
            "ratio_band": "25–49%",
            "sort_order": 2,
            "organizations": ratio_bands["25_to_50_percent"],
        },
        {
            "ratio_band": "50–74%",
            "sort_order": 3,
            "organizations": ratio_bands["50_to_75_percent"],
        },
        {
            "ratio_band": "75–99%",
            "sort_order": 4,
            "organizations": ratio_bands["75_to_100_percent"],
        },
        {
            "ratio_band": "100%+",
            "sort_order": 5,
            "organizations": ratio_bands["at_or_above_100_percent"],
        },
    ]
    sensitivity_rows = [
        row for row in comparison if row["definition_flag"] is None
    ]
    sensitivity_tbs = sum(
        row["tbs_employees_2026"] for row in sensitivity_rows
    )
    sensitivity_geds = sum(row["geds_people"] for row in sensitivity_rows)

    size_band_specs = [
        ("Under 100", 1, 0, 100),
        ("100–499", 2, 100, 500),
        ("500–1,999", 3, 500, 2_000),
        ("2,000–9,999", 4, 2_000, 10_000),
        ("10,000+", 5, 10_000, math.inf),
    ]
    size_bands: list[dict[str, Any]] = []
    for label, sort_order, minimum, maximum in size_band_specs:
        selected = [
            row
            for row in comparison
            if minimum <= row["tbs_employees_2026"] < maximum
        ]
        tbs_sum = sum(row["tbs_employees_2026"] for row in selected)
        geds_sum = sum(row["geds_people"] for row in selected)
        size_bands.append(
            {
                "size_band": label,
                "sort_order": sort_order,
                "organizations": len(selected),
                "tbs_employees_2026": tbs_sum,
                "geds_people": geds_sum,
                "weighted_directory_ratio": round(geds_sum / tbs_sum, 6)
                if tbs_sum
                else 0,
                "median_organization_ratio": round(
                    statistics.median(
                        row["directory_ratio"] for row in selected
                    ),
                    6,
                )
                if selected
                else 0,
            }
        )

    def average_ranks(values: list[float]) -> list[float]:
        indexed = sorted(enumerate(values), key=lambda pair: pair[1])
        ranks = [0.0] * len(values)
        cursor = 0
        while cursor < len(indexed):
            end = cursor + 1
            while end < len(indexed) and indexed[end][1] == indexed[cursor][1]:
                end += 1
            average_rank = ((cursor + 1) + end) / 2
            for position in range(cursor, end):
                ranks[indexed[position][0]] = average_rank
            cursor = end
        return ranks

    log_sizes = [
        math.log10(row["tbs_employees_2026"]) for row in comparison
    ]
    spearman_size_ratio = statistics.correlation(
        average_ranks(log_sizes),
        average_ranks(ratios),
    )
    excluded_population = sum(
        row["tbs_employees_2026"] for row in excluded_tbs_rows
    )
    unmatched_geds_departments = sorted(
        [
            {
                "department": name,
                "geds_people": row["people"],
            }
            for name, row in geds_rows.items()
            if name not in matched_geds_names
        ],
        key=lambda row: (-row["geds_people"], row["department"]),
    )

    payload = {
        "metadata": {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "geds_snapshot_generated_at_utc": geds_snapshot["metadata"][
                "generated_at_utc"
            ],
            "tbs_source_url": TBS_URL,
            "tbs_page_updated": "2026-06-24",
            "tbs_population_as_of": "2026-03-31",
            "tbs_definition": (
                "Active employees in the Pay System, including all tenures, "
                "Governor-in-Council appointees, deputy ministers, and federal "
                "judges, subject to the exclusions documented by TBS."
            ),
            "geds_definition": (
                "Unique person source URLs captured from GEDS organization pages; "
                "not an authoritative employee population and censored at 25 "
                "people per organization page."
            ),
        },
        "summary": {
            "tbs_reported_total_2026": tbs_reported_total,
            "tbs_rows": len(tbs_rows),
            "tbs_nonzero_rows": sum(
                row["tbs_employees_2026"] > 0 for row in tbs_rows
            ),
            "matched_tbs_organizations": len(comparison),
            "matched_tbs_population": matched_tbs_population,
            "matched_geds_people": matched_geds_people,
            "weighted_directory_ratio": round(
                matched_geds_people / matched_tbs_population, 6
            ),
            "median_organization_ratio": round(statistics.median(ratios), 6),
            "mean_organization_ratio": round(statistics.mean(ratios), 6),
            "weighted_directory_ratio_excluding_definition_flags": round(
                sensitivity_geds / sensitivity_tbs, 6
            ),
            "matched_tbs_population_excluding_definition_flags": sensitivity_tbs,
            "matched_geds_people_excluding_definition_flags": sensitivity_geds,
            "spearman_size_vs_directory_ratio": round(
                spearman_size_ratio, 6
            ),
            "tbs_population_covered_by_crosswalk_rate": round(
                matched_tbs_population / tbs_reported_total, 6
            ),
            "excluded_tbs_organizations": len(excluded_tbs_rows),
            "excluded_tbs_population": excluded_population,
            "zero_population_tbs_rows": len(zero_population_rows),
            "unmatched_geds_departments": len(unmatched_geds_departments),
            **ratio_bands,
        },
        "comparison": comparison,
        "size_bands": size_bands,
        "ratio_bands": ratio_band_rows,
        "largest_absolute_gaps": sorted(
            comparison,
            key=lambda row: (
                row["tbs_employees_2026"] - row["geds_people"]
            ),
            reverse=True,
        )[:20],
        "lowest_directory_ratios": sorted(
            comparison, key=lambda row: row["directory_ratio"]
        )[:20],
        "highest_directory_ratios": sorted(
            comparison, key=lambda row: row["directory_ratio"], reverse=True
        )[:20],
        "excluded_tbs_rows": excluded_tbs_rows,
        "zero_population_tbs_rows": zero_population_rows,
        "unmatched_geds_departments": unmatched_geds_departments,
    }

    OUTPUT_JSON.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    with OUTPUT_CSV.open("w", encoding="utf-8-sig", newline="") as csv_file:
        fieldnames = list(comparison[0])
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(comparison)
    materialize_sqlite(payload)
    print(json.dumps(payload["summary"], indent=2))
    print(OUTPUT_JSON)


if __name__ == "__main__":
    main()
