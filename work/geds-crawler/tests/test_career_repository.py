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
    con.executemany(
        "INSERT INTO people_index VALUES (?,?,?,?,?,?,?,?,?)",
        [
            ("Ada", "Machine Learning Engineer", "Digital Services", "AI Centre", "", "https://geds.example/ada", "2026-07-09", org, dept),
            ("Morgan", "Manager, Data Platforms", "Digital Services", "AI Centre", "", "https://geds.example/morgan", "2026-07-09", org, dept),
            ("VACANT, VACANT", "Data Scientist", "Digital Services", "AI Centre", "", "https://geds.example/vacant", "2026-07-09", org, dept),
        ],
    )
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


def test_team_profile_exposes_non_claiming_leads_and_unverified_vacancy_signals(repository):
    org_id = repository.children(parent_id=None, limit=20).items[0].org_id

    profile = dataclasses.asdict(repository.team_profile(org_id))

    assert profile["conversation_leads"][0]["title"] == "Manager, Data Platforms"
    assert profile["conversation_leads"][0]["kind"] == "possible_team_lead"
    assert profile["conversation_leads"][0]["source_url"] == "https://geds.example/morgan"
    assert profile["vacancy_signals"] == (
        {
            "marker": "VACANT, VACANT",
            "title": "Data Scientist",
            "org_id": org_id,
            "observed_at": "2026-07-09",
            "source_url": "https://geds.example/vacant",
            "confidence": "high",
            "reasons": ("placeholder_marker:vacant",),
            "live_competition_verified": False,
        },
    )
    assert "display_name" not in str(profile["conversation_leads"])
    assert all(signal["live_competition_verified"] is False for signal in profile["vacancy_signals"])


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


def test_editorial_tours_are_bilingual_and_never_retarget_missing_stops(repository):
    result = repository.tours()

    assert {tour["id"] for tour in result.items} == {"ai", "software", "cybersecurity", "policy", "data"}
    assert all(tour["title"]["en"] and tour["title"]["fr"] for tour in result.items)
    assert all(tour["categories"] and tour["stops"] for tour in result.items)
    assert all("org_id" in stop and "available" in stop for tour in result.items for stop in tour["stops"])
    assert all(stop["available"] is False for tour in result.items for stop in tour["stops"])
