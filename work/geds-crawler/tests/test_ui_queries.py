from __future__ import annotations

from datetime import UTC, datetime

from geds_crawler.models import Department, OrgUnit, PersonIndex
from geds_crawler.store import SnapshotStore
from geds_crawler.ui_queries import SnapshotReader


def _create_snapshot(db_path):
    now = datetime.now(UTC).isoformat()
    run_id = "test-run"
    department = Department(
        name="Shared Services Canada",
        dn="dc=ssc,dc=gc,dc=ca",
        source_url="https://geds-sage.gc.ca/en/GEDS?pgid=014&dn=dc%3Dssc",
    )
    org = OrgUnit(
        name="Application Development",
        dn="ou=development,dc=ssc,dc=gc,dc=ca",
        parent_dn=department.dn,
        department_dn=department.dn,
        depth=1,
        org_path="Shared Services Canada / Application Development",
        source_url="https://geds-sage.gc.ca/en/GEDS?pgid=014&dn=ou%3Ddevelopment",
    )
    person = PersonIndex(
        display_name="Ada Example",
        title="Senior Software Developer",
        org_dn=org.dn,
        department_dn=department.dn,
        department_name=department.name,
        org_unit=org.name,
        org_path=org.org_path,
        source_url="https://geds-sage.gc.ca/en/GEDS?pgid=015&dn=uid%3Dada",
    )

    with SnapshotStore(db_path) as store:
        store.init_schema()
        store.db.execute(
            "INSERT INTO crawl_runs (id, started_at, request_count, status) VALUES (?, ?, ?, ?)",
            (run_id, now, 42, "running"),
        )
        store.upsert_department(department, run_id, now)
        store.upsert_org_unit(org, run_id, now)
        store.upsert_person(person, run_id, now)
        store.enqueue_org(org, department.name)
        store.db.execute(
            """
            INSERT INTO crawl_errors (url, error, attempts, created_at, crawl_run_id)
            VALUES (?, ?, ?, ?, ?)
            """,
            (org.source_url, "temporary failure", 3, now, run_id),
        )
        store.commit()


def test_status_and_department_options(tmp_path):
    db_path = tmp_path / "snapshot.sqlite"
    _create_snapshot(db_path)

    reader = SnapshotReader(db_path)

    assert reader.status() == {
        "run_status": "running",
        "request_count": 42,
        "departments": 1,
        "org_units": 1,
        "people": 1,
        "errors": 1,
        "queue": {"pending": 1},
        "completion_percent": 0.0,
    }
    assert reader.departments() == ["Shared Services Canada"]


def test_people_search_is_filtered_paginated_and_contact_free(tmp_path):
    db_path = tmp_path / "snapshot.sqlite"
    _create_snapshot(db_path)
    reader = SnapshotReader(db_path)

    result = reader.people(
        query="developer",
        department="Shared Services Canada",
        limit=25,
        offset=0,
    )

    assert result["total"] == 1
    assert result["limit"] == 25
    assert result["offset"] == 0
    assert set(result["items"][0]) == {
        "display_name",
        "title",
        "department_name",
        "org_unit",
        "org_path",
        "source_url",
    }
    assert reader.people(query="missing", limit=25, offset=0)["total"] == 0


def test_org_queue_and_error_queries(tmp_path):
    db_path = tmp_path / "snapshot.sqlite"
    _create_snapshot(db_path)
    reader = SnapshotReader(db_path)

    assert reader.orgs(query="application", limit=10, offset=0)["total"] == 1
    assert reader.queue(status="pending", limit=10, offset=0)["total"] == 1
    assert reader.errors(query="temporary", limit=10, offset=0)["total"] == 1


def test_limit_is_bounded(tmp_path):
    db_path = tmp_path / "snapshot.sqlite"
    _create_snapshot(db_path)

    result = SnapshotReader(db_path).people(limit=10_000, offset=-4)

    assert result["limit"] == 100
    assert result["offset"] == 0
