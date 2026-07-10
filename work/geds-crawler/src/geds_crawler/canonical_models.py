from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CanonicalSnapshot:
    snapshot_id: str
    parent_snapshot_id: str | None
    as_of_at: str
    source_fingerprint: str
    people_count: int
    org_units_count: int
    departments_count: int
    baseline: bool
    quality_status: str = "complete"
    quality_warnings: tuple[str, ...] = ()
    fallback_org_count: int = 0
    root_count: int = 0
    missing_parent_count: int = 0
    cycle_count: int = 0
    max_depth: int = 0


@dataclass(frozen=True)
class SnapshotMember:
    snapshot_id: str
    source_url: str
    display_name: str
    title: str | None
    org_path: str


@dataclass(frozen=True)
class CurrentPerson:
    source_url: str
    display_name: str
    title: str | None
    org_path: str
    snapshot_id: str


@dataclass(frozen=True)
class PersonChangeEvent:
    snapshot_id: str
    person_key: str
    event_type: str
    occurred_at: str
    details_json: str


@dataclass(frozen=True)
class CanonicalOrganization:
    org_id: str
    dn: str
    name: str
    parent_dn: str | None
    department_dn: str
    depth: int
    canonical_path: tuple[str, ...]
    source_url: str
    snapshot_id: str = ""
    direct_people_count: int = 0
    descendant_people_count: int = 0
    child_count: int = 0
    descendant_org_count: int = 0


@dataclass(frozen=True)
class HierarchyQuality:
    root_count: int
    missing_parent_count: int
    cycle_count: int
    max_depth: int


@dataclass(frozen=True)
class CanonicalSource:
    snapshot_id: str
    source_path: str
    source_role: str
    precedence: int
    source_sha256: str


@dataclass(frozen=True)
class CanonicalDepartment:
    department_id: str
    dn: str
    name: str
    source_url: str
    snapshot_id: str


@dataclass(frozen=True)
class CanonicalPerson:
    source_url: str
    display_name: str
    title: str | None
    org_dn: str
    department_dn: str
    department_name: str
    org_unit: str
    canonical_path: tuple[str, ...]
    last_seen_at: str
    snapshot_id: str


@dataclass(frozen=True)
class CanonicalQuality:
    status: str
    warnings: tuple[str, ...]
    fallback_org_count: int
    root_count: int
    missing_parent_count: int
    cycle_count: int
    max_depth: int

    @property
    def has_blocking_errors(self) -> bool:
        return self.missing_parent_count > 0 or self.cycle_count > 0

    def describe(self) -> str:
        details: list[str] = []
        if self.missing_parent_count:
            details.append(f"missing_parents={self.missing_parent_count}")
        if self.cycle_count:
            details.append(f"cycles={self.cycle_count}")
        return ", ".join(details) or self.status
