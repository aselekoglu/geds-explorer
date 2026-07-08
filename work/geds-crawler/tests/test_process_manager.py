import os
import sys
import time
import sqlite3
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from geds_crawler.control_store import ControlStore
from geds_crawler.process_manager import ProcessManager


def test_process_manager_starts_and_stops_subprocess(tmp_path):
    control_db = tmp_path / "control.sqlite"
    run_dir = tmp_path / "runs" / "run1"
    run_dir.mkdir(parents=True, exist_ok=True)
    stop_file = run_dir / "stop_signal"
    
    with ControlStore(control_db) as store:
        store.init_schema()
        # Seed catalog and create a job
        job_id = store.create_job("Job 1", {"OU=SSC-SPC,O=GC,C=CA"}, 1.0, "independent", str(run_dir))
        run_id = store.create_run(job_id, "queued")
        
    # We want to test start_run which launches the subprocess.
    # To avoid launching a full crawl in the test, we patch the subprocess launch
    # to run a dummy python sleep process.
    dummy_args = [sys.executable, "-c", "import time, sys, os; print('running'); time.sleep(10)"]
    
    with patch("subprocess.Popen") as mock_popen:
        mock_proc = MagicMock()
        mock_proc.pid = 99999
        mock_proc.poll.return_value = None  # running
        mock_popen.return_value = mock_proc
        
        pm = ProcessManager(control_db)
        pid = pm.start_run(run_id, stop_file=stop_file, cmd_args=dummy_args)
        
        assert pid == 99999
        
    # Check that PID and status were updated in control DB
    conn = sqlite3.connect(control_db)
    row = conn.execute("SELECT pid, status FROM crawl_runs WHERE id=?", (run_id,)).fetchone()
    assert row[0] == 99999
    assert row[1] == "running"
    conn.close()
    
    # Test stop_run
    with patch("os.kill") as mock_kill:
        pm = ProcessManager(control_db)
        
        # Test cooperative stop: should write the stop file
        pm.stop_run(run_id, force=False)
        assert stop_file.exists()
        
        # Check that stop_requested flag is set in control DB
        conn = sqlite3.connect(control_db)
        row = conn.execute("SELECT stop_requested, status FROM crawl_runs WHERE id=?", (run_id,)).fetchone()
        assert row[0] == 1
        assert row[1] == "stopping"
        conn.close()
        
        # Test force stop: should call kill
        pm.stop_run(run_id, force=True)
        # Verify os.kill was called with pid 99999
        mock_kill.assert_called_once_with(99999, 15)  # SIGTERM or equivalent (on Windows it will be SIGTERM)


def test_process_manager_reconcile_stale_heartbeat(tmp_path):
    control_db = tmp_path / "control.sqlite"
    run_dir = tmp_path / "runs" / "run1"
    run_dir.mkdir(parents=True, exist_ok=True)
    staging_db = run_dir / "geds.sqlite"
    
    # Set up control DB with a running job
    with ControlStore(control_db) as store:
        store.init_schema()
        job_id = store.create_job("Job 1", {"OU=SSC-SPC,O=GC,C=CA"}, 1.0, "independent", str(run_dir))
        run_id = store.create_run(job_id, "running")
        # Update run with a stale PID that isn't running
        store.db.execute("UPDATE crawl_runs SET pid = ?, status = 'running' WHERE id = ?", (123456, run_id))
        store.commit()
        
    # Set up staging DB with a stale heartbeat
    # Let's create the staging DB
    from geds_crawler.store import SnapshotStore
    with SnapshotStore(staging_db) as stage_store:
        stage_store.init_schema()
        # Stale heartbeat (more than 30s ago, e.g. 1970)
        stage_store.update_run_progress(run_id, 0, "running", heartbeat_at="1970-01-01T00:00:00Z")
        stage_store.commit()
        
    pm = ProcessManager(control_db)
    
    # We mock os.kill or psutil to return that PID 123456 is not running
    with patch("geds_crawler.process_manager.ProcessManager._is_pid_running", return_value=False):
        pm.reconcile()
        
    # Reconcile should detect the stale process and mark the run as failed in control DB
    conn = sqlite3.connect(control_db)
    row = conn.execute("SELECT status FROM crawl_runs WHERE id=?", (run_id,)).fetchone()
    assert row[0] == "failed"
    conn.close()
