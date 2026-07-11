from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from geds_crawler.canonical_resolver import ResolvedSnapshot
from geds_crawler.canonicalizer import promote_canonical_snapshot
from geds_crawler.career_api import create_career_app
from geds_crawler.career_cli import main
from geds_crawler.career_index import build_career_index


ROOT = Path(__file__).parents[1]
TAXONOMY_PATH = ROOT / "src" / "geds_crawler" / "data" / "career_taxonomy.v1.json"


@pytest.fixture
def career_client(tmp_path):
    source = tmp_path / "source.sqlite"; master = tmp_path / "master.sqlite"
    con = sqlite3.connect(source)
    con.executescript("""CREATE TABLE crawl_runs(request_count INTEGER,status TEXT,crawl_kind TEXT,started_at TEXT); CREATE TABLE departments(dn TEXT,name TEXT); CREATE TABLE org_units(dn TEXT,name TEXT,department_dn TEXT,depth INTEGER,org_path TEXT,source_url TEXT); CREATE TABLE people_index(display_name TEXT,title TEXT,department_name TEXT,org_unit TEXT,org_path TEXT,source_url TEXT,last_seen TEXT,org_dn TEXT,department_dn TEXT); CREATE TABLE crawl_queue(status TEXT); CREATE TABLE crawl_errors(id INTEGER);""")
    dept = "OU=Dept,O=GC,C=CA"; org = f"OU=AI Centre,{dept}"
    con.execute("INSERT INTO crawl_runs VALUES (0,'finished','full','2026-07-09')"); con.execute("INSERT INTO departments VALUES (?,?)", (dept,"Digital Services")); con.execute("INSERT INTO org_units VALUES (?,?,?,?,?,?)", (org,"AI Centre",dept,1,"Digital Services / AI Centre","org")); con.executemany("INSERT INTO people_index VALUES (?,?,?,?,?,?,?,?,?)", [("Ada","Machine Learning Engineer","Digital Services","AI Centre","","ada","2026-07-09",org,dept), ("VACANT, VACANT","Data Scientist","Digital Services","AI Centre","","vacant","2026-07-09",org,dept)]); con.commit(); con.close()
    promote_canonical_snapshot(master, ResolvedSnapshot((source,), (), (source,)), "2026-07-09T00:00:00+00:00")
    build_career_index(master, TAXONOMY_PATH)
    return TestClient(create_career_app(master))


def test_meta_and_search_contract(career_client):
    meta = career_client.get("/api/meta")
    assert meta.status_code == 200
    assert meta.json()["snapshot_id"]
    search = career_client.get("/api/search", params={"q": "AI", "limit": 20})
    assert search.status_code == 200
    assert search.json()["items"][0]["evidence"]
    assert search.headers["etag"]


def test_org_root_and_child_contract(career_client):
    roots = career_client.get("/api/orgs/root/children", params={"limit": 200})
    assert roots.status_code == 200
    assert roots.json()["items"]
    assert roots.headers["etag"]

    children = career_client.get(f"/api/orgs/{roots.json()['items'][0]['org_id']}/children")
    assert children.status_code == 200


@pytest.mark.parametrize("path", ["/api/crawlers", "/api/jobs", "/api/schedules"])
def test_public_app_has_no_control_routes(career_client, path):
    assert career_client.get(path).status_code == 404
    assert career_client.post(path).status_code in {404, 405}


def test_security_headers_and_bounded_input(career_client):
    response = career_client.get("/api/constellation", params={"q": "AI", "limit": 10000})
    assert response.status_code == 200
    assert response.json()["limit"] == 2000
    assert "default-src 'self'" in response.headers["content-security-policy"]
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert "access-control-allow-origin" not in response.headers


@pytest.mark.parametrize("path", ["/api/meta", "/api/search?q=AI", "/api/orgs/root/children", "/api/tours"])
def test_public_api_surface_is_get_only(career_client, path):
    assert career_client.post(path).status_code == 405
    assert career_client.put(path).status_code == 405
    assert career_client.delete(path).status_code == 405


@pytest.mark.parametrize(
    ("path", "params"),
    [
        ("/api/search", {"q": "AI", "limit": 0}),
        ("/api/search", {"q": "AI", "limit": 201}),
        ("/api/constellation/slice", {"max_depth": 0}),
        ("/api/constellation/slice", {"max_depth": 13}),
        ("/api/constellation/slice", {"limit": 2001}),
    ],
)
def test_public_parameters_are_rejected_outside_documented_bounds(career_client, path, params):
    assert career_client.get(path, params=params).status_code == 422


@pytest.mark.parametrize("query", ["' OR 1=1 --", '" ) UNION SELECT * FROM people_current --', "AI* NEAR/1 data"])
def test_search_treats_query_syntax_as_untrusted_text(career_client, query):
    response = career_client.get("/api/search", params={"q": query})
    assert response.status_code == 200
    assert isinstance(response.json()["items"], list)


def test_public_profile_never_exposes_contacts_or_person_names(career_client):
    root = career_client.get("/api/orgs/root/children").json()["items"][0]
    profile = career_client.get(f"/api/orgs/{root['org_id']}/profile")
    serialized = str(profile.json()).lower()

    assert profile.status_code == 200
    assert not {"email", "phone", "fax", "address", "display_name"} & set(profile.json())
    assert "machine learning engineer" not in serialized


@pytest.mark.parametrize("path", ["/../pyproject.toml", "/api/../pyproject.toml", "/%2e%2e/pyproject.toml"])
def test_path_traversal_is_rejected(career_client, path):
    assert career_client.get(path).status_code in {404, 405}


def test_constellation_slice_contract(career_client):
    response = career_client.get("/api/constellation/slice", params={"max_depth": 1, "limit": 2000})
    assert response.status_code == 200
    assert response.json()["nodes"]
    assert response.json()["truncated"] is False


def test_vacancy_discovery_is_bounded_and_explicitly_unverified(career_client):
    response = career_client.get("/api/vacancy-signals", params={"limit": 5000})

    assert response.status_code == 200
    assert response.json()["limit"] == 200
    assert response.json()["items"] == [
        {
            "marker": "VACANT, VACANT",
            "title": "Data Scientist",
            "org_id": response.json()["items"][0]["org_id"],
            "organization_name": "AI Centre",
            "observed_at": "2026-07-09",
            "source_url": "vacant",
            "confidence": "high",
            "reasons": ["placeholder_marker:vacant"],
            "live_competition_verified": False,
        }
    ]
    assert "apply" not in str(response.json()).lower()
    assert not {"email", "phone", "display_name"} & set(response.json()["items"][0])


def test_serve_refuses_a_missing_master(tmp_path, capsys):
    assert main(["serve", "--master-db", str(tmp_path / "missing.sqlite")]) == 2
    assert "does not exist" in capsys.readouterr().err
