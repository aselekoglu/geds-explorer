from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from .config import DEPARTMENT_LIST_URL, DEFAULT_DEPARTMENTS, CrawlConfig
from .exporter import export_jsonl, write_report
from .fetcher import PoliteFetcher
from .models import OrgUnit, QueueItem, PeoplePageItem, PaginationTarget
from .parser import extract_departments, extract_org_children, extract_people, extract_people_page
from .progress import format_progress_line
from .store import SnapshotStore
from .urls import geds_url
from .catalog import select_departments
from .pagination import MAX_PAGES_PER_ORG


@dataclass(frozen=True)
class CrawlRunConfig:
    run_id: str
    output_dir: Path
    department_dns: set[str]
    rate_limit_seconds: float = 1.0
    stop_file: Path | None = None
    quiet: bool = False
    max_depth: int | None = None
    crawl_kind: Literal["full", "pagination_backfill"] = "full"
    control_db_path: Path | None = None
    max_pages_per_org: int = MAX_PAGES_PER_ORG


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
                "INSERT OR REPLACE INTO crawl_runs (id, started_at, status, request_count, rate_limit_seconds) VALUES (?, ?, ?, ?, ?)",
                (self.config.run_id, now, "running", 0, self.config.rate_limit_seconds),
            )
            store.commit()
            
            # Determine if we need to seed the queue
            if self.config.crawl_kind == "pagination_backfill":
                orgs_count = int(store.db.execute("SELECT COUNT(*) FROM pagination_orgs").fetchone()[0])
                if orgs_count == 0:
                    if not self.config.control_db_path:
                        raise ValueError("control_db_path is required for pagination_backfill")
                    import sqlite3
                    try:
                        # Open the control DB read-only
                        # We use Path to resolve control_db_path to an absolute path first
                        abs_control_db = Path(self.config.control_db_path).resolve()
                        control_conn = sqlite3.connect(f"file:{abs_control_db}?mode=ro", uri=True)
                        control_conn.row_factory = sqlite3.Row
                    except Exception as e:
                        store.update_run_progress(self.config.run_id, 0, "failed", stop_reason="no_control_db")
                        store.commit()
                        raise ValueError(f"Could not open control DB: {e}")

                    seeds = control_conn.execute(
                        """
                        SELECT org_dn, source_url, department_dn, department_name, org_name, org_path, base_db_path, base_people_count
                        FROM run_pagination_seeds
                        WHERE run_id = ?
                        """,
                        (self.config.run_id,),
                    ).fetchall()
                    control_conn.close()

                    if not seeds:
                        store.update_run_progress(self.config.run_id, 0, "failed", stop_reason="no_frozen_targets")
                        store.commit()
                        return CrawlResult(self.config.run_id, "failed", 0)

                    seen_at = self._now()
                    for seed in seeds:
                        store.db.execute(
                            """
                            INSERT INTO departments (dn, name, source_url, first_seen, last_seen, crawl_run_id)
                            VALUES (?, ?, ?, ?, ?, ?)
                            ON CONFLICT(dn) DO NOTHING
                            """,
                            (seed["department_dn"], seed["department_name"], seed["source_url"], seen_at, seen_at, self.config.run_id),
                        )
                        org_unit = OrgUnit(
                            name=seed["org_name"],
                            dn=seed["org_dn"],
                            parent_dn=None,
                            department_dn=seed["department_dn"],
                            depth=0,
                            org_path=seed["org_path"],
                            source_url=seed["source_url"],
                        )
                        store.upsert_org_unit(org_unit, self.config.run_id, seen_at)

                        target = PaginationTarget(
                            org=org_unit,
                            department_name=seed["department_name"],
                            base_db_path=seed["base_db_path"],
                            base_people_count=seed["base_people_count"],
                        )
                        store.seed_pagination_target(target, seen_at)

                        store.enqueue_org(org_unit, seed["department_name"])
                        store.enqueue_people_page(
                            org_dn=seed["org_dn"],
                            page_url=seed["source_url"],
                            page_index=1,
                            discovered_from=None,
                            seen_at=seen_at,
                        )
                    store.commit()
            else:
                has_departments = store.count_rows("departments") > 0
                if not has_departments:
                    # Seed phase
                    html = fetcher.fetch_text(DEPARTMENT_LIST_URL)
                    all_depts = extract_departments(html, allowed_names=None)
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

                self._ensure_first_page(store, item, self._now())
                
                crawl_status, err_msg = self._crawl_pending_pages(store, fetcher, item)
                
                if crawl_status == "stopped":
                    status = "stopped"
                    stop_reason = "operator_stop"
                    break
                elif crawl_status == "error":
                    store.mark_org_error(org.dn, err_msg or "Page crawl failed")
                    store.commit()
                elif crawl_status == "success":
                    store.mark_pagination_org_success(org.dn, "completed_all_pages", self._now())
                    store.mark_org_done(org.dn)
                    store.commit()
            
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

    def _ensure_first_page(
        self, store: SnapshotStore, item: QueueItem, seen_at: str
    ) -> None:
        """Create page-one state only when the org has no persisted page rows."""
        # Ensure it exists in pagination_orgs for tracking pagination
        store.db.execute(
            """
            INSERT INTO pagination_orgs (
                org_dn, department_dn, department_name, org_name, org_path, source_url,
                base_db_path, base_people_count, status, started_at
            )
            VALUES (?, ?, ?, ?, ?, ?, '', 0, 'pending', ?)
            ON CONFLICT(org_dn) DO NOTHING
            """,
            (
                item.org.dn,
                item.org.department_dn,
                item.department_name,
                item.org.name,
                item.org.org_path,
                item.org.source_url,
                seen_at,
            ),
        )
        row = store.db.execute(
            "SELECT COUNT(*) FROM people_page_queue WHERE org_dn = ?",
            (item.org.dn,),
        ).fetchone()
        if row[0] == 0:
            store.enqueue_people_page(
                org_dn=item.org.dn,
                page_url=item.org.source_url,
                page_index=1,
                discovered_from=None,
                seen_at=seen_at,
            )
            store.commit()

    def _crawl_pending_pages(
        self, store: SnapshotStore, fetcher: PoliteFetcher, item: QueueItem
    ) -> tuple[Literal["success", "stopped", "error"], str | None]:
        """Process persisted pages until terminal, stop, or guard failure."""
        visited_urls = set()
        cursor = store.db.execute(
            "SELECT page_url FROM people_page_queue WHERE org_dn = ? AND status = 'done'",
            (item.org.dn,),
        )
        for row in cursor:
            visited_urls.add(row[0])

        while True:
            page_item = store.next_pending_people_page(org_dn=item.org.dn)
            if page_item is None:
                return "success", None

            if page_item.page_url in visited_urls:
                err_msg = f"Cycle detected: {page_item.page_url}"
                store.mark_pagination_org_error(item.org.dn, err_msg, self._now())
                store.commit()
                return "error", err_msg

            visited_urls.add(page_item.page_url)
            res, err_msg = self._process_people_page(store, fetcher, item, page_item)
            if res == "stopped":
                return "stopped", None
            elif res == "error":
                return "error", err_msg
            elif res == "terminal":
                return "success", None

    def _process_people_page(
        self,
        store: SnapshotStore,
        fetcher: PoliteFetcher,
        item: QueueItem,
        page_item: PeoplePageItem,
    ) -> tuple[Literal["next", "terminal", "stopped", "error"], str | None]:
        """Fetch and atomically commit exactly one queued page."""
        if self.stop_signal.is_requested():
            return "stopped", None

        db_row = store.db.execute(
            "SELECT rate_limit_seconds FROM crawl_runs WHERE id=?",
            (self.config.run_id,),
        ).fetchone()
        if db_row:
            fetch_rate = db_row["rate_limit_seconds"]
            if fetch_rate != fetcher.rate_limit_seconds:
                fetcher.rate_limit_seconds = fetch_rate

        store.update_run_progress(
            self.config.run_id,
            request_count=fetcher.stats.request_count,
            status="running",
            heartbeat_at=self._now(),
            current_org_dn=item.org.dn,
            current_department_dn=item.org.department_dn,
        )
        store.commit()

        try:
            page_html = fetcher.fetch_text(page_item.page_url)
            seen_at = self._now()
        except Exception as exc:
            err_msg = str(exc)
            store.db.execute(
                """
                UPDATE people_page_queue
                SET attempts = attempts + 1, last_error = ?
                WHERE page_url = ?
                """,
                (err_msg, page_item.page_url),
            )
            store.db.execute(
                "INSERT INTO crawl_errors (url, error, attempts, created_at, crawl_run_id) VALUES (?, ?, ?, ?, ?)",
                (
                    page_item.page_url,
                    err_msg,
                    len(fetcher.retry_delays_seconds) + 1,
                    self._now(),
                    self.config.run_id,
                ),
            )
            store.mark_pagination_org_error(item.org.dn, err_msg, self._now())
            store.commit()
            return "error", err_msg

        page = extract_people_page(
            page_html,
            org_dn=item.org.dn,
            department_dn=item.org.department_dn,
            department_name=item.department_name,
            org_name=item.org.name,
            org_path=item.org.org_path,
        )

        next_url = page.next_url
        if next_url:
            if next_url == page_item.page_url:
                next_url = None
            else:
                row_exists = store.db.execute(
                    "SELECT COUNT(*) FROM people_page_queue WHERE page_url = ?",
                    (next_url,),
                ).fetchone()
                if row_exists[0] > 0:
                    err_msg = f"Cycle detected: {next_url}"
                    store.mark_pagination_org_error(item.org.dn, err_msg, self._now())
                    store.commit()
                    return "error", err_msg
                elif page_item.page_index >= self.config.max_pages_per_org:
                    err_msg = f"Max pages limit exceeded ({self.config.max_pages_per_org})"
                    store.mark_pagination_org_error(item.org.dn, err_msg, self._now())
                    store.commit()
                    return "error", err_msg

        people_observed = len(page.people)
        people_inserted = 0
        people_deduped = 0
        for person in page.people:
            exist_row = store.db.execute(
                "SELECT COUNT(*) FROM people_index WHERE source_url = ?",
                (person.source_url,),
            ).fetchone()
            if exist_row[0] > 0:
                people_deduped += 1
            else:
                people_inserted += 1
            store.upsert_person(person, self.config.run_id, seen_at)

        if self.config.crawl_kind == "full" and page_item.page_index == 1:
            for child in extract_org_children(
                page_html,
                item.org.dn,
                item.org.department_dn,
                item.org.org_path,
                item.org.depth,
            ):
                store.upsert_org_unit(child, self.config.run_id, seen_at)
                if (
                    self.config.max_depth is None
                    or child.depth <= self.config.max_depth
                ):
                    store.enqueue_org(child, item.department_name)

        store.complete_people_page(
            page_url=page_item.page_url,
            next_url=next_url,
            people_observed=people_observed,
            people_inserted=people_inserted,
            people_deduped=people_deduped,
            completed_at=seen_at,
        )
        store.commit()

        try:
            self._log_progress(
                store,
                fetcher.stats.request_count,
                "done",
                f"{item.org.org_path} (p.{page_item.page_index})",
                item.org.depth,
            )
        except Exception:
            pass

        return ("next" if next_url else "terminal"), None

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
