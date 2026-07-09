from __future__ import annotations

import json
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_PATH = ROOT / "analysis" / "geds_analysis_snapshot.json"
OUTPUT_PATH = ROOT / "analysis" / "geds_report.sqlite"


def create_table(
    connection: sqlite3.Connection,
    table: str,
    columns: list[tuple[str, str]],
    rows: list[dict],
) -> None:
    connection.execute(f'DROP TABLE IF EXISTS "{table}"')
    definition = ", ".join(f'"{name}" {kind}' for name, kind in columns)
    connection.execute(f'CREATE TABLE "{table}" ({definition})')
    names = [name for name, _ in columns]
    placeholders = ", ".join("?" for _ in names)
    quoted_names = ", ".join(f'"{name}"' for name in names)
    connection.executemany(
        f'INSERT INTO "{table}" ({quoted_names}) VALUES ({placeholders})',
        [[row.get(name) for name in names] for row in rows],
    )


def main() -> None:
    snapshot = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    connection = sqlite3.connect(OUTPUT_PATH)
    try:
        coverage_label = {
            "complete": ("Finished source run", 1),
            "complete_or_drained": ("Queue-drained in active batch", 2),
            "in_progress": ("In progress", 3),
            "not_started": ("Not started", 4),
        }
        coverage = [
            {
                "status": coverage_label[row["status"]][0],
                "departments": row["departments"],
                "status_group": row["status"],
                "sort_order": coverage_label[row["status"]][1],
            }
            for row in snapshot["coverage_counts"]
        ]
        create_table(
            connection,
            "coverage",
            [
                ("status", "TEXT"),
                ("departments", "INTEGER"),
                ("status_group", "TEXT"),
                ("sort_order", "INTEGER"),
            ],
            coverage,
        )

        create_table(
            connection,
            "people_per_org_distribution",
            [("people_per_org", "INTEGER"), ("org_units", "INTEGER")],
            snapshot["people_per_org_distribution"],
        )

        category_label = {
            "Artificial intelligence": "AI",
            "Data and analytics": "Data & analytics",
            "Software and development": "Software & development",
            "Cybersecurity": "Cybersecurity",
            "Digital and IT operations": "Digital & IT",
        }
        category_sort = {name: index for index, name in enumerate(category_label, 1)}
        org_by_category = {
            row["category"]: row for row in snapshot["org_categories"]
        }
        tech_signals = []
        for title_row in snapshot["title_categories"]:
            category = title_row["category"]
            org_row = org_by_category[category]
            for signal_sort, (signal, people) in enumerate(
                (
                    ("Title keyword", title_row["people"]),
                    (
                        "Matching org path",
                        org_row["people_assigned_to_matching_orgs"],
                    ),
                ),
                1,
            ):
                tech_signals.append(
                    {
                        "category": category_label[category],
                        "signal": signal,
                        "people": people,
                        "org_units": org_row["org_units"],
                        "category_full": category,
                        "category_sort": category_sort[category],
                        "signal_sort": signal_sort,
                    }
                )
        create_table(
            connection,
            "tech_signals",
            [
                ("category", "TEXT"),
                ("signal", "TEXT"),
                ("people", "INTEGER"),
                ("org_units", "INTEGER"),
                ("category_full", "TEXT"),
                ("category_sort", "INTEGER"),
                ("signal_sort", "INTEGER"),
            ],
            tech_signals,
        )

        create_table(
            connection,
            "top_departments",
            [
                ("department", "TEXT"),
                ("people", "INTEGER"),
                ("org_units", "INTEGER"),
                ("coverage_status", "TEXT"),
                ("people_share", "REAL"),
                ("tech_title_people", "INTEGER"),
                ("missing_title_rate", "REAL"),
                ("rank", "INTEGER"),
            ],
            snapshot["top_departments"][:10],
        )

        headline = snapshot["headline"]
        quality_checks = [
            {
                "check_name": "Person-list ceiling",
                "result": (
                    f'{headline["orgs_at_observed_people_cap"]:,} org units stop at '
                    f'exactly {headline["maximum_people_per_org"]} people; '
                    f'{headline["people_in_capped_orgs"]:,} records sit in capped units'
                ),
                "severity": "High",
                "severity_order": 4,
                "implication": "Person and title totals are lower bounds, not workforce counts.",
            },
            {
                "check_name": "Active crawl completeness",
                "result": (
                    f'{headline["complete_or_drained_departments"]} of '
                    f'{headline["departments"]} departments finished or queue-drained; '
                    f'{headline["in_progress_departments"]} in progress'
                ),
                "severity": "High",
                "severity_order": 4,
                "implication": "Department comparisons remain provisional.",
            },
            {
                "check_name": "Title completeness",
                "result": (
                    f'{headline["missing_titles"]:,} of {headline["people"]:,} '
                    "captured people lack titles"
                ),
                "severity": "Medium",
                "severity_order": 3,
                "implication": "Title-search recall varies sharply by department.",
            },
            {
                "check_name": "Potential duplicate signatures",
                "result": (
                    f'{headline["potential_duplicate_identity_groups"]} normalized '
                    "name-title-org-department groups need review"
                ),
                "severity": "Medium",
                "severity_order": 3,
                "implication": "Review before identity-level deduplication; do not auto-merge.",
            },
            {
                "check_name": "Crawl error classification",
                "result": "3 Windows charmap errors occurred after page commit inside the crawl try block",
                "severity": "Medium",
                "severity_order": 3,
                "implication": "Operational errors can represent logging failures rather than fetch failures.",
            },
            {
                "check_name": "Relational integrity",
                "result": "0 orphan person-to-org rows and 0 orphan org-parent rows",
                "severity": "Low",
                "severity_order": 1,
                "implication": "The captured hierarchy is internally consistent.",
            },
            {
                "check_name": "Official source links",
                "result": "0 invalid person URLs and 0 invalid org URLs",
                "severity": "Low",
                "severity_order": 1,
                "implication": "Captured records retain valid official GEDS navigation.",
            },
            {
                "check_name": "Privacy schema",
                "result": "0 persisted contact-data columns",
                "severity": "Low",
                "severity_order": 1,
                "implication": "The schema follows the contact-data exclusion.",
            },
            {
                "check_name": "Cross-source key overlap",
                "result": "0 duplicate person URLs and 0 duplicate org DNs",
                "severity": "Low",
                "severity_order": 1,
                "implication": "The controlling-source partition avoids double counting.",
            },
        ]
        create_table(
            connection,
            "quality_checks",
            [
                ("check_name", "TEXT"),
                ("result", "TEXT"),
                ("severity", "TEXT"),
                ("severity_order", "INTEGER"),
                ("implication", "TEXT"),
            ],
            quality_checks,
        )

        ai_orgs = [
            {
                "department": row["department"],
                "org_unit": row["org_unit"],
                "captured_people": row["people"],
                "coverage_status": row["coverage_status"],
                "org_path": row["org_path"],
            }
            for row in snapshot["top_org_units_by_category"][
                "Artificial intelligence"
            ][:8]
        ]
        create_table(
            connection,
            "ai_orgs",
            [
                ("department", "TEXT"),
                ("org_unit", "TEXT"),
                ("captured_people", "INTEGER"),
                ("coverage_status", "TEXT"),
                ("org_path", "TEXT"),
            ],
            ai_orgs,
        )

        title_gaps = [
            {
                "department": row["department"],
                "captured_people": row["people"],
                "missing_titles": row["missing_titles"],
                "missing_title_rate": row["missing_title_rate"],
                "coverage_status": row["coverage_status"],
            }
            for row in snapshot["top_missing_title_departments"][:8]
        ]
        create_table(
            connection,
            "title_gaps",
            [
                ("department", "TEXT"),
                ("captured_people", "INTEGER"),
                ("missing_titles", "INTEGER"),
                ("missing_title_rate", "REAL"),
                ("coverage_status", "TEXT"),
            ],
            title_gaps,
        )

        connection.execute(
            "CREATE TABLE IF NOT EXISTS report_metadata (key TEXT PRIMARY KEY, value TEXT)"
        )
        connection.execute("DELETE FROM report_metadata")
        connection.executemany(
            "INSERT INTO report_metadata (key, value) VALUES (?, ?)",
            [
                ("generated_at_utc", snapshot["metadata"]["generated_at_utc"]),
                ("source_snapshot", str(SNAPSHOT_PATH)),
                ("privacy", snapshot["metadata"]["privacy"]),
            ],
        )
        connection.commit()
    finally:
        connection.close()
    print(OUTPUT_PATH)


if __name__ == "__main__":
    main()
