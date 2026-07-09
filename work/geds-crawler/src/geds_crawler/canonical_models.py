from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CanonicalSnapshot:
    snapshot_id: str
    parent_snapshot_id: str | None
    captured_at: str
    member_count: int


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
