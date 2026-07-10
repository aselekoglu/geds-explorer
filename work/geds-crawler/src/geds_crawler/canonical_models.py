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
