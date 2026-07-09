import os
import sqlite3
import pytest
from pathlib import Path

from geds_crawler.control_store import ControlStore
from geds_crawler.models import Department


def test_control_store_init_and_tables(tmp_path):
    db_path = tmp_path / "control.sqlite"
    
    with ControlStore(db_path) as store:
        store.init_schema()
        
    # Check that database file exists
    assert db_path.exists()
    
    # Check that tables exist and WAL mode is enabled
    conn = sqlite3.connect(db_path)
    journal_mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert journal_mode.lower() == "wal"
    
    tables = {
        row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    
    expected_tables = {
        "schema_version",
        "department_catalog",
        "crawl_jobs",
        "job_departments",
        "crawl_runs",
        "run_departments",
        "schedules",
        "controller_events",
    }
    assert expected_tables.issubset(tables)
    conn.close()


def test_control_store_create_job_and_run(tmp_path):
    db_path = tmp_path / "control.sqlite"
    
    with ControlStore(db_path) as store:
        store.init_schema()
        
        # Create a job
        job_id = store.create_job(
            name="ISED + CRTC",
            department_dns={"OU=ISED-ISDE,O=GC,C=CA", "OU=CRTC,O=GC,C=CA"},
            rate_limit_seconds=1.5,
            traffic_policy="queue",
            output_dir="/tmp/ised",
        )
        assert job_id is not None
        
        # Create a run
        run_id = store.create_run(job_id=job_id, status="queued")
        assert run_id is not None
        
        # List runs
        runs = store.list_runs()
        assert len(runs) == 1
        assert runs[0]["id"] == run_id
        assert runs[0]["status"] == "queued"
        assert runs[0]["job_name"] == "ISED + CRTC"


def test_control_store_catalog_and_all_remaining(tmp_path):
    db_path = tmp_path / "control.sqlite"
    
    with ControlStore(db_path) as store:
        store.init_schema()
        
        # Seed catalog
        catalog = [
            Department(name="Shared Services Canada", dn="OU=SSC-SPC,O=GC,C=CA", source_url="url1"),
            Department(name="Innovation Science and Economic Development Canada", dn="OU=ISED-ISDE,O=GC,C=CA", source_url="url2"),
            Department(name="CRTC", dn="OU=CRTC,O=GC,C=CA", source_url="url3"),
        ]
        store.upsert_catalog(catalog)
        
        # Create job with SSC and CRTC
        store.create_job(
            name="Job 1",
            department_dns={"OU=SSC-SPC,O=GC,C=CA", "OU=CRTC,O=GC,C=CA"},
            rate_limit_seconds=1.0,
            traffic_policy="shared",
            output_dir="/tmp/job1",
        )
        
        # "All remaining" builder means catalog DNs minus DNs already assigned to enabled jobs
        remaining_dns = store.get_all_remaining_dns()
        assert remaining_dns == {"OU=ISED-ISDE,O=GC,C=CA"}


def test_control_store_coverage(tmp_path):
    db_path = tmp_path / "control.sqlite"
    
    with ControlStore(db_path) as store:
        store.init_schema()
        
        catalog = [
            Department(name="Shared Services Canada", dn="OU=SSC-SPC,O=GC,C=CA", source_url="url1"),
            Department(name="ISED", dn="OU=ISED-ISDE,O=GC,C=CA", source_url="url2"),
            Department(name="CRTC", dn="OU=CRTC,O=GC,C=CA", source_url="url3"),
        ]
        store.upsert_catalog(catalog)
        
        # Test 1: SSC is assigned to Job 1, ISED is unassigned, CRTC has overlap
        job1_id = store.create_job("Job 1", {"OU=SSC-SPC,O=GC,C=CA", "OU=CRTC,O=GC,C=CA"}, 1.0, "shared", "/tmp/j1")
        job2_id = store.create_job("Job 2", {"OU=CRTC,O=GC,C=CA"}, 1.0, "shared", "/tmp/j2")
        
        cov = store.coverage()
        assert cov["OU=SSC-SPC,O=GC,C=CA"]["status"] == "scheduled"
        assert cov["OU=ISED-ISDE,O=GC,C=CA"]["status"] == "unassigned"
        assert cov["OU=CRTC,O=GC,C=CA"]["status"] == "overlap"
        
        # Test 2: running run sets it to running
        run_id = store.create_run(job1_id, "running")
        cov2 = store.coverage()
        # Since Job 1 includes SSC and CRTC, SSC should now be running
        assert cov2["OU=SSC-SPC,O=GC,C=CA"]["status"] == "running"


def test_control_store_v2_migration_and_freezing(tmp_path):
    # Setup: Create a v1 control database manually, close it, and run init_schema to migrate to v2
    db_path = tmp_path / "control.sqlite"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE schema_version (
            version INTEGER PRIMARY KEY
        );
        """
    )
    conn.execute("INSERT INTO schema_version (version) VALUES (1)")
    conn.execute(
        """
        CREATE TABLE crawl_jobs (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL,
            rate_limit_seconds REAL NOT NULL,
            traffic_policy TEXT NOT NULL,
            output_dir TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1
        );
        """
    )
    conn.execute(
        """
        CREATE TABLE crawl_runs (
            id TEXT PRIMARY KEY,
            job_id TEXT,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            status TEXT NOT NULL,
            request_count INTEGER NOT NULL DEFAULT 0,
            pid INTEGER,
            stop_requested INTEGER NOT NULL DEFAULT 0,
            output_dir TEXT NOT NULL
        );
        """
    )
    conn.commit()
    conn.close()

    # Now open with ControlStore and initialize schema (should run v2 migration)
    with ControlStore(db_path) as store:
        store.init_schema()
        # Verify schema version table is updated to 2
        ver = store.db.execute("SELECT version FROM schema_version").fetchone()[0]
        assert ver == 2
        
        # Verify run_pagination_seeds table exists
        tables = {row[0] for row in store.db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert "run_pagination_seeds" in tables

    # Test freezing targets:
    # 1. Create a dummy base snapshot sqlite DB
    base_db_path = tmp_path / "base_snapshot.sqlite"
    from geds_crawler.store import SnapshotStore
    from geds_crawler.models import OrgUnit, PersonIndex
    with SnapshotStore(base_db_path) as base_store:
        base_store.init_schema()
        
        # Seed run
        base_store.db.execute(
            "INSERT INTO crawl_runs (id, started_at, request_count, status) VALUES ('run-base', '2026-07-08T12:00:00+00:00', 10, 'finished')"
        )
        # Create department
        base_store.db.execute(
            "INSERT INTO departments (dn, name, source_url, first_seen, last_seen, crawl_run_id) VALUES ('OU=DEPT,O=GC,C=CA', 'Dept', 'url', 'now', 'now', 'run-base')"
        )
        
        # Org 1: exactly 25 people (capped)
        org1 = OrgUnit("Org1", "OU=ORG1,OU=DEPT,O=GC,C=CA", None, "OU=DEPT,O=GC,C=CA", 1, "Dept / Org1", "url-org1")
        base_store.upsert_org_unit(org1, "run-base", "now")
        for i in range(25):
            person = PersonIndex(f"Person {i}", "Title", org1.dn, org1.department_dn, "Dept", org1.name, org1.org_path, f"url-person-1-{i}")
            base_store.upsert_person(person, "run-base", "now")
            
        # Org 2: 24 people (not capped)
        org2 = OrgUnit("Org2", "OU=ORG2,OU=DEPT,O=GC,C=CA", None, "OU=DEPT,O=GC,C=CA", 1, "Dept / Org2", "url-org2")
        base_store.upsert_org_unit(org2, "run-base", "now")
        for i in range(24):
            person = PersonIndex(f"Person {i}", "Title", org2.dn, org2.department_dn, "Dept", org2.name, org2.org_path, f"url-person-2-{i}")
            base_store.upsert_person(person, "run-base", "now")
            
        # Org 3: 26 people (not capped)
        org3 = OrgUnit("Org3", "OU=ORG3,OU=DEPT,O=GC,C=CA", None, "OU=DEPT,O=GC,C=CA", 1, "Dept / Org3", "url-org3")
        base_store.upsert_org_unit(org3, "run-base", "now")
        for i in range(26):
            person = PersonIndex(f"Person {i}", "Title", org3.dn, org3.department_dn, "Dept", org3.name, org3.org_path, f"url-person-3-{i}")
            base_store.upsert_person(person, "run-base", "now")
            
        base_store.commit()

    # Now create job and run on control store
    with ControlStore(db_path) as store:
        # Assert exception raised if source DB not finished or not present
        with pytest.raises(ValueError):
            store.create_job("Backfill Job", set(), 1.0, "queue", "/tmp/out", crawl_kind="pagination_backfill", source_db_path="invalid.sqlite")

        job_id = store.create_job("Backfill Job", set(), 1.0, "queue", "/tmp/out", crawl_kind="pagination_backfill", source_db_path=str(base_db_path))
        
        # Verify run creation freezes targets (only Org1 because it has exactly 25 people)
        run_id = store.create_run(job_id)
        seeds = store.list_pagination_seeds(run_id)
        assert len(seeds) == 1
        assert seeds[0]["org_dn"] == "OU=ORG1,OU=DEPT,O=GC,C=CA"
        assert seeds[0]["base_people_count"] == 25

