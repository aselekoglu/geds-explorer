from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Job:
    id: str
    name: str
    created_at: str
    rate_limit_seconds: float
    traffic_policy: str
    output_dir: str
    enabled: bool = True


@dataclass(frozen=True)
class CrawlRun:
    id: str
    job_id: str | None
    started_at: str
    finished_at: str | None
    status: str
    request_count: int
    pid: int | None
    stop_requested: bool
    output_dir: str


@dataclass(frozen=True)
class Schedule:
    id: str
    job_id: str
    expression: str
    timezone: str
    overlap_policy: str
    enabled: bool
    next_run_at: str | None
