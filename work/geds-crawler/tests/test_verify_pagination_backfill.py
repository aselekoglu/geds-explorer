from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
import pytest
import sqlite3

from geds_crawler.store import SnapshotStore
from geds_crawler.models import OrgUnit, PersonIndex

@pytest.fixture
def base_and_overlay_dbs(tmp_path):
    base_db = tmp_path / "base.sqlite"
    overlay_db = tmp_path / "overlay.sqlite"

    # Setup base DB
    with SnapshotStore(base_db) as store:
        store.init_schema()
        store.db.execute(
            "INSERT INTO crawl_runs (id, started_at, request_count, status) VALUES ('run-base', '2026-07-08T12:00:00+00:00', 10, 'finished')"
        )
        store.db.execute(
            "INSERT INTO departments (dn, name, source_url, first_seen, last_seen, crawl_run_id) VALUES ('OU=DEPT,O=GC,C=CA', 'Dept', 'url', 'now', 'now', 'run-base')"
        )
        org1 = OrgUnit("Org1", "OU=ORG1,OU=DEPT,O=GC,C=CA", None, "OU=DEPT,O=GC,C=CA", 1, "Dept / Org1", "url-org1")
        org2 = OrgUnit("Org2", "OU=ORG2,OU=DEPT,O=GC,C=CA", None, "OU=DEPT,O=GC,C=CA", 1, "Dept / Org2", "url-org2")
        store.upsert_org_unit(org1, "run-base", "now")
        store.upsert_org_unit(org2, "run-base", "now")
        # Put 25 people in Org1
        for i in range(25):
            person = PersonIndex(f"P {i}", "Title", org1.dn, org1.department_dn, "Dept", org1.name, org1.org_path, f"url-person-1-{i}")
            store.upsert_person(person, "run-base", "now")
        # Put 25 people in Org2
        for i in range(25):
            person = PersonIndex(f"Q {i}", "Title", org2.dn, org2.department_dn, "Dept", org2.name, org2.org_path, f"url-person-2-{i}")
            store.upsert_person(person, "run-base", "now")
        store.commit()

    # Setup overlay DB (backfill progress)
    with SnapshotStore(overlay_db) as store:
        store.init_schema()
        store.db.execute(
            "INSERT INTO crawl_runs (id, started_at, request_count, status) VALUES ('run-backfill', '2026-07-09T12:00:00+00:00', 5, 'finished')"
        )
        # Create pagination_orgs
        store.db.execute(
            """
            INSERT INTO pagination_orgs (
                org_dn, department_dn, department_name, org_name, org_path, source_url, base_db_path, base_people_count,
                pages_fetched, status, last_error, terminal_reason
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("OU=ORG1,OU=DEPT,O=GC,C=CA", "OU=DEPT,O=GC,C=CA", "Dept", "Org1", "Dept / Org1", "url-org1", "base.sqlite", 25, 2, "finished", None, None)
        )
        store.db.execute(
            """
            INSERT INTO pagination_orgs (
                org_dn, department_dn, department_name, org_name, org_path, source_url, base_db_path, base_people_count,
                pages_fetched, status, last_error, terminal_reason
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("OU=ORG2,OU=DEPT,O=GC,C=CA", "OU=DEPT,O=GC,C=CA", "Dept", "Org2", "Dept / Org2", "url-org2", "base.sqlite", 25, 1, "finished", None, None)
        )
        # Put new crawled people in Org1 (making it exceed 25!)
        for i in range(25, 30):
            person = PersonIndex(f"P {i}", "Title", "OU=ORG1,OU=DEPT,O=GC,C=CA", "OU=DEPT,O=GC,C=CA", "Dept", "Org1", "Dept / Org1", f"url-person-1-{i}")
            store.upsert_person(person, "run-backfill", "now")
        store.commit()

    return base_db, overlay_db


def test_verifier_script_success(base_and_overlay_dbs):
    base_db, overlay_db = base_and_overlay_dbs
    script_path = Path(__file__).parent.parent / "scripts" / "verify_pagination_backfill.py"

    cmd = [
        sys.executable,
        str(script_path),
        "--base-db",
        str(base_db),
        "--overlay-db",
        str(overlay_db),
        "--expected-org-dn",
        "OU=ORG1,OU=DEPT,O=GC,C=CA",
        "--expected-org-dn",
        "OU=ORG2,OU=DEPT,O=GC,C=CA",
    ]

    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    
    data = json.loads(res.stdout)
    assert data["base_unchanged"] is True
    assert data["contact_columns_present"] is False
    assert data["duplicate_source_urls"] == 0
    
    orgs = {o["org_dn"]: o for o in data["organizations"]}
    assert orgs["OU=ORG1,OU=DEPT,O=GC,C=CA"]["exceeds_25"] is True
    assert orgs["OU=ORG1,OU=DEPT,O=GC,C=CA"]["unique_people"] == 30
    assert orgs["OU=ORG2,OU=DEPT,O=GC,C=CA"]["exceeds_25"] is False
    assert orgs["OU=ORG2,OU=DEPT,O=GC,C=CA"]["unique_people"] == 25


def test_verifier_script_fails_if_neither_exceeds_25(base_and_overlay_dbs, tmp_path):
    base_db, overlay_db = base_and_overlay_dbs
    
    # Setup overlay DB with no new people
    empty_overlay = tmp_path / "empty_overlay.sqlite"
    with SnapshotStore(empty_overlay) as store:
        store.init_schema()
        store.db.execute(
            """
            INSERT INTO pagination_orgs (
                org_dn, department_dn, department_name, org_name, org_path, source_url, base_db_path, base_people_count,
                pages_fetched, status, last_error, terminal_reason
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("OU=ORG1,OU=DEPT,O=GC,C=CA", "OU=DEPT,O=GC,C=CA", "Dept", "Org1", "Dept / Org1", "url-org1", "base.sqlite", 25, 2, "finished", None, None)
        )
        store.db.execute(
            """
            INSERT INTO pagination_orgs (
                org_dn, department_dn, department_name, org_name, org_path, source_url, base_db_path, base_people_count,
                pages_fetched, status, last_error, terminal_reason
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("OU=ORG2,OU=DEPT,O=GC,C=CA", "OU=DEPT,O=GC,C=CA", "Dept", "Org2", "Dept / Org2", "url-org2", "base.sqlite", 25, 1, "finished", None, None)
        )
        store.commit()

    script_path = Path(__file__).parent.parent / "scripts" / "verify_pagination_backfill.py"
    cmd = [
        sys.executable,
        str(script_path),
        "--base-db",
        str(base_db),
        "--overlay-db",
        str(empty_overlay),
        "--expected-org-dn",
        "OU=ORG1,OU=DEPT,O=GC,C=CA",
        "--expected-org-dn",
        "OU=ORG2,OU=DEPT,O=GC,C=CA",
    ]

    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode != 0
    assert "Neither organization exceeds 25 people" in res.stderr


def test_verifier_script_fails_if_contact_columns_present(base_and_overlay_dbs, tmp_path):
    base_db, overlay_db = base_and_overlay_dbs
    
    # Add email column to overlay db
    conn = sqlite3.connect(overlay_db)
    conn.execute("ALTER TABLE people_index ADD COLUMN email TEXT")
    conn.close()

    script_path = Path(__file__).parent.parent / "scripts" / "verify_pagination_backfill.py"
    cmd = [
        sys.executable,
        str(script_path),
        "--base-db",
        str(base_db),
        "--overlay-db",
        str(overlay_db),
        "--expected-org-dn",
        "OU=ORG1,OU=DEPT,O=GC,C=CA",
        "--expected-org-dn",
        "OU=ORG2,OU=DEPT,O=GC,C=CA",
    ]

    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode != 0
    assert "Contact columns exist in people_index" in res.stderr
