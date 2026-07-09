from __future__ import annotations

import argparse
import json
import math
import re
import sqlite3
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
CONTROL_DB = ROOT / "outputs" / "control" / "control.sqlite"

SOURCE_SPECS = (
    {
        "id": "initial-nine",
        "path": ROOT / "outputs" / "geds-snapshot-2026-07-08" / "geds.sqlite",
        "exclude_departments": set(),
    },
    {
        "id": "a-batch",
        "path": ROOT / "outputs" / "runs" / "2026-07-08" / "a-batch" / "geds.sqlite",
        "exclude_departments": set(),
    },
    {
        "id": "ised",
        "path": ROOT / "outputs" / "runs" / "2026-07-08" / "ised-crtc" / "geds.sqlite",
        "exclude_departments": set(),
    },
    {
        "id": "crtc",
        "path": ROOT / "outputs" / "runs" / "2026-07-08" / "crtc" / "geds.sqlite",
        "exclude_departments": set(),
    },
    {
        "id": "rest-batch",
        "path": ROOT / "outputs" / "runs" / "2026-07-08" / "rest-batch" / "geds.sqlite",
        # CRTC is also present in rest-batch. Prefer its finished dedicated run.
        "exclude_departments": {"OU=CRTC-CRTC,O=GC,C=CA"},
    },
)


TECH_PATTERNS = {
    "Artificial intelligence": re.compile(
        r"\b(artificial intelligence|intelligence artificielle|machine learning|"
        r"apprentissage automatique|deep learning|neural|ai|ia)\b"
    ),
    "Data and analytics": re.compile(
        r"\b(data|donnee\w*|analytic\w*|analytique\w*|statistic\w*|"
        r"statistique\w*|business intelligence|information management|"
        r"gestion de l information|database\w*|base de donnees)\b"
    ),
    "Software and development": re.compile(
        r"\b(software\w*|logiciel\w*|developer\w*|developpeur\w*|"
        r"programmer\w*|programmeur\w*|application\w*|devops|web)\b"
    ),
    "Cybersecurity": re.compile(
        r"\b(cyber\w*|infosec|information security|securite de l information|"
        r"it security|securite des ti|network security|securite reseau|"
        r"cloud security|securite infonuagique|security operations centre|"
        r"information assurance)\b"
    ),
    "Digital and IT operations": re.compile(
        r"\b(information technology|technologie\w* de l information|digital\w*|"
        r"numerique\w*|cloud|infonuagique\w*|nuage\w*|network\w*|reseau\w*|"
        r"systems? (?:analyst|administrator|architect|engineer)|"
        r"systemes? (?:analyste|administrateur|architecte|ingenieur)|"
        r"technology infrastructure|infrastructure technologique|ict|tic|it)\b"
    ),
}

CONTACT_FIELD_TOKENS = ("phone", "email", "fax", "address", "telephone", "courriel")
GEDS_URL_PREFIX = "https://geds-sage.gc.ca/"


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    decomposed = unicodedata.normalize("NFKD", value)
    ascii_text = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", ascii_text.casefold()).strip()


def categories_for(value: str | None) -> list[str]:
    normalized = normalize_text(value)
    return [name for name, pattern in TECH_PATTERNS.items() if pattern.search(normalized)]


def open_readonly(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("BEGIN")
    return connection


def table_names(connection: sqlite3.Connection) -> set[str]:
    return {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }


def rows_as_dicts(
    connection: sqlite3.Connection, query: str, parameters: Iterable[Any] = ()
) -> list[dict[str, Any]]:
    return [dict(row) for row in connection.execute(query, tuple(parameters))]


def get_catalog() -> dict[str, str]:
    connection = open_readonly(CONTROL_DB)
    try:
        return {
            row["dn"]: row["name"]
            for row in connection.execute(
                "SELECT dn, name FROM department_catalog ORDER BY name"
            )
        }
    finally:
        connection.close()


def get_controller_runs() -> list[dict[str, Any]]:
    connection = open_readonly(CONTROL_DB)
    try:
        return rows_as_dicts(
            connection,
            """
            SELECT
                jobs.name AS job_name,
                runs.id AS run_id,
                runs.started_at,
                runs.finished_at,
                runs.status AS controller_status,
                runs.request_count AS controller_request_count,
                runs.output_dir
            FROM crawl_runs AS runs
            LEFT JOIN crawl_jobs AS jobs ON jobs.id = runs.job_id
            ORDER BY runs.started_at
            """,
        )
    finally:
        connection.close()


def analyze() -> dict[str, Any]:
    generated_at = datetime.now(timezone.utc).isoformat()
    catalog = get_catalog()
    controller_runs = get_controller_runs()

    departments: dict[str, dict[str, Any]] = {}
    orgs: dict[str, dict[str, Any]] = {}
    people: dict[str, dict[str, Any]] = {}
    run_summaries: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    forbidden_schema_columns: list[dict[str, str]] = []
    duplicate_org_dns_across_selected_sources = 0
    duplicate_person_urls_across_selected_sources = 0

    for spec in SOURCE_SPECS:
        connection = open_readonly(spec["path"])
        try:
            run = dict(connection.execute("SELECT * FROM crawl_runs LIMIT 1").fetchone())
            queue_counts = {
                row["status"]: row["count"]
                for row in connection.execute(
                    "SELECT status, COUNT(*) AS count FROM crawl_queue GROUP BY status"
                )
            }
            run_summary = {
                "source": spec["id"],
                "path": str(spec["path"].relative_to(ROOT)),
                "status": run["status"],
                "started_at": run["started_at"],
                "finished_at": run.get("finished_at"),
                "heartbeat_at": run.get("heartbeat_at"),
                "request_count": run["request_count"],
                "rate_limit_seconds": run.get("rate_limit_seconds"),
                "queue_done": queue_counts.get("done", 0),
                "queue_pending": queue_counts.get("pending", 0),
                "queue_error": queue_counts.get("error", 0),
                "people": connection.execute(
                    "SELECT COUNT(*) FROM people_index"
                ).fetchone()[0],
                "org_units": connection.execute(
                    "SELECT COUNT(*) FROM org_units"
                ).fetchone()[0],
                "errors": connection.execute(
                    "SELECT COUNT(*) FROM crawl_errors"
                ).fetchone()[0],
            }
            if run_summary["started_at"]:
                end_text = (
                    run_summary["finished_at"]
                    or run_summary["heartbeat_at"]
                    or generated_at
                )
                start = datetime.fromisoformat(run_summary["started_at"])
                end = datetime.fromisoformat(end_text)
                elapsed = max((end - start).total_seconds(), 0.0)
                run_summary["elapsed_hours"] = round(elapsed / 3600, 3)
                run_summary["observed_requests_per_second"] = (
                    round(run_summary["request_count"] / elapsed, 4)
                    if elapsed
                    else None
                )
                run_summary["minimum_pending_hours_at_configured_rate"] = (
                    round(
                        run_summary["queue_pending"]
                        * (run_summary["rate_limit_seconds"] or 0)
                        / 3600,
                        3,
                    )
                    if run_summary["rate_limit_seconds"]
                    else None
                )
            run_summaries.append(run_summary)

            for table in ("departments", "org_units", "people_index"):
                for column in connection.execute(f'PRAGMA table_info("{table}")'):
                    column_name = column["name"].casefold()
                    if any(token in column_name for token in CONTACT_FIELD_TOKENS):
                        forbidden_schema_columns.append(
                            {
                                "source": spec["id"],
                                "table": table,
                                "column": column["name"],
                            }
                        )

            source_departments = rows_as_dicts(connection, "SELECT * FROM departments")
            included_dns = {
                row["dn"]
                for row in source_departments
                if row["dn"] not in spec["exclude_departments"]
            }

            queue_by_department = {
                row["department_dn"]: {
                    "queue_done": row["queue_done"],
                    "queue_pending": row["queue_pending"],
                    "queue_error": row["queue_error"],
                }
                for row in connection.execute(
                    """
                    SELECT
                        department_dn,
                        SUM(CASE WHEN status = 'done' THEN 1 ELSE 0 END) AS queue_done,
                        SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) AS queue_pending,
                        SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) AS queue_error
                    FROM crawl_queue
                    GROUP BY department_dn
                    """
                )
            }

            for row in source_departments:
                if row["dn"] not in included_dns:
                    continue
                queue = queue_by_department.get(
                    row["dn"],
                    {"queue_done": 0, "queue_pending": 0, "queue_error": 0},
                )
                if queue["queue_done"] == 0 and queue["queue_pending"] > 0:
                    coverage_status = "not_started"
                elif queue["queue_pending"] > 0:
                    coverage_status = "in_progress"
                elif run["status"] == "finished":
                    coverage_status = "complete"
                else:
                    coverage_status = "complete_or_drained"
                departments[row["dn"]] = {
                    **row,
                    "source": spec["id"],
                    "source_run_status": run["status"],
                    "coverage_status": coverage_status,
                    **queue,
                }

            placeholders = ",".join("?" for _ in included_dns)
            if included_dns:
                for row in rows_as_dicts(
                    connection,
                    f"SELECT * FROM org_units WHERE department_dn IN ({placeholders})",
                    sorted(included_dns),
                ):
                    if row["dn"] in orgs:
                        duplicate_org_dns_across_selected_sources += 1
                    orgs[row["dn"]] = {**row, "source": spec["id"]}
                for row in rows_as_dicts(
                    connection,
                    f"SELECT * FROM people_index WHERE department_dn IN ({placeholders})",
                    sorted(included_dns),
                ):
                    if row["source_url"] in people:
                        duplicate_person_urls_across_selected_sources += 1
                    people[row["source_url"]] = {**row, "source": spec["id"]}

            for row in rows_as_dicts(connection, "SELECT * FROM crawl_errors"):
                errors.append({**row, "source": spec["id"]})
        finally:
            connection.close()

    represented_departments = set(departments)
    catalog_departments = set(catalog)
    missing_departments = sorted(catalog_departments - represented_departments)
    unexpected_departments = sorted(represented_departments - catalog_departments)

    people_by_department: Counter[str] = Counter()
    orgs_by_department: Counter[str] = Counter()
    missing_title_by_department: Counter[str] = Counter()
    max_depth_by_department: defaultdict[str, int] = defaultdict(int)
    tech_people_by_department: Counter[str] = Counter()
    tech_orgs_by_department: Counter[str] = Counter()
    title_category_counts: Counter[str] = Counter()
    org_category_counts: Counter[str] = Counter()
    people_in_org_category_counts: Counter[str] = Counter()
    normalized_title_counts: Counter[str] = Counter()
    normalized_name_department: Counter[tuple[str, str]] = Counter()
    normalized_identity_signature: Counter[tuple[str, str, str, str]] = Counter()
    people_by_org: Counter[str] = Counter()
    org_category_membership: dict[str, list[str]] = {}

    invalid_person_urls = 0
    invalid_org_urls = 0
    orphan_people_org = 0
    orphan_people_department = 0
    orphan_org_department = 0
    orphan_org_parent = 0
    missing_titles = 0
    tech_people_union = 0
    tech_orgs_union = 0

    for org in orgs.values():
        department_dn = org["department_dn"]
        orgs_by_department[department_dn] += 1
        max_depth_by_department[department_dn] = max(
            max_depth_by_department[department_dn], org["depth"]
        )
        if not org["source_url"].startswith(GEDS_URL_PREFIX):
            invalid_org_urls += 1
        if department_dn not in departments:
            orphan_org_department += 1
        if org["parent_dn"] and org["parent_dn"] not in orgs:
            orphan_org_parent += 1
        categories = categories_for(f'{org["name"]} {org["org_path"]}')
        org_category_membership[org["dn"]] = categories
        if categories:
            tech_orgs_union += 1
            tech_orgs_by_department[department_dn] += 1
            org_category_counts.update(categories)

    for person in people.values():
        department_dn = person["department_dn"]
        people_by_department[department_dn] += 1
        people_by_org[person["org_dn"]] += 1
        normalized_name_department[
            (department_dn, normalize_text(person["display_name"]))
        ] += 1
        normalized_identity_signature[
            (
                department_dn,
                normalize_text(person["display_name"]),
                normalize_text(person["title"]),
                person["org_dn"],
            )
        ] += 1
        if not person["source_url"].startswith(GEDS_URL_PREFIX):
            invalid_person_urls += 1
        if department_dn not in departments:
            orphan_people_department += 1
        if person["org_dn"] not in orgs:
            orphan_people_org += 1
        title = person["title"]
        if not title or not title.strip():
            missing_titles += 1
            missing_title_by_department[department_dn] += 1
        else:
            normalized_title_counts[normalize_text(title)] += 1
        categories = categories_for(title)
        if categories:
            tech_people_union += 1
            tech_people_by_department[department_dn] += 1
            title_category_counts.update(categories)
        people_in_org_category_counts.update(
            org_category_membership.get(person["org_dn"], [])
        )

    collision_groups = {
        key: count
        for key, count in normalized_name_department.items()
        if key[1] and count > 1
    }
    collision_rows = sum(collision_groups.values())
    identity_collision_groups = {
        key: count
        for key, count in normalized_identity_signature.items()
        if key[1] and count > 1
    }
    identity_collision_rows = sum(identity_collision_groups.values())
    people_per_org_distribution = Counter(people_by_org.values())
    orgs_with_people = sum(people_per_org_distribution.values())
    maximum_people_per_org = max(people_per_org_distribution, default=0)
    orgs_at_observed_cap = people_per_org_distribution[maximum_people_per_org]
    people_in_capped_orgs = maximum_people_per_org * orgs_at_observed_cap
    capped_orgs_by_department: Counter[str] = Counter()
    capped_people_by_department: Counter[str] = Counter()
    for org_dn, people_count in people_by_org.items():
        if people_count != maximum_people_per_org:
            continue
        department_dn = orgs[org_dn]["department_dn"]
        capped_orgs_by_department[department_dn] += 1
        capped_people_by_department[department_dn] += people_count

    department_rows: list[dict[str, Any]] = []
    for dn, department in departments.items():
        people_count = people_by_department[dn]
        org_count = orgs_by_department[dn]
        missing_count = missing_title_by_department[dn]
        tech_people_count = tech_people_by_department[dn]
        tech_org_count = tech_orgs_by_department[dn]
        department_rows.append(
            {
                "department_dn": dn,
                "department": department["name"],
                "source": department["source"],
                "coverage_status": department["coverage_status"],
                "people": people_count,
                "org_units": org_count,
                "queue_done": department["queue_done"],
                "queue_pending": department["queue_pending"],
                "max_depth": max_depth_by_department[dn],
                "people_per_org": round(people_count / org_count, 2)
                if org_count
                else None,
                "missing_titles": missing_count,
                "missing_title_rate": round(missing_count / people_count, 6)
                if people_count
                else None,
                "tech_title_people": tech_people_count,
                "tech_title_share": round(tech_people_count / people_count, 6)
                if people_count
                else None,
                "tech_org_units": tech_org_count,
                "tech_org_share": round(tech_org_count / org_count, 6)
                if org_count
                else None,
                "orgs_at_people_cap": capped_orgs_by_department[dn],
                "people_in_capped_orgs": capped_people_by_department[dn],
                "people_in_capped_orgs_share": round(
                    capped_people_by_department[dn] / people_count, 6
                )
                if people_count
                else None,
            }
        )

    coverage_counts = Counter(row["coverage_status"] for row in department_rows)
    people_total = len(people)
    org_total = len(orgs)
    concentration_rows = sorted(
        department_rows, key=lambda row: (row["people"], row["org_units"]), reverse=True
    )
    cumulative = 0
    top_departments: list[dict[str, Any]] = []
    for rank, row in enumerate(concentration_rows[:20], 1):
        cumulative += row["people"]
        top_departments.append(
            {
                **row,
                "rank": rank,
                "people_share": round(row["people"] / people_total, 6)
                if people_total
                else 0,
                "cumulative_people_share": round(cumulative / people_total, 6)
                if people_total
                else 0,
            }
        )

    complete_density_rows = [
        row
        for row in department_rows
        if row["coverage_status"] in {"complete", "complete_or_drained"}
        and row["people"] >= 100
    ]
    top_tech_density = sorted(
        complete_density_rows,
        key=lambda row: (
            row["tech_title_share"] or 0,
            row["tech_title_people"],
        ),
        reverse=True,
    )[:20]
    top_tech_count = sorted(
        department_rows,
        key=lambda row: (row["tech_title_people"], row["people"]),
        reverse=True,
    )[:20]
    top_missing_title_departments = sorted(
        [row for row in department_rows if row["people"] >= 100],
        key=lambda row: (row["missing_titles"], row["missing_title_rate"] or 0),
        reverse=True,
    )[:20]

    top_titles = [
        {"title_normalized": title, "people": count}
        for title, count in normalized_title_counts.most_common(25)
    ]
    title_categories = [
        {
            "category": category,
            "people": title_category_counts[category],
            "share_of_people": round(title_category_counts[category] / people_total, 6)
            if people_total
            else 0,
        }
        for category in TECH_PATTERNS
    ]
    org_categories = [
        {
            "category": category,
            "org_units": org_category_counts[category],
            "share_of_org_units": round(org_category_counts[category] / org_total, 6)
            if org_total
            else 0,
            "people_assigned_to_matching_orgs": people_in_org_category_counts[
                category
            ],
            "share_of_people_assigned_to_matching_orgs": round(
                people_in_org_category_counts[category] / people_total, 6
            )
            if people_total
            else 0,
        }
        for category in TECH_PATTERNS
    ]
    top_org_units_by_category: dict[str, list[dict[str, Any]]] = {}
    for category in TECH_PATTERNS:
        matching_orgs = [
            {
                "category": category,
                "department": departments[org["department_dn"]]["name"],
                "coverage_status": departments[org["department_dn"]][
                    "coverage_status"
                ],
                "org_unit": org["name"],
                "org_path": org["org_path"],
                "people": people_by_org[org["dn"]],
                "depth": org["depth"],
            }
            for org in orgs.values()
            if category in org_category_membership[org["dn"]]
        ]
        top_org_units_by_category[category] = sorted(
            matching_orgs,
            key=lambda row: (row["people"], row["department"], row["org_path"]),
            reverse=True,
        )[:20]

    completed_or_drained_departments = sum(
        coverage_counts[key] for key in ("complete", "complete_or_drained")
    )
    ready_people = sum(
        row["people"]
        for row in department_rows
        if row["coverage_status"] in {"complete", "complete_or_drained"}
    )
    ready_orgs = sum(
        row["org_units"]
        for row in department_rows
        if row["coverage_status"] in {"complete", "complete_or_drained"}
    )

    people_shares = [
        row["people"] / people_total for row in department_rows if people_total
    ]
    department_hhi = sum(share * share for share in people_shares)

    controller_by_output = {
        row["output_dir"].replace("/", "\\"): row for row in controller_runs
    }
    for run in run_summaries:
        controller = controller_by_output.get(str(Path(run["path"]).parent))
        if controller:
            run["controller_status"] = controller["controller_status"]
            run["controller_request_count"] = controller["controller_request_count"]
            run["controller_request_count_lag"] = (
                run["request_count"] - controller["controller_request_count"]
            )

    quality_checks = [
        {
            "check": "Catalog representation",
            "value": len(represented_departments),
            "denominator": len(catalog_departments),
            "rate": round(len(represented_departments) / len(catalog_departments), 6),
            "severity": "low" if not missing_departments else "high",
        },
        {
            "check": "Departments complete or queue-drained",
            "value": completed_or_drained_departments,
            "denominator": len(catalog_departments),
            "rate": round(
                completed_or_drained_departments / len(catalog_departments), 6
            ),
            "severity": "high"
            if completed_or_drained_departments < len(catalog_departments)
            else "low",
        },
        {
            "check": "People in complete or queue-drained departments",
            "value": ready_people,
            "denominator": people_total,
            "rate": round(ready_people / people_total, 6) if people_total else 0,
            "severity": "medium" if ready_people < people_total else "low",
        },
        {
            "check": "Org units in complete or queue-drained departments",
            "value": ready_orgs,
            "denominator": org_total,
            "rate": round(ready_orgs / org_total, 6) if org_total else 0,
            "severity": "medium" if ready_orgs < org_total else "low",
        },
        {
            "check": "Missing person titles",
            "value": missing_titles,
            "denominator": people_total,
            "rate": round(missing_titles / people_total, 6) if people_total else 0,
            "severity": "medium",
        },
        {
            "check": f"Org units at observed people ceiling ({maximum_people_per_org})",
            "value": orgs_at_observed_cap,
            "denominator": orgs_with_people,
            "rate": round(orgs_at_observed_cap / orgs_with_people, 6)
            if orgs_with_people
            else 0,
            "severity": "high" if maximum_people_per_org == 25 else "medium",
        },
        {
            "check": "People with missing org parent",
            "value": orphan_people_org,
            "denominator": people_total,
            "rate": round(orphan_people_org / people_total, 6)
            if people_total
            else 0,
            "severity": "high" if orphan_people_org else "low",
        },
        {
            "check": "Org units with missing parent",
            "value": orphan_org_parent,
            "denominator": org_total,
            "rate": round(orphan_org_parent / org_total, 6) if org_total else 0,
            "severity": "high" if orphan_org_parent else "low",
        },
        {
            "check": "Invalid person source URLs",
            "value": invalid_person_urls,
            "denominator": people_total,
            "rate": round(invalid_person_urls / people_total, 6)
            if people_total
            else 0,
            "severity": "high" if invalid_person_urls else "low",
        },
        {
            "check": "Invalid org source URLs",
            "value": invalid_org_urls,
            "denominator": org_total,
            "rate": round(invalid_org_urls / org_total, 6) if org_total else 0,
            "severity": "high" if invalid_org_urls else "low",
        },
        {
            "check": "Potential same-name collisions within department",
            "value": collision_rows,
            "denominator": people_total,
            "rate": round(collision_rows / people_total, 6) if people_total else 0,
            "severity": "medium",
        },
        {
            "check": "Potential duplicate identity signatures",
            "value": identity_collision_rows,
            "denominator": people_total,
            "rate": round(identity_collision_rows / people_total, 6)
            if people_total
            else 0,
            "severity": "medium" if identity_collision_rows else "low",
        },
        {
            "check": "Duplicate person URLs across selected sources",
            "value": duplicate_person_urls_across_selected_sources,
            "denominator": people_total,
            "rate": round(
                duplicate_person_urls_across_selected_sources / people_total, 6
            )
            if people_total
            else 0,
            "severity": "high"
            if duplicate_person_urls_across_selected_sources
            else "low",
        },
        {
            "check": "Duplicate org DNs across selected sources",
            "value": duplicate_org_dns_across_selected_sources,
            "denominator": org_total,
            "rate": round(duplicate_org_dns_across_selected_sources / org_total, 6)
            if org_total
            else 0,
            "severity": "high" if duplicate_org_dns_across_selected_sources else "low",
        },
        {
            "check": "Forbidden contact columns in persisted schema",
            "value": len(forbidden_schema_columns),
            "denominator": 1,
            "rate": float(len(forbidden_schema_columns)),
            "severity": "critical" if forbidden_schema_columns else "low",
        },
    ]

    limitations = [
        "The observed per-org people count has a hard ceiling of 25, strongly indicating source-page pagination censoring; workforce and title totals are lower bounds.",
        "Keyword categories are bilingual heuristics and may include false positives or miss specialized titles.",
        "Same-name collision candidates are not confirmed duplicates.",
    ]
    if any(run["status"] != "finished" for run in run_summaries):
        limitations.insert(
            0,
            "At least one selected crawl run was still active at extraction time, so some department totals are partial.",
        )
        limitations.append(
            "A queue-drained department in a running batch is treated as operationally complete, but only a finished run proves batch-level completion."
        )

    return {
        "metadata": {
            "generated_at_utc": generated_at,
            "analysis_scope": "Aggregate analysis across selected run databases; CRTC is taken from its dedicated finished run and excluded from rest-batch.",
            "catalog_departments": len(catalog_departments),
            "represented_departments": len(represented_departments),
            "missing_department_dns": missing_departments,
            "unexpected_department_dns": unexpected_departments,
            "privacy": "Only aggregate values are emitted; person names and contact fields are excluded.",
            "limitations": limitations,
        },
        "headline": {
            "departments": len(departments),
            "complete_or_drained_departments": completed_or_drained_departments,
            "in_progress_departments": coverage_counts["in_progress"],
            "not_started_departments": coverage_counts["not_started"],
            "people": people_total,
            "org_units": org_total,
            "people_with_title": people_total - missing_titles,
            "missing_titles": missing_titles,
            "tech_title_people": tech_people_union,
            "tech_title_share": round(tech_people_union / people_total, 6)
            if people_total
            else 0,
            "tech_org_units": tech_orgs_union,
            "tech_org_share": round(tech_orgs_union / org_total, 6)
            if org_total
            else 0,
            "crawl_errors": len(errors),
            "department_people_hhi": round(department_hhi, 6),
            "same_name_collision_groups": len(collision_groups),
            "potential_duplicate_identity_groups": len(identity_collision_groups),
            "maximum_people_per_org": maximum_people_per_org,
            "orgs_at_observed_people_cap": orgs_at_observed_cap,
            "people_in_capped_orgs": people_in_capped_orgs,
            "people_in_capped_orgs_share": round(
                people_in_capped_orgs / people_total, 6
            )
            if people_total
            else 0,
        },
        "coverage_counts": [
            {"status": status, "departments": count}
            for status, count in sorted(coverage_counts.items())
        ],
        "run_summaries": run_summaries,
        "quality_checks": quality_checks,
        "title_categories": title_categories,
        "org_categories": org_categories,
        "top_org_units_by_category": top_org_units_by_category,
        "top_departments": top_departments,
        "top_tech_departments_by_count": top_tech_count,
        "top_tech_departments_by_density_complete_min_100_people": top_tech_density,
        "top_missing_title_departments": top_missing_title_departments,
        "top_titles": top_titles,
        "people_per_org_distribution": [
            {"people_per_org": people_count, "org_units": org_count}
            for people_count, org_count in sorted(people_per_org_distribution.items())
        ],
        "departments": sorted(department_rows, key=lambda row: row["department"]),
        "errors": errors,
        "forbidden_schema_columns": forbidden_schema_columns,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "analysis" / "geds_analysis_snapshot.json",
    )
    args = parser.parse_args()
    result = analyze()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(result["headline"], ensure_ascii=False, indent=2))
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
