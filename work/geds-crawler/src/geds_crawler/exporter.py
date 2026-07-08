from __future__ import annotations

import json
import re
import sqlite3
from collections import Counter
from pathlib import Path


WORD_RE = re.compile(r"[A-Za-z][A-Za-z-]{2,}")
STOPWORDS = {
    "and",
    "the",
    "for",
    "with",
    "services",
    "canada",
    "canadian",
    "branch",
    "directorate",
    "division",
    "office",
}


def export_jsonl(db_path: Path, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row

    _write_rows(output_dir / "org_units.jsonl", con.execute("SELECT * FROM org_units ORDER BY org_path"))
    _write_rows(output_dir / "people_index.jsonl", con.execute("SELECT * FROM people_index ORDER BY department_name, org_path, display_name"))


def write_report(db_path: Path, output_dir: Path, runtime_seconds: float, request_count: int) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row

    department_count = _scalar(con, "SELECT COUNT(*) FROM departments")
    org_count = _scalar(con, "SELECT COUNT(*) FROM org_units")
    person_count = _scalar(con, "SELECT COUNT(*) FROM people_index")
    error_count = _scalar(con, "SELECT COUNT(*) FROM crawl_errors")
    title_keywords = _top_keywords(row["title"] for row in con.execute("SELECT title FROM people_index WHERE title IS NOT NULL"))
    org_keywords = _top_keywords(row["org_path"] for row in con.execute("SELECT org_path FROM org_units"))

    lines = [
        "# GEDS Crawl Report",
        "",
        f"- Runtime seconds: {runtime_seconds:.1f}",
        f"- Request count: {request_count}",
        f"- Departments: {department_count}",
        f"- Org units: {org_count}",
        f"- People index rows: {person_count}",
        f"- Crawl errors: {error_count}",
        "",
        "## Top Title Keywords",
        "",
        *[f"- {word}: {count}" for word, count in title_keywords],
        "",
        "## Top Org Path Keywords",
        "",
        *[f"- {word}: {count}" for word, count in org_keywords],
    ]
    (output_dir / "crawl_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_rows(path: Path, rows) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(dict(row), ensure_ascii=False) + "\n")


def _scalar(con: sqlite3.Connection, sql: str) -> int:
    return int(con.execute(sql).fetchone()[0])


def _top_keywords(values, limit: int = 20) -> list[tuple[str, int]]:
    counter: Counter[str] = Counter()
    for value in values:
        for word in WORD_RE.findall(value or ""):
            normalized = word.casefold()
            if normalized not in STOPWORDS:
                counter[normalized] += 1
    return counter.most_common(limit)
