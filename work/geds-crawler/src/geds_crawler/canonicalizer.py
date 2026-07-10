from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, replace
from datetime import datetime
from pathlib import Path

from .canonical_hierarchy import (
    derive_hierarchy,
    stable_org_id,
    validate_hierarchy,
)
from .canonical_models import (
    CanonicalDepartment,
    CanonicalOrganization,
    CanonicalPerson,
    CanonicalQuality,
    CanonicalSnapshot,
    CanonicalSource,
    PersonChangeEvent,
)
from .canonical_resolver import (
    CanonicalValidationError,
    ResolvedSnapshot,
    resolve_completed_run,
)
from .canonical_store import CanonicalStore


@dataclass(frozen=True)
class PromotionResult:
    snapshot: CanonicalSnapshot
    event_counts: dict[str, int]


def publish_canonical(
    control_db: Path | str,
    run_id: str,
    master_db: Path | str,
    as_of_at: str | datetime,
) -> PromotionResult:
    resolved = resolve_completed_run(Path(control_db), run_id)
    return promote_canonical_snapshot(master_db, resolved, as_of_at)


def promote_canonical_snapshot(
    master_db: Path | str,
    resolved: ResolvedSnapshot,
    as_of_at: str | datetime,
) -> PromotionResult:
    """Validate and atomically publish a complete current projection."""

    as_of = as_of_at.isoformat() if isinstance(as_of_at, datetime) else str(as_of_at)
    raw_departments = tuple(resolved.iter_departments())
    raw_orgs = tuple(resolved.iter_orgs())
    raw_people = tuple(resolved.iter_people())
    hierarchy = derive_hierarchy(raw_orgs)
    hierarchy_quality = validate_hierarchy(hierarchy)
    quality = CanonicalQuality(
        status=(
            "partial_overlay"
            if resolved.quality.fallback_org_dns
            else "complete"
        ),
        warnings=resolved.quality.warnings,
        fallback_org_count=len(resolved.quality.fallback_org_dns),
        root_count=hierarchy_quality.root_count,
        missing_parent_count=hierarchy_quality.missing_parent_count,
        cycle_count=hierarchy_quality.cycle_count,
        max_depth=hierarchy_quality.max_depth,
    )
    if quality.has_blocking_errors:
        raise CanonicalValidationError(quality.describe())

    org_by_dn = {org.dn.casefold(): org for org in hierarchy}
    for person in raw_people:
        org_dn = str(person.get("org_dn") or "").casefold()
        if org_dn not in org_by_dn:
            raise CanonicalValidationError(
                "Person references an organization outside the canonical "
                f"projection: {person.get('source_url')}"
            )

    source_rows = _source_rows(resolved)
    fingerprint = _fingerprint(
        raw_departments,
        hierarchy,
        raw_people,
        source_rows,
        quality,
    )

    with CanonicalStore(master_db) as store:
        store.init_schema()
        parent_id = store.current_snapshot()
        snapshot_id = hashlib.sha256(
            f"{as_of}|{fingerprint}|{parent_id or ''}".encode("utf-8")
        ).hexdigest()
        departments = tuple(
            CanonicalDepartment(
                department_id=stable_org_id(str(row["dn"])),
                dn=str(row["dn"]),
                name=str(row.get("name") or "").strip(),
                source_url=str(row.get("source_url") or "").strip(),
                snapshot_id=snapshot_id,
            )
            for row in raw_departments
        )
        people = tuple(
            _canonical_person(row, org_by_dn, snapshot_id, as_of)
            for row in raw_people
        )
        organizations = _organizations_with_counts(
            hierarchy,
            people,
            snapshot_id,
        )
        snapshot = CanonicalSnapshot(
            snapshot_id=snapshot_id,
            parent_snapshot_id=parent_id,
            as_of_at=as_of,
            source_fingerprint=fingerprint,
            people_count=len(people),
            org_units_count=len(organizations),
            departments_count=len(departments),
            baseline=parent_id is None,
            quality_status=quality.status,
            quality_warnings=quality.warnings,
            fallback_org_count=quality.fallback_org_count,
            root_count=quality.root_count,
            missing_parent_count=quality.missing_parent_count,
            cycle_count=quality.cycle_count,
            max_depth=quality.max_depth,
        )
        sources = tuple(
            CanonicalSource(
                snapshot_id=snapshot_id,
                source_path=row["source_path"],
                source_role=row["source_role"],
                precedence=row["precedence"],
                source_sha256=row["source_sha256"],
            )
            for row in source_rows
        )
        current = {person.source_url: person for person in people}
        events: list[PersonChangeEvent] = []
        counts: Counter[str] = Counter()
        with store.transaction():
            previous_rows = store.db.execute(
                "SELECT * FROM people_current"
            ).fetchall()
            previous = {
                str(row["source_url"]): dict(row)
                for row in previous_rows
            }
            if parent_id is not None:
                _record_present_events(
                    snapshot_id,
                    as_of,
                    current,
                    previous,
                    events,
                    counts,
                )
                _record_missing_events(
                    snapshot_id,
                    as_of,
                    current,
                    previous,
                    events,
                    counts,
                )
            store.insert_snapshot(snapshot)
            store.insert_sources(sources)
            store.replace_current_projection(
                departments,
                organizations,
                people,
            )
            _restore_missing_people(store, snapshot_id, current, previous)
            store.append_events(events)
            store.set_current_snapshot(snapshot_id)
        return PromotionResult(snapshot, dict(counts))


def _canonical_person(
    row: dict,
    org_by_dn: dict[str, CanonicalOrganization],
    snapshot_id: str,
    as_of: str,
) -> CanonicalPerson:
    org = org_by_dn[str(row["org_dn"]).casefold()]
    return CanonicalPerson(
        source_url=str(row["source_url"]),
        display_name=str(row.get("display_name") or ""),
        title=row.get("title"),
        org_dn=org.dn,
        department_dn=str(row.get("department_dn") or org.department_dn),
        department_name=str(row.get("department_name") or ""),
        org_unit=str(row.get("org_unit") or org.name),
        canonical_path=org.canonical_path,
        last_seen_at=str(row.get("last_seen") or as_of),
        snapshot_id=snapshot_id,
    )


def _organizations_with_counts(
    organizations: tuple[CanonicalOrganization, ...],
    people: tuple[CanonicalPerson, ...],
    snapshot_id: str,
) -> tuple[CanonicalOrganization, ...]:
    direct_people = Counter(person.org_dn.casefold() for person in people)
    children: dict[str, list[str]] = defaultdict(list)
    by_key = {org.dn.casefold(): org for org in organizations}
    for org in organizations:
        if org.parent_dn is not None:
            children[org.parent_dn.casefold()].append(org.dn.casefold())

    totals: dict[str, tuple[int, int]] = {}

    def subtree(key: str) -> tuple[int, int]:
        cached = totals.get(key)
        if cached is not None:
            return cached
        descendant_people = direct_people.get(key, 0)
        descendant_orgs = 0
        for child in children.get(key, ()):
            child_people, child_orgs = subtree(child)
            descendant_people += child_people
            descendant_orgs += child_orgs + 1
        totals[key] = (descendant_people, descendant_orgs)
        return totals[key]

    materialized: list[CanonicalOrganization] = []
    for key in sorted(by_key):
        org = by_key[key]
        descendant_people, descendant_orgs = subtree(key)
        materialized.append(
            replace(
                org,
                snapshot_id=snapshot_id,
                direct_people_count=direct_people.get(key, 0),
                descendant_people_count=descendant_people,
                child_count=len(children.get(key, ())),
                descendant_org_count=descendant_orgs,
            )
        )
    return tuple(materialized)


def _record_present_events(
    snapshot_id: str,
    as_of: str,
    current: dict[str, CanonicalPerson],
    previous: dict[str, dict],
    events: list[PersonChangeEvent],
    counts: Counter[str],
) -> None:
    for key, person in current.items():
        old = previous.get(key)
        after = asdict(person)
        if old is None:
            _append_event(
                events,
                counts,
                snapshot_id,
                key,
                "joined",
                as_of,
                {"before": None, "after": after},
            )
            continue
        if old.get("presence_status") != "present":
            _append_event(
                events,
                counts,
                snapshot_id,
                key,
                "reappeared",
                as_of,
                {"before": old, "after": after},
            )
            continue
        changes: list[str] = []
        if old.get("title") != person.title:
            changes.append("title_changed")
        if str(old.get("org_dn") or "").casefold() != person.org_dn.casefold():
            changes.append("org_changed")
        if (
            str(old.get("department_dn") or "").casefold()
            != person.department_dn.casefold()
        ):
            changes.append("department_changed")
        details = {"before": old, "after": after}
        for event_type in changes:
            _append_event(
                events,
                counts,
                snapshot_id,
                key,
                event_type,
                as_of,
                details,
            )
        if "department_changed" in changes:
            _append_event(
                events,
                counts,
                snapshot_id,
                key,
                "possible_move",
                as_of,
                {**details, "uncertain": True},
            )


def _record_missing_events(
    snapshot_id: str,
    as_of: str,
    current: dict[str, CanonicalPerson],
    previous: dict[str, dict],
    events: list[PersonChangeEvent],
    counts: Counter[str],
) -> None:
    for key, old in previous.items():
        if key in current:
            continue
        streak = int(old.get("missing_streak") or 0)
        event_type = "departed" if streak >= 1 else "missing_once"
        _append_event(
            events,
            counts,
            snapshot_id,
            key,
            event_type,
            as_of,
            {"before": old, "after": None},
        )


def _append_event(
    events: list[PersonChangeEvent],
    counts: Counter[str],
    snapshot_id: str,
    person_key: str,
    event_type: str,
    as_of: str,
    details: dict,
) -> None:
    events.append(
        PersonChangeEvent(
            snapshot_id,
            person_key,
            event_type,
            as_of,
            json.dumps(
                details,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
        )
    )
    counts[event_type] += 1


def _restore_missing_people(
    store: CanonicalStore,
    snapshot_id: str,
    current: dict[str, CanonicalPerson],
    previous: dict[str, dict],
) -> None:
    for key, old in previous.items():
        if key in current:
            continue
        store.db.execute(
            """
            INSERT INTO people_current
              (source_url, display_name, title, org_path, org_dn, department_dn,
               department_name, org_unit, canonical_path_json, last_seen_at,
               snapshot_id, missing_streak, presence_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'missing')
            """,
            (
                key,
                old["display_name"],
                old["title"],
                old["org_path"],
                old.get("org_dn") or "",
                old.get("department_dn") or "",
                old.get("department_name") or "",
                old.get("org_unit") or "",
                old.get("canonical_path_json") or "[]",
                old.get("last_seen_at") or "",
                snapshot_id,
                int(old.get("missing_streak") or 0) + 1,
            ),
        )


def _source_rows(resolved: ResolvedSnapshot) -> tuple[dict, ...]:
    rows: list[dict] = []
    precedence = 0
    for role, paths in (
        ("base", resolved.base_db_paths),
        ("overlay", resolved.overlay_db_paths),
    ):
        for path in paths:
            resolved_path = Path(path).resolve()
            rows.append(
                {
                    "source_path": str(resolved_path),
                    "source_role": role,
                    "precedence": precedence,
                    "source_sha256": _sha256_file(resolved_path),
                }
            )
            precedence += 1
    return tuple(rows)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _fingerprint(
    departments: tuple[dict, ...],
    organizations: tuple[CanonicalOrganization, ...],
    people: tuple[dict, ...],
    sources: tuple[dict, ...],
    quality: CanonicalQuality,
) -> str:
    payload = {
        "departments": sorted(
            (
                {
                    "dn": str(row["dn"]),
                    "name": str(row.get("name") or ""),
                    "source_url": str(row.get("source_url") or ""),
                }
                for row in departments
            ),
            key=lambda row: row["dn"].casefold(),
        ),
        "organizations": [
            {
                "dn": org.dn,
                "name": org.name,
                "parent_dn": org.parent_dn,
                "department_dn": org.department_dn,
                "canonical_path": org.canonical_path,
                "source_url": org.source_url,
            }
            for org in organizations
        ],
        "people": sorted(
            (
                {
                    "source_url": str(row["source_url"]),
                    "display_name": str(row.get("display_name") or ""),
                    "title": row.get("title"),
                    "org_dn": str(row.get("org_dn") or ""),
                    "department_dn": str(row.get("department_dn") or ""),
                }
                for row in people
            ),
            key=lambda row: row["source_url"],
        ),
        "sources": sources,
        "quality": asdict(quality),
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()
