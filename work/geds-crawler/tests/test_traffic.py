import time
import sqlite3
import pytest
from pathlib import Path

from geds_crawler.control_store import ControlStore
from geds_crawler.traffic import (
    calculate_configured_rps,
    calculate_rolling_rps,
    can_start,
    distribute_shared_rate,
)
from geds_crawler.store import SnapshotStore


def test_calculate_configured_rps(tmp_path):
    control_db = tmp_path / "control.sqlite"
    
    with ControlStore(control_db) as store:
        store.init_schema()
        # Create two running jobs
        job1 = store.create_job("J1", {"OU=SSC,O=GC,C=CA"}, 2.0, "independent", str(tmp_path / "j1"))
        job2 = store.create_job("J2", {"OU=TBS,O=GC,C=CA"}, 4.0, "independent", str(tmp_path / "j2"))
        
        # Create active runs
        store.create_run(job1, "running")
        store.create_run(job2, "running")
        
    # Job 1 RPS = 1 / 2.0 = 0.5
    # Job 2 RPS = 1 / 4.0 = 0.25
    # Total = 0.75
    rps = calculate_configured_rps(control_db, unmanaged_estimates={"unmanaged-1": 0.1})
    assert rps == 0.85


def test_calculate_rolling_rps():
    # history is a list of (timestamp, total_requests)
    now = time.time()
    history = [
        (now - 10.0, 100),
        (now - 5.0, 105),
        (now, 110),
    ]
    
    rps = calculate_rolling_rps(history, window_seconds=10.0)
    # 10 requests over 10 seconds = 1.0 RPS
    assert rps == 1.0


def test_can_start_policy_decisions():
    # Inside budget (<= 1.0 RPS)
    assert can_start(projected_rps=0.8, budget_rps=1.0, acknowledged=False) == "allow"
    
    # Over budget, not acknowledged
    assert can_start(projected_rps=1.2, budget_rps=1.0, acknowledged=False) == "block"
    
    # Over budget, acknowledged
    assert can_start(projected_rps=1.2, budget_rps=1.0, acknowledged=True) == "warning"


def test_distribute_shared_rate(tmp_path):
    control_db = tmp_path / "control.sqlite"
    j1_dir = tmp_path / "j1"
    j2_dir = tmp_path / "j2"
    j1_dir.mkdir(parents=True, exist_ok=True)
    j2_dir.mkdir(parents=True, exist_ok=True)
    
    with ControlStore(control_db) as store:
        store.init_schema()
        job1 = store.create_job("J1", {"OU=SSC,O=GC,C=CA"}, 1.0, "shared", str(j1_dir))
        job2 = store.create_job("J2", {"OU=TBS,O=GC,C=CA"}, 1.0, "shared", str(j2_dir))
        
        run1 = store.create_run(job1, "running")
        run2 = store.create_run(job2, "running")
        
    # Initialize staging DBs
    with SnapshotStore(j1_dir / "geds.sqlite") as s1:
        s1.init_schema()
        s1.db.execute("INSERT OR REPLACE INTO crawl_runs (id, started_at, status, request_count, rate_limit_seconds) VALUES (?, ?, ?, ?, ?)", (run1, "2026-07-08", "running", 0, 1.0))
        s1.commit()
        
    with SnapshotStore(j2_dir / "geds.sqlite") as s2:
        s2.init_schema()
        s2.db.execute("INSERT OR REPLACE INTO crawl_runs (id, started_at, status, request_count, rate_limit_seconds) VALUES (?, ?, ?, ?, ?)", (run2, "2026-07-08", "running", 0, 1.0))
        s2.commit()
        
    # Distribute shared rate with a global budget of 1.0 RPS.
    # With 2 active shared runs, each should get rate_limit_seconds = 2.0 (i.e. 0.5 RPS)
    distribute_shared_rate(control_db, global_budget_rps=1.0)
    
    # Check staging DBs to see if rate_limit_seconds was updated to 2.0
    with SnapshotStore(j1_dir / "geds.sqlite") as s1:
        row = s1.db.execute("SELECT rate_limit_seconds FROM crawl_runs WHERE id=?", (run1,)).fetchone()
        assert row["rate_limit_seconds"] == 2.0
        
    with SnapshotStore(j2_dir / "geds.sqlite") as s2:
        row = s2.db.execute("SELECT rate_limit_seconds FROM crawl_runs WHERE id=?", (run2,)).fetchone()
        assert row["rate_limit_seconds"] == 2.0
