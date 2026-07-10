from __future__ import annotations

import sqlite3
import json
from pathlib import Path

import pytest

from geds_crawler.canonical_resolver import ResolvedSnapshot
from geds_crawler.canonicalizer import promote_canonical_snapshot
from geds_crawler.career_cli import main
from geds_crawler.career_index import (
    build_career_index,
    current_index_state,
    parse_vacancy_signal,
)


ROOT = Path(__file__).parents[1]
TAXONOMY_PATH = ROOT / "src" / "geds_crawler" / "data" / "career_taxonomy.v1.json"


def _source_db(path: Path) -> None:
    department_dn = "OU=Dept,O=GC,C=CA"
    org_dn = f"OU=Team,{department_dn}"
    con = sqlite3.connect(path)
    con.executescript(
        """
        CREATE TABLE crawl_runs(request_count INTEGER,status TEXT,crawl_kind TEXT,started_at TEXT);
        CREATE TABLE departments(dn TEXT,name TEXT);
        CREATE TABLE org_units(dn TEXT,name TEXT,department_dn TEXT,depth INTEGER,org_path TEXT,source_url TEXT);
        CREATE TABLE people_index(display_name TEXT,title TEXT,department_name TEXT,org_unit TEXT,org_path TEXT,source_url TEXT,last_seen TEXT,org_dn TEXT,department_dn TEXT);
        CREATE TABLE crawl_queue(status TEXT); CREATE TABLE crawl_errors(id INTEGER);
        """
    )
    con.execute("INSERT INTO crawl_runs VALUES (0, 'finished', 'full', '2026-07-09')")
    con.execute("INSERT INTO departments VALUES (?, ?)", (department_dn, "Digital Services"))
    con.execute(
        "INSERT INTO org_units VALUES (?, ?, ?, ?, ?, ?)",
        (org_dn, "Cybersecurity Office", department_dn, 1, "Digital Services / Cybersecurity Office", "org"),
    )
    con.executemany(
        "INSERT INTO people_index VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            ("Ada Lovelace", "Cybersecurity Analyst", "Digital Services", "Cybersecurity Office", "", "ada", "", org_dn, department_dn),
            ("VACANT, VACANT", "Analyst", "Digital Services", "Cybersecurity Office", "", "vacant", "", org_dn, department_dn),
        ],
    )
    con.commit()
    con.close()


@pytest.fixture
def canonical_master(tmp_path):
    source = tmp_path / "source.sqlite"
    master = tmp_path / "master.sqlite"
    _source_db(source)
    promote_canonical_snapshot(
        master,
        ResolvedSnapshot((source,), (), (source,)),
        "2026-07-09T00:00:00+00:00",
    )
    return master


def test_index_is_bound_to_current_snapshot(canonical_master):
    report = build_career_index(canonical_master, TAXONOMY_PATH)
    state = current_index_state(canonical_master)

    assert report.snapshot_id == state["snapshot_id"]
    assert report.organization_count == 1
    assert report.people_count == 2
    assert report.entity_count == 3
    assert report.taxonomy_version == "1.0.0"
    assert report.vacancy_signal_count == 1


def test_rebuild_replaces_the_same_snapshot_index(canonical_master):
    first = build_career_index(canonical_master, TAXONOMY_PATH)
    second = build_career_index(canonical_master, TAXONOMY_PATH)

    assert first.snapshot_id == second.snapshot_id
    with sqlite3.connect(canonical_master) as con:
        assert con.execute("SELECT COUNT(*) FROM career_entities").fetchone()[0] == 3
        assert con.execute("SELECT COUNT(*) FROM career_entities_fts").fetchone()[0] == 3
        assert con.execute("SELECT COUNT(*) FROM career_matches").fetchone()[0] >= 1


def test_failed_build_preserves_previous_index_state(canonical_master, tmp_path):
    build_career_index(canonical_master, TAXONOMY_PATH)
    before = current_index_state(canonical_master)

    with pytest.raises(ValueError, match="invalid taxonomy file"):
        build_career_index(canonical_master, tmp_path / "missing.json")

    assert current_index_state(canonical_master) == before


@pytest.mark.parametrize(
    ("name", "confidence"),
    [
        ("VACANT, VACANT", "high"),
        ("Vacant, Inocuppé", "high"),
        ("Position, Vacant", "high"),
        ("Vacancy Planning Officer", "none"),
    ],
)
def test_vacancy_requires_placeholder_shaped_name(name, confidence):
    assert parse_vacancy_signal(name, "Analyst").confidence == confidence


def test_vacancy_table_has_no_contact_or_application_columns(canonical_master):
    build_career_index(canonical_master, TAXONOMY_PATH)

    with sqlite3.connect(canonical_master) as con:
        columns = {row[1] for row in con.execute("PRAGMA table_info(vacancy_signals)")}
    assert not {"email", "phone", "fax", "address", "application_url", "application_status"} & columns


def test_index_cli_prints_the_current_manifest(canonical_master, capsys):
    code = main(
        [
            "index",
            "--master-db",
            str(canonical_master),
            "--taxonomy",
            str(TAXONOMY_PATH),
        ]
    )

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["entity_count"] == 3
    assert payload["vacancy_signal_count"] == 1
