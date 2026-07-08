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
        assert cov["OU=SSC-SPC,O=GC,C=CA"] == "scheduled"
        assert cov["OU=ISED-ISDE,O=GC,C=CA"] == "unassigned"
        assert cov["OU=CRTC,O=GC,C=CA"] == "overlap"
        
        # Test 2: running run sets it to running
        run_id = store.create_run(job1_id, "running")
        cov2 = store.coverage()
        # Since Job 1 includes SSC and CRTC, SSC should now be running
        assert cov2["OU=SSC-SPC,O=GC,C=CA"] == "running"

