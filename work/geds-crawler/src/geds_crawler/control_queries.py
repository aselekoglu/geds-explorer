from __future__ import annotations

import sqlite3
from datetime import datetime, UTC
from pathlib import Path
from typing import Any, Sequence

from .run_metrics import (
    calculate_progress,
    estimate_remaining_requests,
    estimate_eta,
)
from .store import SnapshotStore


class ControlQueries:
    def __init__(self, control_db_path: Path | str):
        self.control_db_path = Path(control_db_path).resolve()

    def _resolve_output_dir(self, output_dir: str) -> Path:
        path = Path(output_dir)
        if path.is_absolute():
            return path
        return self.control_db_path.parent / path

    def enrich_run(self, run: dict[str, Any], rate_limit_seconds: float = 1.0) -> dict[str, Any]:
        enriched = dict(run)
        configured_rps = 1.0 / rate_limit_seconds if rate_limit_seconds > 0 else 1.0
        enriched["configured_rps"] = configured_rps
        
        # Default neutral metrics
        total_orgs = 0
        if run.get("crawl_kind") == "pagination_backfill":
            with sqlite3.connect(self.control_db_path) as con:
                row = con.execute("SELECT COUNT(*) FROM run_pagination_seeds WHERE run_id = ?", (run["id"],)).fetchone()
                total_orgs = row[0] if row else 0

        enriched["progress"] = calculate_progress(total_orgs, 0, 0)
        enriched["measured_rps"] = None
        enriched["pagination_metrics"] = {
            "pages_fetched": 0,
            "known_pending_pages": 0,
            "new_people": 0,
            "deduped_people": 0,
            "active_org": None,
        }
        enriched["eta"] = {
            "expected_seconds": 0,
            "low_seconds": 0,
            "high_seconds": 0,
            "confidence": "low",
            "basis": "configured_rate",
            "estimated_finish_at": run["started_at"],
        }
        
        # Check if staging DB exists
        output_dir = self._resolve_output_dir(run["output_dir"])
        staging_db = output_dir / "geds.sqlite"
        if not staging_db.is_file():
            return enriched
            
        try:
            with SnapshotStore(staging_db) as stage_store:
                prog = stage_store.pagination_progress()
                metrics = stage_store.pagination_metrics()
                samples = stage_store.completed_org_samples()
                
                # Fetch recent run information to compute measured RPS
                stage_run = stage_store.db.execute(
                    "SELECT request_count, heartbeat_at, started_at, status FROM crawl_runs WHERE id = ?",
                    (run["id"],),
                ).fetchone()
                
                incomplete_rows = stage_store.db.execute(
                    """
                    SELECT org_dn FROM pagination_orgs
                    WHERE status NOT IN ('finished', 'failed')
                    """
                ).fetchall()
                incomplete_org_dns = {r[0] for r in incomplete_rows}
                
                pending_page_rows = stage_store.db.execute(
                    """
                    SELECT DISTINCT org_dn FROM people_page_queue
                    WHERE status = 'pending'
                    """
                ).fetchall()
                orgs_with_pending = {r[0] for r in pending_page_rows}
                
                incomplete_without_next = len(incomplete_org_dns - orgs_with_pending)
        except Exception:
            return enriched

        if not stage_run:
            return enriched

        pages_fetched = metrics["pages_fetched"]
        known_pending_pages = metrics["known_pending_pages"]
        
        completed_samples = [s["pages_fetched"] for s in samples]
        remaining_requests = estimate_remaining_requests(
            known_pending_pages=known_pending_pages,
            incomplete_orgs_without_known_next=incomplete_without_next,
            completed_org_request_samples=completed_samples,
        )
        
        measured_rps = None
        measured_at = None
        
        if stage_run["heartbeat_at"] and stage_run["started_at"]:
            try:
                def parse_iso(dt_str: str) -> datetime:
                    cleaned = dt_str.replace("Z", "+00:00")
                    return datetime.fromisoformat(cleaned)
                    
                hb = parse_iso(stage_run["heartbeat_at"])
                st = parse_iso(stage_run["started_at"])
                duration = (hb - st).total_seconds()
                if duration > 1.0:
                    measured_rps = stage_run["request_count"] / duration
                    measured_at = hb
            except Exception:
                pass

        now = datetime.now(UTC)
        eta_est = estimate_eta(
            remaining_requests=remaining_requests,
            configured_rps=configured_rps,
            measured_rps=measured_rps,
            measured_at=measured_at,
            completed_orgs=prog["completed_orgs"],
            now=now,
        )
        
        enriched["progress"] = {
            "total_orgs": prog["total_orgs"] if run.get("crawl_kind") == "pagination_backfill" else total_orgs,
            "completed_orgs": prog["completed_orgs"],
            "failed_orgs": prog["failed_orgs"],
            "terminal_orgs": prog["terminal_orgs"],
            "percent": prog["percent"],
        }
        enriched["pagination_metrics"] = {
            "pages_fetched": pages_fetched,
            "known_pending_pages": known_pending_pages,
            "new_people": metrics["new_people"],
            "deduped_people": metrics["deduped_people"],
            "active_org": metrics["active_org"],
        }
        enriched["request_count"] = int(stage_run["request_count"])
        enriched["heartbeat_at"] = stage_run["heartbeat_at"]
        enriched["current_org_dn"] = metrics["active_org"]
        enriched["eta"] = {
            "expected_seconds": eta_est.expected_seconds,
            "low_seconds": eta_est.low_seconds,
            "high_seconds": eta_est.high_seconds,
            "confidence": eta_est.confidence,
            "basis": eta_est.basis,
            "estimated_finish_at": eta_est.estimated_finish_at,
        }
        enriched["measured_rps"] = measured_rps
        
        return enriched

    def list_run_pagination_orgs(
        self,
        run_id: str,
        status: str = "",
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        with sqlite3.connect(self.control_db_path) as con:
            con.row_factory = sqlite3.Row
            row = con.execute("SELECT output_dir FROM crawl_runs WHERE id = ?", (run_id,)).fetchone()
            if not row:
                raise ValueError(f"Run not found: {run_id}")
            output_dir = self._resolve_output_dir(row["output_dir"])
            
        staging_db = output_dir / "geds.sqlite"
        if not staging_db.is_file():
            return {"items": [], "total": 0, "limit": limit, "offset": offset}
            
        bounded_limit = min(max(int(limit), 1), 100)
        bounded_offset = max(int(offset), 0)
        
        clauses = []
        params = []
        if status:
            # support filtering by 'error' which maps to 'failed' status in pagination_orgs
            if status == "error":
                clauses.append("status = 'failed'")
            else:
                clauses.append("status = ?")
                params.append(status)
            
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        
        with sqlite3.connect(f"file:{staging_db.as_posix()}?mode=ro", uri=True) as con:
            con.row_factory = sqlite3.Row
            total = con.execute(f"SELECT COUNT(*) FROM pagination_orgs{where}", params).fetchone()[0]
            rows = con.execute(
                f"SELECT * FROM pagination_orgs{where} ORDER BY org_path COLLATE NOCASE LIMIT ? OFFSET ?",
                [*params, bounded_limit, bounded_offset],
            ).fetchall()
            
        return {
            "items": [dict(r) for r in rows],
            "total": total,
            "limit": bounded_limit,
            "offset": bounded_offset,
        }
