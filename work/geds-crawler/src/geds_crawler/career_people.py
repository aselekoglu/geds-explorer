from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from urllib.parse import urlparse


ALLOWED_GROUPS = frozenset({"EC", "CO", "IT", "CS"})
CLASSIFICATION_RE = re.compile(r"(?<![A-Z0-9])(EC|CO|IT|CS)[- ]?(\d{1,2})(?!\d)", re.IGNORECASE)
OFFICIAL_GEDS_HOST = "geds-sage.gc.ca"


def extract_observed_classifications(title: str | None) -> tuple[str, ...]:
    values: list[str] = []
    for group, level in CLASSIFICATION_RE.findall(title or ""):
        normalized = f"{group.upper()}-{int(level):02d}"
        if normalized not in values:
            values.append(normalized)
    return tuple(values)


def official_geds_url(value: str | None) -> str:
    parsed = urlparse(value or "")
    if parsed.scheme == "https" and parsed.hostname == OFFICIAL_GEDS_HOST:
        return value or ""
    return ""


def public_person_id(source_url: str) -> str:
    return hashlib.sha256(source_url.encode("utf-8")).hexdigest()[:20]


@dataclass(frozen=True)
class PublicPerson:
    person_id: str
    display_name: str
    observed_title: str
    observed_classifications: tuple[str, ...]
    org_id: str
    organization_name: str
    snapshot_id: str
    snapshot_as_of: str
    source_url: str


@dataclass(frozen=True)
class PeoplePage:
    items: tuple[PublicPerson, ...]
    total: int
    limit: int
    offset: int
    available_classifications: tuple[str, ...]
    snapshot_id: str
    quality_status: str
    etag: str
