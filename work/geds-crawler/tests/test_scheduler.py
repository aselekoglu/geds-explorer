from datetime import datetime, UTC
import zoneinfo
import pytest

from geds_crawler.scheduler import (
    validate_cron,
    next_occurrence,
    resolve_overlap_policy,
)
from geds_crawler.control_store import ControlStore


def test_validate_cron():
    # Valid expressions
    assert validate_cron("*/5 * * * *") == "*/5 * * * *"
    assert validate_cron("0 0 * * *") == "0 0 * * *"
    
    # Invalid expressions
    with pytest.raises(ValueError):
        validate_cron("invalid cron")
        
    with pytest.raises(ValueError):
        validate_cron("* * * * * *")  # 6 fields, not 5


def test_next_occurrence():
    # Let's check with America/Toronto timezone
    tz = zoneinfo.ZoneInfo("America/Toronto")
    after = datetime(2026, 7, 8, 12, 0, 0, tzinfo=tz)
    
    # "hourly" -> should be 2026-07-08 13:00:00
    next_time = next_occurrence("hourly", "America/Toronto", after)
    assert next_time == datetime(2026, 7, 8, 13, 0, 0, tzinfo=tz)
    
    # "daily" -> 2026-07-09 00:00:00
    next_time_daily = next_occurrence("daily", "America/Toronto", after)
    assert next_time_daily == datetime(2026, 7, 9, 0, 0, 0, tzinfo=tz)


def test_resolve_overlap_policy(tmp_path):
    control_db = tmp_path / "control.sqlite"
    
    with ControlStore(control_db) as store:
        store.init_schema()
        job_id = store.create_job("J1", {"OU=SSC,O=GC,C=CA"}, 1.0, "independent", str(tmp_path / "j1"))
        
        # Test 1: No runs active -> should allow starting
        decision = resolve_overlap_policy(store, job_id, overlap_policy="skip")
        assert decision == "start"
        
        # Start a run
        run_id = store.create_run(job_id, "running")
        
        # Test 2: Skip policy -> should skip
        decision_skip = resolve_overlap_policy(store, job_id, overlap_policy="skip")
        assert decision_skip == "skip"
        
        # Test 3: Queue policy -> should queue (returns queued run_id)
        decision_queue = resolve_overlap_policy(store, job_id, overlap_policy="queue")
        assert decision_queue.startswith("queued:")
        
        # Verify run was queued
        runs = store.list_runs()
        queued_runs = [r for r in runs if r["status"] == "queued"]
        assert len(queued_runs) == 1
        
        # Test 4: Allow policy -> should allow starting
        decision_allow = resolve_overlap_policy(store, job_id, overlap_policy="allow")
        assert decision_allow == "start"
