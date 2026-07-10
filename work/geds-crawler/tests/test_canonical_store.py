import sqlite3
from dataclasses import FrozenInstanceError

import pytest

from geds_crawler.canonical_models import (
    CanonicalDepartment,
    CanonicalOrganization,
    CanonicalPerson,
    CanonicalQuality,
    CanonicalSnapshot,
    CanonicalSource,
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


def test_store_materializes_source_and_current_entity_tables(tmp_path):
    with CanonicalStore(tmp_path / "master.sqlite") as store:
        store.init_schema()

        assert {
            "canonical_snapshot_sources",
            "departments_current",
            "organizations_current",
            "people_current",
        } <= store.table_names()
        assert {
            "idx_org_current_parent_name",
            "idx_org_current_department_depth",
            "idx_people_current_org_title",
            "idx_people_current_department",
        } <= store.index_names()


def test_init_schema_upgrades_legacy_people_projection_before_indexing(tmp_path):
    db_path = tmp_path / "master.sqlite"
    with sqlite3.connect(db_path) as con:
        con.execute(
            """
            CREATE TABLE people_current (
              source_url TEXT PRIMARY KEY,
              display_name TEXT NOT NULL,
              title TEXT,
              org_path TEXT NOT NULL,
              snapshot_id TEXT NOT NULL,
              missing_streak INTEGER NOT NULL DEFAULT 0,
              presence_status TEXT NOT NULL DEFAULT 'present'
            )
            """
        )

    with CanonicalStore(db_path) as store:
        store.init_schema()
        columns = {
            row["name"]
            for row in store.db.execute("PRAGMA table_info(people_current)")
        }

        assert {"org_dn", "department_dn", "canonical_path_json"} <= columns
        assert "idx_people_current_org_title" in store.index_names()


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


def test_source_lineage_round_trips(tmp_path):
    source = CanonicalSource(
        snapshot_id="s1",
        source_path="C:/data/base.sqlite",
        source_role="base",
        precedence=0,
        source_sha256="sha256:base",
    )
    with CanonicalStore(tmp_path / "master.sqlite") as store:
        store.init_schema()
        with store.transaction():
            store.insert_snapshot(_snapshot("s1", None))
            store.insert_sources([source])

        row = store.db.execute(
            "SELECT snapshot_id, source_path, source_role, precedence, source_sha256 "
            "FROM canonical_snapshot_sources"
        ).fetchone()

    assert tuple(row) == (
        source.snapshot_id,
        source.source_path,
        source.source_role,
        source.precedence,
        source.source_sha256,
    )


def test_replace_current_projection_materializes_all_entities(tmp_path):
    snapshot = _snapshot("s1", None)
    department, organization, person = _projection("s1")
    with CanonicalStore(tmp_path / "master.sqlite") as store:
        store.init_schema()
        with store.transaction():
            store.insert_snapshot(snapshot)
            store.replace_current_projection(
                [department],
                [organization],
                [person],
            )
            store.set_current_snapshot(snapshot.snapshot_id)

        assert store.current_manifest()["snapshot_id"] == "s1"
        assert store.db.execute(
            "SELECT department_id FROM departments_current"
        ).fetchone()[0] == department.department_id
        org_row = store.db.execute(
            "SELECT org_id, direct_people_count, canonical_path_json "
            "FROM organizations_current"
        ).fetchone()
        assert tuple(org_row) == (
            organization.org_id,
            organization.direct_people_count,
            '["Department","Team"]',
        )
        person_row = store.db.execute(
            "SELECT source_url, org_dn, department_name FROM people_current"
        ).fetchone()
        assert tuple(person_row) == (
            person.source_url,
            person.org_dn,
            person.department_name,
        )


def test_projection_and_pointer_rollback_together(tmp_path):
    snapshot = _snapshot("s1", None)
    projection = _projection("s1")
    with CanonicalStore(tmp_path / "master.sqlite") as store:
        store.init_schema()
        with pytest.raises(RuntimeError):
            with store.transaction():
                store.insert_snapshot(snapshot)
                store.replace_current_projection(
                    [projection[0]],
                    [projection[1]],
                    [projection[2]],
                )
                store.set_current_snapshot(snapshot.snapshot_id)
                raise RuntimeError("abort")

        assert store.current_snapshot() is None
        assert store.db.execute(
            "SELECT COUNT(*) FROM organizations_current"
        ).fetchone()[0] == 0


def test_current_manifest_exposes_quality_warnings(tmp_path):
    snapshot = CanonicalSnapshot(
        snapshot_id="s1",
        parent_snapshot_id=None,
        as_of_at="2026-07-09T00:00:00+00:00",
        source_fingerprint="sha256:quality",
        people_count=1,
        org_units_count=1,
        departments_count=1,
        baseline=True,
        quality_status="partial_overlay",
        quality_warnings=("partial_overlay_base_fallback:org",),
        fallback_org_count=1,
        root_count=1,
        missing_parent_count=0,
        cycle_count=0,
        max_depth=0,
    )
    with CanonicalStore(tmp_path / "master.sqlite") as store:
        store.init_schema()
        with store.transaction():
            store.insert_snapshot(snapshot)
            store.set_current_snapshot(snapshot.snapshot_id)

        assert store.current_manifest()["quality_status"] == "partial_overlay"
        assert store.quality_warnings() == (
            "partial_overlay_base_fallback:org",
        )


def test_canonical_quality_blocks_cycles_and_missing_parents():
    quality = CanonicalQuality(
        status="invalid",
        warnings=(),
        fallback_org_count=0,
        root_count=1,
        missing_parent_count=2,
        cycle_count=3,
        max_depth=4,
    )

    assert quality.has_blocking_errors is True
    assert quality.describe() == "missing_parents=2, cycles=3"


def _projection(
    snapshot_id: str,
) -> tuple[CanonicalDepartment, CanonicalOrganization, CanonicalPerson]:
    department = CanonicalDepartment(
        department_id="department-id",
        dn="OU=Department,O=GC,C=CA",
        name="Department",
        source_url="https://example.test/department",
        snapshot_id=snapshot_id,
    )
    organization = CanonicalOrganization(
        org_id="organization-id",
        dn="OU=Team,OU=Department,O=GC,C=CA",
        name="Team",
        parent_dn=department.dn,
        department_dn=department.dn,
        depth=1,
        canonical_path=("Department", "Team"),
        source_url="https://example.test/team",
        snapshot_id=snapshot_id,
        direct_people_count=1,
        descendant_people_count=1,
        child_count=0,
        descendant_org_count=0,
    )
    person = CanonicalPerson(
        source_url="https://example.test/person",
        display_name="Ada Lovelace",
        title="Analyst",
        org_dn=organization.dn,
        department_dn=department.dn,
        department_name=department.name,
        org_unit=organization.name,
        canonical_path=organization.canonical_path,
        last_seen_at="2026-07-09T00:00:00+00:00",
        snapshot_id=snapshot_id,
    )
    return department, organization, person
