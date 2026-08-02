from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from geds_crawler.canonical_resolver import ResolvedSnapshot
from geds_crawler.canonicalizer import promote_canonical_snapshot
from geds_crawler.career_index import build_career_index
from geds_crawler.public_projection import export_public_projection
from geds_crawler.public_projection_import import (
    PublicProjectionImportCoordinator,
    PublicProjectionError,
    build_public_projection_import_plan,
    postgres_schema_path,
)


ROOT = Path(__file__).parents[1]
TAXONOMY_PATH = ROOT / "src" / "geds_crawler" / "data" / "career_taxonomy.v1.json"


def _master(tmp_path: Path) -> Path:
    source = tmp_path / "source.sqlite"
    master = tmp_path / "master.sqlite"
    with sqlite3.connect(source) as con:
        con.executescript(
            """
            CREATE TABLE crawl_runs(request_count INTEGER,status TEXT,crawl_kind TEXT,started_at TEXT);
            CREATE TABLE departments(dn TEXT,name TEXT);
            CREATE TABLE org_units(dn TEXT,name TEXT,department_dn TEXT,depth INTEGER,org_path TEXT,source_url TEXT);
            CREATE TABLE people_index(display_name TEXT,title TEXT,department_name TEXT,org_unit TEXT,org_path TEXT,source_url TEXT,last_seen TEXT,org_dn TEXT,department_dn TEXT);
            CREATE TABLE crawl_queue(status TEXT);
            CREATE TABLE crawl_errors(id INTEGER);
            """
        )
        department = "OU=Dept,O=GC,C=CA"
        organization = f"OU=AI Centre,{department}"
        con.execute("INSERT INTO crawl_runs VALUES (0,'finished','full','2026-07-09')")
        con.execute("INSERT INTO departments VALUES (?,?)", (department, "Digital Services"))
        con.execute(
            "INSERT INTO org_units VALUES (?,?,?,?,?,?)",
            (organization, "AI Centre", department, 1, "Digital Services / AI Centre", "https://geds.example/team"),
        )
        con.execute(
            "INSERT INTO people_index VALUES (?,?,?,?,?,?,?,?,?)",
            ("Ada Lovelace", "IT02 Machine Learning Engineer", "Digital Services", "AI Centre", "", "https://geds-sage.gc.ca/en/GEDS?dn=ada", "2026-07-09", organization, department),
        )
    promote_canonical_snapshot(master, ResolvedSnapshot((source,), (), (source,)), "2026-07-09T00:00:00+00:00")
    build_career_index(master, TAXONOMY_PATH)
    return master


def test_coordinator_requires_staging_smoke_before_activation(tmp_path):
    output = tmp_path / "projection"
    export_public_projection(_master(tmp_path), output)

    class Target:
        def __init__(self):
            self.events = []

        def stage_public_projection(self, plan, source):
            self.events.append(("stage", plan.release_id))
            assert source.execute("SELECT COUNT(*) FROM people_current").fetchone()[0] == 1

        def smoke_public_projection(self, plan):
            self.events.append(("smoke", plan.release_id))

        def activate_public_projection(self, plan):
            self.events.append(("activate", plan.release_id))

    target = Target()
    coordinator = PublicProjectionImportCoordinator(target)
    plan = coordinator.stage(output)

    assert target.events == [("stage", plan.release_id), ("smoke", plan.release_id)]
    coordinator.activate(plan)
    assert target.events[-1] == ("activate", plan.release_id)
    with pytest.raises(PublicProjectionError, match="staging and smoke"):
        coordinator.activate(plan)


def test_import_plan_is_validated_and_uses_checked_in_postgres_schema(tmp_path):
    output = tmp_path / "projection"
    export_public_projection(_master(tmp_path), output)

    plan = build_public_projection_import_plan(output)

    assert plan.manifest.publishable is True
    assert "people_current" in plan.table_names
    assert postgres_schema_path().is_file()
