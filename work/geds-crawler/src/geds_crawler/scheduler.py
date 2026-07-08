from __future__ import annotations

import zoneinfo
from datetime import datetime
from croniter import croniter

from .control_store import ControlStore


PRESET_MAP = {
    "hourly": "0 * * * *",
    "daily": "0 0 * * *",
    "weekly": "0 0 * * 0",
}


def validate_cron(expression: str) -> str:
    expr = PRESET_MAP.get(expression.lower(), expression)
    try:
        # croniter requires exactly 5 fields
        parts = expr.split()
        if len(parts) != 5:
            raise ValueError("Cron expression must have exactly 5 fields")
        # Validate syntax
        croniter(expr)
    except Exception as exc:
        raise ValueError(f"Invalid cron expression: {exc}")
    return expr


def next_occurrence(expression: str, timezone_str: str, after_datetime: datetime) -> datetime:
    expr = PRESET_MAP.get(expression.lower(), expression)
    tz = zoneinfo.ZoneInfo(timezone_str)
    
    # Ensure after_datetime has timezone info
    if after_datetime.tzinfo is None:
        after_datetime = after_datetime.replace(tzinfo=tz)
    else:
        after_datetime = after_datetime.astimezone(tz)
        
    iter_cron = croniter(expr, after_datetime)
    next_time = iter_cron.get_next(datetime)
    return next_time.astimezone(tz)


def resolve_overlap_policy(store: ControlStore, job_id: str, overlap_policy: str) -> str:
    # Check if there are any active runs for this job
    rows = store.db.execute(
        """
        SELECT id FROM crawl_runs
        WHERE job_id = ? AND status IN ('running', 'stopping', 'queued')
        """,
        (job_id,),
    ).fetchall()
    
    is_active = len(rows) > 0
    
    if not is_active:
        return "start"
        
    if overlap_policy == "skip":
        return "skip"
    elif overlap_policy == "queue":
        # Create a run in 'queued' status
        run_id = store.create_run(job_id, status="queued")
        return f"queued:{run_id}"
    elif overlap_policy == "allow":
        return "start"
        
    return "start"
