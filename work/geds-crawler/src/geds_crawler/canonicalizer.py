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
    org_count = int(reader.orgs(limit=1, offset=0)["total"])
    dept_count = len(reader.departments())

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
            org_units_count=org_count,
            departments_count=dept_count,
            baseline=parent_id is None,
        )
        members = [SnapshotMember(snapshot_id, p["source_url"], p["display_name"], p["title"], p["org_path"]) for p in normalized]
        current = {p["source_url"]: p for p in normalized}
        events: list[PersonChangeEvent] = []
        counts: dict[str, int] = {}
        with store.transaction():
            previous_rows = store.db.execute("SELECT source_url, display_name, title, org_path, missing_streak, presence_status FROM people_current").fetchall()
            previous = {r["source_url"]: dict(r) for r in previous_rows}
            if parent_id is not None:
                for key, person in current.items():
                    old = previous.get(key)
                    event_type = None
                    if old is None:
                        # A person seen before but absent in the immediate projection has reappeared.
                        event_type = "reappeared" if old is not None and old.get("presence_status") == "missing" else "joined"
                        details = json.dumps({"before": None, "after": person}, sort_keys=True)
                        events.append(PersonChangeEvent(snapshot_id, key, event_type, as_of, details))
                        counts[event_type] = counts.get(event_type, 0) + 1
                    elif old["title"] != person["title"] or old["org_path"] != person["org_path"]:
                        before = old
                        after = person
                        changed = []
                        if old["title"] != person["title"]:
                            changed.append("title_changed")
                        if old["org_path"] != person["org_path"]:
                            changed.append("org_changed")
                        if old["org_path"] != person["org_path"] and _department(old["org_path"]) != _department(person["org_path"]):
                            changed.append("department_changed")
                        details = json.dumps({"before": before, "after": after}, sort_keys=True)
                        for event_type in changed:
                            events.append(PersonChangeEvent(snapshot_id, key, event_type, as_of, details))
                            counts[event_type] = counts.get(event_type, 0) + 1
                        if "department_changed" in changed:
                            details = json.dumps({"before": before, "after": after, "uncertain": True}, sort_keys=True)
                            events.append(PersonChangeEvent(snapshot_id, key, "possible_move", as_of, details))
                            counts["possible_move"] = counts.get("possible_move", 0) + 1
                for key, old in previous.items():
                    if key not in current:
                        streak = int(old.get("missing_streak") or 0)
                        event_type = "departed" if streak >= 1 else "missing_once"
                        details = json.dumps({"before": old, "after": None}, sort_keys=True)
                        events.append(PersonChangeEvent(snapshot_id, key, event_type, as_of, details))
                        counts[event_type] = counts.get(event_type, 0) + 1
            store.insert_snapshot(snapshot, members)
            store.replace_current_people(CurrentPerson(p["source_url"], p["display_name"], p["title"], p["org_path"], snapshot_id) for p in normalized)
            for key, old in previous.items():
                if key not in current:
                    store.db.execute("INSERT OR REPLACE INTO people_current(source_url,display_name,title,org_path,snapshot_id,missing_streak,presence_status) VALUES(?,?,?,?,?,?,?)", (key, old["display_name"], old["title"], old["org_path"], snapshot_id, int(old.get("missing_streak") or 0)+1, "missing"))
            store.append_events(events)
            store.set_current_snapshot(snapshot_id)
        return PromotionResult(snapshot, counts)


def _department(path: str) -> str:
    return path.split(" / ", 1)[0].strip()
