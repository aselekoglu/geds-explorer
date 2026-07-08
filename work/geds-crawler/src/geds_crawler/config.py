from __future__ import annotations

from dataclasses import dataclass, field


BASE_URL = "https://geds-sage.gc.ca"
GEDS_PATH = "/en/GEDS"
DEPARTMENT_LIST_URL = f"{BASE_URL}{GEDS_PATH}?pgid=012"

DEFAULT_DEPARTMENTS = {
    "Shared Services Canada",
    "Treasury Board of Canada Secretariat",
    "Innovation Science and Economic Development Canada",
    "Employment and Social Development Canada",
    "Canada Revenue Agency",
    "Public Services and Procurement Canada",
    "Statistics Canada",
    "National Research Council Canada",
    "Natural Resources Canada",
    "National Defence",
}


@dataclass(frozen=True)
class CrawlConfig:
    allowed_departments: set[str] = field(default_factory=lambda: set(DEFAULT_DEPARTMENTS))
    rate_limit_seconds: float = 1.0
    retry_delays_seconds: tuple[float, ...] = (2.0, 5.0, 15.0)
    user_agent: str = "GEDS Explorer research crawler/0.1 (+polite snapshot; no contact storage)"
