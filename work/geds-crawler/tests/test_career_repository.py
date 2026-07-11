from __future__ import annotations

import dataclasses
import sqlite3
from pathlib import Path

import pytest

from geds_crawler.canonical_resolver import ResolvedSnapshot
from geds_crawler.canonicalizer import promote_canonical_snapshot
from geds_crawler.career_index import build_career_index
from geds_crawler.career_repository import CareerRepository


ROOT = Path(__file__).parents[1]
TAXONOMY_PATH = ROOT / "src" / "geds_crawler" / "data" / "career_taxonomy.v1.json"


@pytest.fixture
def repository(tmp_path):
    source = tmp_path / "source.sqlite"
    master = tmp_path / "master.sqlite"
    con = sqlite3.connect(source)
    con.executescript("""
      CREATE TABLE crawl_runs(request_count INTEGER,status TEXT,crawl_kind TEXT,started_at TEXT);
      CREATE TABLE departments(dn TEXT,name TEXT); CREATE TABLE org_units(dn TEXT,name TEXT,department_dn TEXT,depth INTEGER,org_path TEXT,source_url TEXT);
      CREATE TABLE people_index(display_name TEXT,title TEXT,department_name TEXT,org_unit TEXT,org_path TEXT,source_url TEXT,last_seen TEXT,org_dn TEXT,department_dn TEXT);
      CREATE TABLE crawl_queue(status TEXT); CREATE TABLE crawl_errors(id INTEGER);
    """)
    dept = "OU=Dept,O=GC,C=CA"; org = f"OU=AI Centre,{dept}"
    con.execute("INSERT INTO crawl_runs VALUES (0,'finished','full','2026-07-09')")
    con.execute("INSERT INTO departments VALUES (?,?)", (dept, "Digital Services"))
    con.execute("INSERT INTO org_units VALUES (?,?,?,?,?,?)", (org, "AI Centre", dept, 1, "Digital Services / AI Centre", "org"))
    con.execute("INSERT INTO people_index VALUES (?,?,?,?,?,?,?,?,?)", ("Ada", "Machine Learning Engineer", "Digital Services", "AI Centre", "", "ada", "", org, dept))
    con.commit(); con.close()
    promote_canonical_snapshot(master, ResolvedSnapshot((source,), (), (source,)), "2026-07-09T00:00:00+00:00")
    build_career_index(master, TAXONOMY_PATH)
    return CareerRepository(master)


def test_search_returns_explainable_ranked_results(repository):
    result = repository.search(query="AI", limit=20)
    assert result.items
    assert result.items[0].evidence
    assert result.items[0].confidence in {"high", "medium", "exploratory"}
    assert result.limit == 20
    assert result.snapshot_id
    assert result.etag


def test_children_caps_unbounded_limit(repository):
    assert repository.children(parent_id=None, limit=10000).limit == 200


def test_team_profile_has_no_contact_fields(repository):
    org_id = repository.children(parent_id=None, limit=20).items[0].org_id
    payload = dataclasses.asdict(repository.team_profile(org_id))
    assert not {"email", "phone", "fax", "address"} & set(payload)


def test_repository_connection_is_query_only(repository):
    with repository.connect() as con:
        with pytest.raises(sqlite3.OperationalError):
            con.execute("DELETE FROM career_entities")


def test_navigation_queries_are_snapshot_bound_and_capped(repository):
    departments = repository.departments()
    root = repository.children(parent_id=None, limit=20).items[0]
    ancestors = repository.ancestors(root.org_id)
    roles = repository.roles(org_id=root.org_id, limit=10000)
    constellation = repository.constellation(query="AI", limit=10000)

    assert departments.items and departments.snapshot_id
    assert ancestors.snapshot_id == departments.snapshot_id
    assert roles.limit == 200
    assert constellation.limit == 2000
    assert constellation.items


def test_root_constellation_returns_only_root_organizations(repository):
    result = repository.constellation_slice(root_id=None, max_depth=1, limit=2000)

    assert result.nodes
    assert all(node.parent_id is None for node in result.nodes)
    assert result.truncated is False
    assert result.limit == 2000


def test_tours_are_deterministic_and_have_no_personal_data(repository):
    first = repository.tours()
    second = repository.tours()

    assert first == second
    assert first.snapshot_id
    assert all("email" not in str(tour).lower() for tour in first.items)
