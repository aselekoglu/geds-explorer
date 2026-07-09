import os
import sys
import time
import sqlite3
import pytest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from geds_crawler.control_store import ControlStore
from geds_crawler.process_manager import ProcessManager
from geds_crawler.store import SnapshotStore


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


def test_reconcile_keeps_run_running_when_pid_check_disagrees_with_fresh_heartbeat(tmp_path):
    control_db = tmp_path / "control.sqlite"
    output_dir = tmp_path / "runs" / "live"
    output_dir.mkdir(parents=True)

    with ControlStore(control_db) as store:
        store.init_schema()
        job_id = store.create_job(
            "Live",
            {"OU=LIVE,O=GC,C=CA"},
            1.0,
            "queue",
            str(output_dir),
        )
        run_id = store.create_run(job_id, "running")
        store.db.execute(
            "UPDATE crawl_runs SET pid = ?, request_count = ? WHERE id = ?",
            (123456, 10, run_id),
        )
        store.commit()

    with SnapshotStore(output_dir / "geds.sqlite") as stage_store:
        stage_store.init_schema()
        stage_store.db.execute(
            """
            INSERT INTO crawl_runs
                (id, started_at, request_count, status, heartbeat_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                run_id,
                "2026-07-08T12:00:00+00:00",
                42,
                "running",
                datetime.now(UTC).isoformat(),
            ),
        )
        stage_store.commit()

    pm = ProcessManager(control_db)
    with patch.object(pm, "_is_pid_running", return_value=False):
        pm.reconcile()

    conn = sqlite3.connect(control_db)
    row = conn.execute(
        "SELECT status, request_count, finished_at FROM crawl_runs WHERE id = ?",
        (run_id,),
    ).fetchone()
    assert row == ("running", 42, None)
    conn.close()


def test_queue_policy_waits_until_budget_is_available(tmp_path):
    control_db = tmp_path / "control.sqlite"
    active_dir = tmp_path / "runs" / "active"
    queued_dir = tmp_path / "runs" / "queued"
    active_dir.mkdir(parents=True, exist_ok=True)
    queued_dir.mkdir(parents=True, exist_ok=True)

    with ControlStore(control_db) as store:
        store.init_schema()
        active_job = store.create_job("Active", {"OU=ACTIVE,O=GC,C=CA"}, 1.0, "queue", str(active_dir))
        queued_job = store.create_job("Queued", {"OU=QUEUED,O=GC,C=CA"}, 1.5, "queue", str(queued_dir))
        active_run = store.create_run(active_job, "running")
        queued_run = store.create_run(queued_job, "queued")
        store.db.execute("UPDATE crawl_runs SET pid = ? WHERE id = ?", (11111, active_run))
        store.commit()

    pm = ProcessManager(control_db)
    assert pm.try_start_run(queued_run) == "queued"

    with ControlStore(control_db) as store:
        store.db.execute("UPDATE crawl_runs SET status = 'finished' WHERE id = ?", (active_run,))
        store.commit()

    with patch("subprocess.Popen") as mock_popen:
        mock_proc = MagicMock()
        mock_proc.pid = 22222
        mock_popen.return_value = mock_proc

        assert pm.try_start_run(queued_run) == "running"

    conn = sqlite3.connect(control_db)
    row = conn.execute("SELECT status, pid FROM crawl_runs WHERE id = ?", (queued_run,)).fetchone()
    assert row == ("running", 22222)
    conn.close()


def test_process_manager_arguments_based_on_crawl_kind(tmp_path):
    control_db = tmp_path / "control.sqlite"
    run_dir = tmp_path / "runs" / "run1"
    run_dir.mkdir(parents=True, exist_ok=True)
    
    with ControlStore(control_db) as store:
        store.init_schema()
        job1_id = store.create_job("Job 1", {"OU=SSC-SPC,O=GC,C=CA"}, 1.0, "independent", str(run_dir), crawl_kind="full")
        run1_id = store.create_run(job1_id, "queued")

        # Fake a finished snapshot db to satisfy validation
        base_db_path = tmp_path / "base.sqlite"
        with SnapshotStore(base_db_path) as base_store:
            base_store.init_schema()
            base_store.db.execute(
                "INSERT INTO crawl_runs (id, started_at, request_count, status) VALUES ('r-base', 'now', 0, 'finished')"
            )
            base_store.commit()

        job2_id = store.create_job("Job 2", set(), 1.0, "independent", str(run_dir), crawl_kind="pagination_backfill", source_db_path=str(base_db_path))
        run2_id = store.create_run(job2_id, "queued")
        
    pm = ProcessManager(control_db)
    
    # Test Full run arguments
    with patch("subprocess.Popen") as mock_popen:
        mock_proc = MagicMock()
        mock_proc.pid = 11111
        mock_popen.return_value = mock_proc
        
        pm.start_run(run1_id)
        
        # Verify args passed
        called_args = mock_popen.call_args[0][0]
        assert "--crawl-kind" in called_args
        assert called_args[called_args.index("--crawl-kind") + 1] == "full"
        assert "--department-dns" in called_args
        assert "OU=SSC-SPC,O=GC,C=CA" in called_args

    # Test Pagination backfill run arguments
    with patch("subprocess.Popen") as mock_popen:
        mock_proc = MagicMock()
        mock_proc.pid = 22222
        mock_popen.return_value = mock_proc
        
        pm.start_run(run2_id)
        
        called_args = mock_popen.call_args[0][0]
        assert "--crawl-kind" in called_args
        assert called_args[called_args.index("--crawl-kind") + 1] == "pagination_backfill"
        assert "--control-db" in called_args
        assert called_args[called_args.index("--control-db") + 1] == str(control_db.resolve())
        # No --department-dns parameter passed
        assert "--department-dns" not in called_args
