from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from geds_crawler.canonical_resolver import ResolvedSnapshot
from geds_crawler.canonicalizer import promote_canonical_snapshot
from geds_crawler.career_cli import main
from geds_crawler.career_api import create_career_app
from geds_crawler.career_index import build_career_index
from geds_crawler.career_repository import CareerRepository
from geds_crawler.public_projection import (
    PublicProjectionError,
    export_public_projection,
    validate_public_projection,
)


ROOT = Path(__file__).parents[1]
TAXONOMY_PATH = ROOT / "src" / "geds_crawler" / "data" / "career_taxonomy.v1.json"


def _master(tmp_path: Path, *, quality_status: str = "complete") -> Path:
    source = tmp_path / "source.sqlite"
    master = tmp_path / "master.sqlite"
    con = sqlite3.connect(source)
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
    con.commit()
    con.close()
    promote_canonical_snapshot(master, ResolvedSnapshot((source,), (), (source,)), "2026-07-09T00:00:00+00:00")
    build_career_index(master, TAXONOMY_PATH)
    if quality_status != "complete":
        with sqlite3.connect(master) as con:
            con.execute("UPDATE canonical_snapshots SET quality_status=? WHERE snapshot_id=(SELECT snapshot_id FROM career_index_state WHERE singleton=1)", (quality_status,))
            con.commit()
    return master


def test_export_manifest_privacy_counts_hash_and_local_adapter(tmp_path):
    master = _master(tmp_path)
    output = tmp_path / "projection"

    manifest = export_public_projection(master, output)

    assert manifest.publishable is True
    assert manifest.release_kind == "public"
    assert manifest.counts == {"departments": 1, "organizations": 1, "people": 1, "career_entities": 2}
    assert validate_public_projection(output) == manifest
    with sqlite3.connect(output / "geds-public.sqlite") as con:
        tables = {row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        people_columns = {row[1] for row in con.execute("PRAGMA table_info(people_current)")}
    assert "crawl_runs" not in tables
    assert {"display_name", "title"} <= people_columns
    assert "last_seen_at" not in people_columns
    assert "email" not in people_columns

    repository = CareerRepository(output / "geds-public.sqlite")
    org_id = repository.children(parent_id=None).items[0].org_id
    assert repository.people(org_id=org_id).items[0].display_name == "Ada Lovelace"
    assert repository.meta()["projection_version"] == "public-projection.v1"


def test_partial_export_requires_explicit_labelled_preview(tmp_path):
    master = _master(tmp_path, quality_status="partial_overlay")

    with pytest.raises(PublicProjectionError, match="complete snapshot"):
        export_public_projection(master, tmp_path / "rejected")

    output = tmp_path / "preview"
    manifest = export_public_projection(master, output, allow_partial_preview=True)

    assert manifest.release_kind == "preview"
    assert manifest.publishable is False
    with pytest.raises(PublicProjectionError, match="explicit preview"):
        validate_public_projection(output)
    assert validate_public_projection(output, allow_partial_preview=True) == manifest


def test_validator_rejects_private_columns_and_hash_tampering(tmp_path):
    master = _master(tmp_path)
    output = tmp_path / "projection"
    export_public_projection(master, output)

    with sqlite3.connect(output / "geds-public.sqlite") as con:
        con.execute("ALTER TABLE people_current ADD COLUMN email TEXT")
        con.commit()
    with pytest.raises(PublicProjectionError, match="column allow-list"):
        validate_public_projection(output)

    output = tmp_path / "projection-hash"
    export_public_projection(master, output)
    with sqlite3.connect(output / "geds-public.sqlite") as con:
        con.execute("UPDATE people_current SET display_name='Tampered'")
        con.commit()
    with pytest.raises(PublicProjectionError, match="hash mismatch"):
        validate_public_projection(output)


def test_api_accepts_a_read_store_object(tmp_path):
    master = _master(tmp_path)
    repository = CareerRepository(master)
    client = TestClient(create_career_app(repository))
    response = client.get("/api/meta")
    assert response.status_code == 200
    assert response.json()["snapshot_id"] == repository.meta()["snapshot_id"]


def test_cli_export_and_validate_return_manifest_json(tmp_path, capsys):
    master = _master(tmp_path)
    output = tmp_path / "projection"
    assert main(["export", "--master-db", str(master), "--output-dir", str(output)]) == 0
    exported = json.loads(capsys.readouterr().out)
    assert exported["projection_version"] == "public-projection.v1"
    assert main(["validate", "--projection-dir", str(output)]) == 0
    validated = json.loads(capsys.readouterr().out)
    assert validated["data_sha256"] == exported["data_sha256"]
