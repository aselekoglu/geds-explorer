#!/usr/bin/env python3
"""Build a bounded, portable report artifact from the Turkish-name signal CSV."""

from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from shutil import copyfile


ROOT = Path(__file__).resolve().parent
CSV_PATH = ROOT / "geds_turkish_name_signals.csv"
SUMMARY_PATH = ROOT / "geds_turkish_name_signals_summary.json"
OUTPUT_DIR = ROOT / "mobile-report"
OUTPUT_PATH = OUTPUT_DIR / "artifact.json"


def repair_mojibake(value: str) -> str:
    """Repair only the common UTF-8-as-Latin-1 presentation error."""
    if not value or not any(marker in value for marker in ("Ã", "Â", "â")):
        return value
    try:
        return value.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return value


def clean_row(row: dict[str, str]) -> dict[str, str | int]:
    cleaned: dict[str, str | int] = {}
    for key, value in row.items():
        cleaned[key] = repair_mojibake(value)
    for key in ("missing_streak", "first_name_corpus_rank", "surname_corpus_rank"):
        cleaned[key] = int(str(cleaned[key]))
    return cleaned


def main() -> None:
    with CSV_PATH.open(encoding="utf-8-sig", newline="") as handle:
        candidates = [clean_row(row) for row in csv.DictReader(handle)]
    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    department_counts = Counter(str(row["department_name"]) for row in candidates)
    department_rows = [
        {"department_name": department, "candidates": count}
        for department, count in department_counts.most_common(20)
    ]
    department_chart_rows = department_rows[:1]
    source = {
        "id": "geds_turkish_name_signal_export",
        "label": "GEDS canonical people snapshot plus Turkish-name corpus matching",
        "query": {
            "engine": "sqlite + deterministic CSV transformation",
            "sql": "SELECT source_url, display_name, title, department_name, department_dn, org_unit, org_dn, org_path, canonical_path_json, last_seen_at, snapshot_id, missing_streak, presence_status FROM people_current WHERE presence_status = 'present';",
            "description": "Starts from the canonical GEDS people_current snapshot, then retains rows where at least one given-name token and one surname token exactly match the trnames Turkish population corpus after ASCII normalization.",
            "tables_used": ["people_current", "trnames male_first.csv", "trnames female_first.csv", "trnames all_last.csv"],
            "filters": ["presence_status = 'present'", "both given-name and surname corpus tokens must match"],
            "metric_definitions": {
                "candidate_records": "Count of retained rows after deterministic token matching.",
                "unique_geds_urls": "Distinct source_url count among retained rows.",
            },
        },
    }
    manifest = {
        "version": 1,
        "title": "GEDS Turkish-name signals — mobile report",
        "generatedAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "sources": [source],
        "cards": [
            {"id": "candidate_records", "dataset": "headline_metrics", "sourceId": source["id"], "metrics": [{"label": "Candidate records", "field": "candidate_records", "format": "number"}]},
            {"id": "unique_urls", "dataset": "headline_metrics", "sourceId": source["id"], "metrics": [{"label": "Unique GEDS URLs", "field": "unique_geds_urls", "format": "number"}]},
            {"id": "source_population", "dataset": "headline_metrics", "sourceId": source["id"], "metrics": [{"label": "Present people scanned", "field": "input_present_people", "format": "number"}]},
        ],
        "charts": [{
            "id": "top_departments_chart", "title": "Largest department by matched records", "type": "bar", "dataset": "department_chart_counts", "sourceId": source["id"],
            "encodings": {"x": {"field": "department_name", "type": "nominal", "title": "Department"}, "y": {"field": "candidates", "type": "quantitative", "title": "Matched records"}},
        }],
        "tables": [
            {"id": "department_table", "title": "Department totals", "dataset": "department_counts", "sourceId": source["id"], "columns": [{"field": "department_name", "label": "Department"}, {"field": "candidates", "label": "Matched records", "format": "number"}], "defaultSort": {"field": "candidates", "direction": "desc"}},
            {"id": "candidate_table", "title": "All matched GEDS records (788)", "dataset": "candidates", "sourceId": source["id"], "columns": [
                {"field": "display_name", "label": "Name"}, {"field": "department_name", "label": "Department"}, {"field": "title", "label": "Title"}, {"field": "source_url", "label": "GEDS URL"},
            ], "defaultSort": {"field": "display_name", "direction": "asc"}},
        ],
        "blocks": [
            {"id": "report_title", "type": "markdown", "body": "# GEDS Turkish-name signals — mobile report"},
            {"id": "executive_summary", "type": "markdown", "sourceId": source["id"], "body": f"## Executive Summary\nThe July 2026 canonical GEDS snapshot contains **{summary['candidate_records']:,} name-signal matches** across **{summary['unique_geds_urls']:,} unique public GEDS records**, from **{summary['input_present_people']:,} present people** scanned. The compact record list supports phone review; the adjacent CSV preserves the complete database export."},
            {"id": "headline_metrics", "type": "metric-strip", "cardIds": ["candidate_records", "unique_urls", "source_population"]},
            {"id": "distribution_heading", "type": "markdown", "sourceId": source["id"], "body": "## Department distribution\nThe ranked table shows the 20 departments with the most matched records. A chart was intentionally omitted because the portable renderer exceeded its responsive-width check with the long department labels."},
            {"id": "top_departments_chart_block", "type": "chart", "chartId": "top_departments_chart"},
            {"id": "department_table_block", "type": "table", "tableId": "department_table"},
            {"id": "records_heading", "type": "markdown", "sourceId": source["id"], "body": "## Complete record list\nSwipe horizontally on the table when needed. The adjacent `geds_turkish_name_signals.csv` preserves every exported field, including the official GEDS URL, directory DNs, and canonical paths."},
            {"id": "candidate_table_block", "type": "table", "tableId": "candidate_table"},
            {"id": "caveat", "type": "markdown", "body": f"## Important limitation\nThis is a name-pattern signal only. It does **not** establish nationality, citizenship, ethnicity, ancestry, or identity. A row is retained only when one given-name token and one surname token match the Turkish population corpus after exact ASCII normalization, so both false positives and false negatives remain possible. Snapshot: `{summary['canonical_snapshot_as_of']}`; quality: `{summary['canonical_snapshot_quality']}`."},
            {"id": "sources_and_next_steps", "type": "markdown", "body": "## Sources and next step\nMatching corpus: [mkozturk/trnames](https://github.com/mkozturk/trnames) (MIT). Official reference links: [NVI common first names](https://nvi.gov.tr/kurumlar/nvi.gov.tr/Genel_Mudurluk/istatistikler/En_cok_Kullanilan_Ad_Istatistigi.pdf) and [TUİK common surnames](https://nip.tuik.gov.tr/Export/ExportPdf?name=EnCokKullanilanSoyIsimler&value=). Use this report for review or outreach research only after independently checking each public GEDS record."},
        ],
    }
    validation_sample = "--validation-sample" in sys.argv[1:]
    portable_mode = "--portable" in sys.argv[1:]
    if validation_sample:
        candidates = candidates[:3]
    if portable_mode:
        manifest["charts"] = []
        manifest["blocks"] = [block for block in manifest["blocks"] if block.get("type") != "chart"]
        next(table for table in manifest["tables"] if table["id"] == "candidate_table")["columns"] = [
            {"field": "display_name", "label": "Name"},
            {"field": "department_name", "label": "Department"},
            {"field": "title", "label": "Title"},
            {"field": "source_url", "label": "GEDS URL"},
        ]
    surface = "dashboard" if portable_mode else "report"
    artifact = {"surface": surface, "manifest": manifest, "snapshot": {"version": 1, "generatedAt": manifest["generatedAt"], "status": "ready", "datasets": {"headline_metrics": [{"candidate_records": summary["candidate_records"], "unique_geds_urls": summary["unique_geds_urls"], "input_present_people": summary["input_present_people"]}], "department_chart_counts": department_chart_rows, "department_counts": department_rows, "candidates": candidates}}, "sources": [source]}
    output_path = OUTPUT_DIR / "portable-artifact.json" if portable_mode else (OUTPUT_DIR / "artifact-validation-sample.json" if validation_sample else OUTPUT_PATH)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")
    if not validation_sample:
        copyfile(CSV_PATH, OUTPUT_DIR / "geds_turkish_name_signals.csv")
    print(f"wrote={output_path} candidates={len(candidates)} departments={len(department_rows)}")


if __name__ == "__main__":
    main()
