from __future__ import annotations

import sqlite3
import time
from pathlib import Path


def calculate_configured_rps(control_db_path: Path | str, unmanaged_estimates: dict[str, float] | None = None) -> float:
    total_rps = 0.0
    
    # Query all active runs and get their jobs' rate limit
    with sqlite3.connect(control_db_path) as con:
        con.row_factory = sqlite3.Row
        rows = con.execute(
            """
            SELECT j.rate_limit_seconds
            FROM crawl_runs r
            JOIN crawl_jobs j ON j.id = r.job_id
            WHERE r.status IN ('running', 'stopping')
            """
        ).fetchall()
        
    for row in rows:
        rate = row["rate_limit_seconds"]
        if rate > 0:
            total_rps += 1.0 / rate

    # Add estimates for unmanaged/legacy runs
    if unmanaged_estimates:
        for estimate in unmanaged_estimates.values():
            total_rps += estimate
            
    return total_rps


def calculate_rolling_rps(history: list[tuple[float, int]], window_seconds: float = 10.0) -> float:
    if len(history) < 2:
        return 0.0
        
    now = time.time()
    # Filter history to window
    window_start = now - window_seconds
    relevant = [item for item in history if item[0] >= window_start]
    
    if len(relevant) < 2:
        return 0.0
        
    t_first, count_first = relevant[0]
    t_last, count_last = relevant[-1]
    
    duration = t_last - t_first
    if duration <= 0:
        return 0.0
        
    delta_requests = count_last - count_first
    return max(0.0, delta_requests / duration)


def can_start(projected_rps: float, budget_rps: float = 1.0, acknowledged: bool = False) -> str:
    if projected_rps <= budget_rps:
        return "allow"
    elif acknowledged:
        return "warning"
    else:
        return "block"


def distribute_shared_rate(control_db_path: Path | str, global_budget_rps: float = 1.0) -> None:
    # 1. Query all active runs that have a 'shared' policy
    with sqlite3.connect(control_db_path) as con:
        con.row_factory = sqlite3.Row
        rows = con.execute(
            """
            SELECT r.id, r.output_dir
            FROM crawl_runs r
            JOIN crawl_jobs j ON j.id = r.job_id
            WHERE r.status = 'running' AND j.traffic_policy = 'shared'
            """
        ).fetchall()
        
    if not rows:
        return
        
    n_shared = len(rows)
    # Each shared run gets an equal share of the budget: budget_rps / n_shared.
    # Therefore, individual rate_limit_seconds = n_shared / global_budget_rps.
    rate_limit_seconds = float(n_shared) / global_budget_rps
    
    for row in rows:
        run_id = row["id"]
        output_dir = Path(row["output_dir"])
        staging_db = output_dir / "geds.sqlite"
        
        # Write this new rate limit to the staging DB's crawl_runs table so the worker picks it up
        if staging_db.exists():
            try:
                with sqlite3.connect(staging_db) as stage_conn:
                    stage_conn.execute(
                        "UPDATE crawl_runs SET rate_limit_seconds = ? WHERE id = ?",
                        (rate_limit_seconds, run_id),
                    )
                    stage_conn.commit()
            except Exception:
                pass
