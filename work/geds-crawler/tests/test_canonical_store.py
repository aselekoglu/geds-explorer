from dataclasses import FrozenInstanceError

import pytest

from geds_crawler.canonical_models import (
    CanonicalSnapshot,
    CurrentPerson,
    PersonChangeEvent,
    SnapshotMember,
)
from geds_crawler.canonical_store import CanonicalStore


def _snapshot(snapshot_id: str, parent_snapshot_id: str | None) -> CanonicalSnapshot:
    return CanonicalSnapshot(
        snapshot_id=snapshot_id,
        parent_snapshot_id=parent_snapshot_id,
        as_of_at="2026-07-09T00:00:00+00:00",
        source_fingerprint="sha256:empty",
        people_count=0,
        org_units_count=0,
        departments_count=0,
        baseline=False,
    )


def test_failed_transaction_does_not_advance_current_snapshot(tmp_path):
    with CanonicalStore(tmp_path / "master.sqlite") as store:
        store.init_schema()
        with pytest.raises(RuntimeError):
            with store.transaction():
                store.insert_snapshot(_snapshot("s1", None))
                store.set_current_snapshot("s1")
                raise RuntimeError("abort")
        assert store.current_snapshot() is None


def test_event_indexes_support_person_timeline(tmp_path):
    with CanonicalStore(tmp_path / "master.sqlite") as store:
        store.init_schema()
        assert {
            "idx_person_change_events_person_time",
            "idx_person_change_events_snapshot_type",
        } <= store.index_names()


def test_canonical_models_are_immutable():
    snapshot = _snapshot("s1", None)

    with pytest.raises(FrozenInstanceError):
        snapshot.snapshot_id = "s2"  # type: ignore[misc]


def test_replacing_current_people_replaces_only_the_current_projection(tmp_path):
    member = SnapshotMember(
        snapshot_id="s1",
        source_url="https://example.test/people/1",
        display_name="Ada Lovelace",
        title="Analyst",
        org_path="Department / Team",
    )
    person = CurrentPerson(
        source_url=member.source_url,
        display_name=member.display_name,
        title=member.title,
        org_path=member.org_path,
        snapshot_id="s1",
    )
    replacement = CurrentPerson(
        source_url="https://example.test/people/2",
        display_name="Grace Hopper",
        title=None,
        org_path="Department / Other Team",
        snapshot_id="s1",
    )

    with CanonicalStore(tmp_path / "master.sqlite") as store:
        store.init_schema()
        with store.transaction():
            store.insert_snapshot(_snapshot("s1", None), [member])
            store.replace_current_people([person])
            store.replace_current_people([replacement])

        rows = store.db.execute(
            "SELECT source_url, display_name FROM people_current ORDER BY source_url"
        ).fetchall()
        assert [tuple(row) for row in rows] == [(replacement.source_url, replacement.display_name)]
        assert store.db.execute(
            "SELECT source_url FROM canonical_snapshot_members"
        ).fetchone()[0] == member.source_url


def test_appending_events_preserves_person_timeline(tmp_path):
    event = PersonChangeEvent(
        snapshot_id="s1",
        person_key="https://example.test/people/1",
        event_type="added",
        occurred_at="2026-07-09T00:00:00+00:00",
        details_json='{"display_name":"Ada Lovelace"}',
    )

    with CanonicalStore(tmp_path / "master.sqlite") as store:
        store.init_schema()
        with store.transaction():
            store.insert_snapshot(_snapshot("s1", None))
            store.append_events([event])

        row = store.db.execute(
            "SELECT snapshot_id, person_key, event_type, occurred_at, details_json "
            "FROM person_change_events"
        ).fetchone()
        assert tuple(row) == (
            event.snapshot_id,
            event.person_key,
            event.event_type,
            event.occurred_at,
            event.details_json,
        )


def test_full_snapshot_manifest_round_trips_through_storage(tmp_path):
    snapshot = CanonicalSnapshot(
        snapshot_id="s1",
        parent_snapshot_id=None,
        as_of_at="2026-07-09T00:00:00+00:00",
        source_fingerprint="sha256:abc123",
        people_count=11,
        org_units_count=4,
        departments_count=2,
        baseline=True,
    )
    db_path = tmp_path / "master.sqlite"

    with CanonicalStore(db_path) as store:
        store.init_schema()
        with store.transaction():
            store.insert_snapshot(snapshot)

    with CanonicalStore(db_path) as store:
        row = store.db.execute(
            """
            SELECT snapshot_id, parent_snapshot_id, as_of_at, source_fingerprint,
                   people_count, org_units_count, departments_count, baseline
            FROM canonical_snapshots
            WHERE snapshot_id = ?
            """,
            (snapshot.snapshot_id,),
        ).fetchone()

    reloaded = CanonicalSnapshot(
        snapshot_id=row["snapshot_id"],
        parent_snapshot_id=row["parent_snapshot_id"],
        as_of_at=row["as_of_at"],
        source_fingerprint=row["source_fingerprint"],
        people_count=row["people_count"],
        org_units_count=row["org_units_count"],
        departments_count=row["departments_count"],
        baseline=bool(row["baseline"]),
    )

    assert reloaded == snapshot
