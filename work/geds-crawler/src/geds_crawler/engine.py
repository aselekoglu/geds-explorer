from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from .config import DEPARTMENT_LIST_URL, DEFAULT_DEPARTMENTS, CrawlConfig
from .exporter import export_jsonl, write_report
from .fetcher import PoliteFetcher
from .models import OrgUnit, QueueItem
from .parser import extract_departments, extract_org_children, extract_people
from .progress import format_progress_line
from .store import SnapshotStore
from .urls import geds_url
from .catalog import select_departments


@dataclass(frozen=True)
class CrawlRunConfig:
    run_id: str
    output_dir: Path
    department_dns: set[str]
    rate_limit_seconds: float = 1.0
    stop_file: Path | None = None
    quiet: bool = False
    max_depth: int | None = None


@dataclass(frozen=True)
class CrawlResult:
    run_id: str
    status: str
    request_count: int


class StopSignal:
    def __init__(self, stop_file: Path | None = None):
        self.stop_file = stop_file

    def is_requested(self) -> bool:
        if self.stop_file is not None:
            return self.stop_file.exists()
        return False


class CrawlEngine:
    def __init__(self, config: CrawlRunConfig):
        self.config = config
        self.stop_signal = StopSignal(config.stop_file)

    def run(self) -> CrawlResult:
        self.config.output_dir.mkdir(parents=True, exist_ok=True)
        db_path = self.config.output_dir / "geds.sqlite"
        
        fetcher = PoliteFetcher(
            rate_limit_seconds=self.config.rate_limit_seconds,
            user_agent="GEDS Explorer research crawler/0.1 (+polite snapshot; no contact storage)",
        )
        
        started = time.monotonic()
        
        with SnapshotStore(db_path) as store:
            store.init_schema()
            
            # Check if we should insert/replace or update the crawl run
            # In simple CLI, it is always a new run or replacing the run_id record
            now = self._now()
            store.db.execute(
                "INSERT OR REPLACE INTO crawl_runs (id, started_at, status, request_count) VALUES (?, ?, ?, ?)",
                (self.config.run_id, now, "running", 0),
            )
            store.commit()
            
            # Determine if we need to seed the queue
            # If the database already has departments enqueued/seeded, skip seeding
            has_departments = store.count_rows("departments") > 0
            
            if not has_departments:
                # Seed phase
                html = fetcher.fetch_text(DEPARTMENT_LIST_URL)
                # Parse all departments
                all_depts = extract_departments(html, allowed_names=None)
                # Filter by canonical DNs
                seed_departments = select_departments(all_depts, self.config.department_dns)
                
                for department in seed_departments:
                    seen_at = self._now()
                    store.upsert_department(department, self.config.run_id, seen_at)
                    root = OrgUnit(
                        name=department.name,
                        dn=department.dn,
                        parent_dn=None,
                        department_dn=department.dn,
                        depth=0,
                        org_path=department.name,
                        source_url=department.source_url,
                    )
                    store.upsert_org_unit(root, self.config.run_id, seen_at)
                    store.enqueue_org(root, department.name)
                
                store.update_run_progress(self.config.run_id, fetcher.stats.request_count, "running")
                store.commit()
                self._log_progress(store, fetcher.stats.request_count, "seeded", "department list", 0)

            # BFS crawl loop
            status = "finished"
            stop_reason = None
            while True:
                if self.stop_signal.is_requested():
                    status = "stopped"
                    stop_reason = "operator_stop"
                    break
                
                item = store.next_pending_org()
                if item is None:
                    break
                    
                org = item.org
                if self.config.max_depth is not None and org.depth > self.config.max_depth:
                    store.mark_org_done(org.dn)
                    store.commit()
                    continue
                
                # Update heartbeat and current progress before fetching
                store.update_run_progress(
                    self.config.run_id,
                    request_count=fetcher.stats.request_count,
                    status="running",
                    heartbeat_at=self._now(),
                    current_org_dn=org.dn,
                    current_department_dn=org.department_dn
                )
                store.commit()
                    
                try:
                    page_html = fetcher.fetch_text(geds_url("014", org.dn))
                    seen_at = self._now()
                    
                    for person in extract_people(page_html, org.dn, org.department_dn, item.department_name, org.name, org.org_path):
                        store.upsert_person(person, self.config.run_id, seen_at)
                        
                    for child in extract_org_children(page_html, org.dn, org.department_dn, org.org_path, org.depth):
                        store.upsert_org_unit(child, self.config.run_id, seen_at)
                        if self.config.max_depth is None or child.depth <= self.config.max_depth:
                            store.enqueue_org(child, item.department_name)
                            
                    store.mark_org_done(org.dn)
                    store.update_run_progress(
                        self.config.run_id,
                        request_count=fetcher.stats.request_count,
                        status="running",
                        heartbeat_at=self._now(),
                        current_org_dn=org.dn,
                        current_department_dn=org.department_dn
                    )
                    store.commit()
                    self._log_progress(store, fetcher.stats.request_count, "done", org.org_path, org.depth)
                    
                except Exception as exc:
                    store.mark_org_error(org.dn, str(exc))
                    store.db.execute(
                        "INSERT INTO crawl_errors (url, error, attempts, created_at, crawl_run_id) VALUES (?, ?, ?, ?, ?)",
                        (org.source_url, str(exc), len(fetcher.retry_delays_seconds) + 1, self._now(), self.config.run_id),
                    )
                    store.update_run_progress(
                        self.config.run_id,
                        request_count=fetcher.stats.request_count,
                        status="running",
                        heartbeat_at=self._now(),
                        current_org_dn=org.dn,
                        current_department_dn=org.department_dn
                    )
                    store.commit()
                    self._log_progress(store, fetcher.stats.request_count, "error", org.org_path, org.depth)
            
            runtime = time.monotonic() - started
            # Save the final status of the run
            store.update_run_progress(
                self.config.run_id,
                request_count=fetcher.stats.request_count,
                status=status,
                heartbeat_at=self._now(),
                stop_reason=stop_reason
            )
            if status == "finished":
                store.db.execute(
                    "UPDATE crawl_runs SET finished_at=? WHERE id=?",
                    (self._now(), self.config.run_id),
                )
            store.commit()

        if status == "finished":
            export_jsonl(db_path, self.config.output_dir)
            write_report(db_path, self.config.output_dir, runtime, fetcher.stats.request_count)
            
        return CrawlResult(
            run_id=self.config.run_id,
            status=status,
            request_count=fetcher.stats.request_count,
        )

    def _log_progress(
        self,
        store: SnapshotStore,
        request_count: int,
        event: str,
        org_path: str,
        depth: int,
    ) -> None:
        if self.config.quiet:
            return
        queue = store.queue_counts()
        print(
            format_progress_line(
                event=event,
                org_path=org_path,
                depth=depth,
                request_count=request_count,
                org_count=store.count_rows("org_units"),
                people_count=store.count_rows("people_index"),
                queue_done=queue.get("done", 0),
                queue_pending=queue.get("pending", 0),
                error_count=store.count_rows("crawl_errors"),
            ),
            flush=True,
        )

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat()
