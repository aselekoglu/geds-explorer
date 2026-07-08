from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Department:
    name: str
    dn: str
    source_url: str


@dataclass(frozen=True)
class OrgUnit:
    name: str
    dn: str
    parent_dn: str | None
    department_dn: str
    depth: int
    org_path: str
    source_url: str


@dataclass(frozen=True)
class PersonIndex:
    display_name: str
    title: str | None
    org_dn: str
    department_dn: str
    department_name: str
    org_unit: str
    org_path: str
    source_url: str


@dataclass(frozen=True)
class ParsedLink:
    pgid: str
    dn: str
    url: str


@dataclass(frozen=True)
class CrawlError:
    url: str
    error: str
    attempts: int


@dataclass(frozen=True)
class QueueItem:
    org: OrgUnit
    department_name: str
