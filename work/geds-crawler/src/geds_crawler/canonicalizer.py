from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .canonical_models import CanonicalSnapshot, CurrentPerson, PersonChangeEvent, SnapshotMember
from .canonical_resolver import ResolvedSnapshot
from .canonical_store import CanonicalStore


@dataclass(frozen=True)
class PromotionResult:
    snapshot: CanonicalSnapshot
    event_counts: dict[str, int]


def promote_canonical_snapshot(
    master_db: Path | str, resolved: ResolvedSnapshot, as_of_at: str | datetime
) -> PromotionResult:
    """Validate and atomically promote a resolved source snapshot."""
    as_of = as_of_at.isoformat() if isinstance(as_of_at, datetime) else str(as_of_at)
    reader = resolved.reader()
    status = reader.status()
    people_rows: list[dict] = []
    offset = 0
    while True:
        page = reader.people(limit=100, offset=offset)
        people_rows.extend(page["items"])
        if len(people_rows) >= int(page["total"]):
            break
        offset += len(page["items"])
    if int(status["people"]) != len(people_rows):
        raise ValueError(f"people count mismatch: status={status['people']} rows={len(people_rows)}")

    normalized = []
    for row in people_rows:
        normalized.append({
            "source_url": str(row["source_url"]),
            "display_name": str(row.get("display_name") or ""),
            "title": row.get("title"),
            "org_path": str(row.get("org_path") or ""),
        })
    normalized.sort(key=lambda p: p["source_url"])
    fingerprint = "sha256:" + hashlib.sha256(
        json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()

    with CanonicalStore(master_db) as store:
        store.init_schema()
        parent_id = store.current_snapshot()
        snapshot_id = hashlib.sha256(f"{as_of}|{fingerprint}|{parent_id or ''}".encode()).hexdigest()
        snapshot = CanonicalSnapshot(
            snapshot_id=snapshot_id,
            parent_snapshot_id=parent_id,
            as_of_at=as_of,
            source_fingerprint=fingerprint,
            people_count=len(normalized),
            org_units_count=int(status["org_units"]),
            departments_count=int(status["departments"]),
            baseline=parent_id is None,
        )
        members = [SnapshotMember(snapshot_id, p["source_url"], p["display_name"], p["title"], p["org_path"]) for p in normalized]
        current = {p["source_url"]: p for p in normalized}
        events: list[PersonChangeEvent] = []
        counts: dict[str, int] = {}
        with store.transaction():
            previous_rows = store.db.execute("SELECT source_url, display_name, title, org_path FROM people_current").fetchall()
            previous = {r["source_url"]: dict(r) for r in previous_rows}
            if parent_id is not None:
                historical_rows = store.db.execute(
                    "SELECT source_url, display_name, title, org_path FROM canonical_snapshot_members GROUP BY source_url",
                ).fetchall()
                for row in historical_rows:
                    previous.setdefault(row["source_url"], dict(row))
                for key, person in current.items():
                    old = previous.get(key)
                    event_type = None
                    if old is None:
                        # A person seen before but absent in the immediate projection has reappeared.
                        prior = store.db.execute("SELECT 1 FROM person_change_events WHERE person_key=? AND event_type IN ('missing_once','departed') LIMIT 1", (key,)).fetchone()
                        event_type = "reappeared" if prior else "joined"
                    elif old["title"] != person["title"]:
                        event_type = "title_changed"
                    elif old["org_path"] != person["org_path"]:
                        event_type = "org_changed"
                    if event_type:
                        before = old
                        after = person
                        details = json.dumps({"before": before, "after": after}, sort_keys=True)
                        events.append(PersonChangeEvent(snapshot_id, key, event_type, as_of, details))
                        counts[event_type] = counts.get(event_type, 0) + 1
                        if old and old["org_path"] != person["org_path"] and _department(old["org_path"]) != _department(person["org_path"]):
                            dept_details = json.dumps({"before": before, "after": after}, sort_keys=True)
                            events.append(PersonChangeEvent(snapshot_id, key, "department_changed", as_of, dept_details))
                            counts["department_changed"] = counts.get("department_changed", 0) + 1
                            details = json.dumps({"before": before, "after": after, "uncertain": True}, sort_keys=True)
                            events.append(PersonChangeEvent(snapshot_id, key, "possible_move", as_of, details))
                            counts["possible_move"] = counts.get("possible_move", 0) + 1
                for key, old in previous.items():
                    if key not in current:
                        prior = store.db.execute("SELECT event_type FROM person_change_events WHERE person_key=? ORDER BY id DESC LIMIT 1", (key,)).fetchone()
                        event_type = "departed" if prior and prior["event_type"] == "missing_once" else "missing_once"
                        details = json.dumps({"before": old, "after": None}, sort_keys=True)
                        events.append(PersonChangeEvent(snapshot_id, key, event_type, as_of, details))
                        counts[event_type] = counts.get(event_type, 0) + 1
            store.insert_snapshot(snapshot, members)
            store.replace_current_people(CurrentPerson(p["source_url"], p["display_name"], p["title"], p["org_path"], snapshot_id) for p in normalized)
            store.append_events(events)
            store.set_current_snapshot(snapshot_id)
        return PromotionResult(snapshot, counts)


def _department(path: str) -> str:
    return path.split(" / ", 1)[0].strip()
