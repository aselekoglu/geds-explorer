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
    con.execute("INSERT INTO crawl_runs VALUES (0,'finished','full','2026-07-09')"); con.execute("INSERT INTO departments VALUES (?,?)", (dept,"Digital Services")); con.execute("INSERT INTO org_units VALUES (?,?,?,?,?,?)", (org,"AI Centre",dept,1,"Digital Services / AI Centre","org")); con.execute("INSERT INTO people_index VALUES (?,?,?,?,?,?,?,?,?)", ("Ada","Machine Learning Engineer","Digital Services","AI Centre","","ada","",org,dept)); con.commit(); con.close()
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


def test_serve_refuses_a_missing_master(tmp_path, capsys):
    assert main(["serve", "--master-db", str(tmp_path / "missing.sqlite")]) == 2
    assert "does not exist" in capsys.readouterr().err
