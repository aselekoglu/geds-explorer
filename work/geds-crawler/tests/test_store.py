import sqlite3

from geds_crawler.models import OrgUnit, PaginationTarget
from geds_crawler.store import SnapshotStore


def test_sqlite_schema_excludes_contact_columns(tmp_path):
    db_path = tmp_path / "geds.sqlite"

    with SnapshotStore(db_path) as store:
        store.init_schema()

    con = sqlite3.connect(db_path)
    columns = {
        row[1]
        for table in ("departments", "org_units", "people_index")
        for row in con.execute(f"PRAGMA table_info({table})")
    }

    assert "phone" not in columns
    assert "telephone" not in columns
    assert "email" not in columns
    assert "fax" not in columns
    assert "source_url" in columns


def test_crawl_queue_tracks_pending_and_done_without_resetting_completed_items(tmp_path):
    db_path = tmp_path / "geds.sqlite"
    org = OrgUnit(
        name="Shared Services Canada",
        dn="OU=SSC-SPC,O=GC,C=CA",
        parent_dn=None,
        department_dn="OU=SSC-SPC,O=GC,C=CA",
        depth=0,
        org_path="Shared Services Canada",
        source_url="https://geds-sage.gc.ca/en/GEDS?pgid=014&dn=T1U9U1NDLVNQQyxPPUdDLEM9Q0E%3D",
    )

    with SnapshotStore(db_path) as store:
        store.init_schema()
        store.enqueue_org(org, "Shared Services Canada")
        next_item = store.next_pending_org()
        assert next_item is not None
        assert next_item.org.dn == org.dn
        assert next_item.department_name == "Shared Services Canada"

        store.mark_org_done(org.dn)
        store.enqueue_org(org, "Shared Services Canada")

        assert store.next_pending_org() is None


def test_store_updates_live_run_request_count(tmp_path):
    db_path = tmp_path / "geds.sqlite"

    with SnapshotStore(db_path) as store:
        store.init_schema()
        store.db.execute(
            "INSERT INTO crawl_runs (id, started_at, request_count, status) VALUES (?, ?, ?, ?)",
            ("run-1", "2026-07-08T12:00:00+00:00", 0, "running"),
        )
        store.update_run_progress("run-1", request_count=7, status="running")
        store.commit()

    con = sqlite3.connect(db_path)
    row = con.execute("SELECT request_count, status FROM crawl_runs WHERE id = ?", ("run-1",)).fetchone()

    assert row == (7, "running")


def make_pagination_target(org_dn: str) -> PaginationTarget:
    return PaginationTarget(
        org=OrgUnit(
            name="Team",
            dn=org_dn,
            parent_dn=None,
            department_dn="OU=DEPT,O=GC,C=CA",
            depth=0,
            org_path="Dept / Team",
            source_url="https://geds-sage.gc.ca/en/GEDS?dn=" + org_dn + "&pgid=014",
        ),
        department_name="Dept",
        base_db_path="base.sqlite",
        base_people_count=25,
    )


def test_pagination_schema_tracks_fixed_org_targets_and_page_queue(tmp_path):
    with SnapshotStore(tmp_path / "geds.sqlite") as store:
        store.init_schema()
        tables = {
            row[0] for row in store.db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        assert {"pagination_orgs", "people_page_queue"} <= tables


def test_page_completion_and_next_enqueue_are_atomic_and_idempotent(tmp_path):
    page_1 = "https://geds-sage.gc.ca/en/GEDS?dn=team&page=1&pgid=014"
    page_2 = "https://geds-sage.gc.ca/en/GEDS?dn=team&page=2&pgid=014"
    now = "2026-07-09T00:00:00+00:00"
    target = make_pagination_target(org_dn="OU=TEAM,O=GC,C=CA")
    with SnapshotStore(tmp_path / "geds.sqlite") as store:
        store.init_schema()
        store.seed_pagination_target(target, now)
        store.enqueue_people_page(target.org.dn, page_1, 1, None, now)
        store.complete_people_page(
            page_url=page_1,
            next_url=page_2,
            people_observed=25,
            people_inserted=20,
            people_deduped=5,
            completed_at=now,
        )
        store.complete_people_page(
            page_url=page_1,
            next_url=page_2,
            people_observed=25,
            people_inserted=20,
            people_deduped=5,
            completed_at=now,
        )
        assert store.pagination_metrics()["pages_fetched"] == 1
        assert store.pagination_metrics()["known_pending_pages"] == 1
        assert store.pagination_metrics()["new_people"] == 20

        # Test terminal success/error increments organization numerator only once
        store.mark_pagination_org_success(target.org.dn, "done", now)
        progress1 = store.pagination_progress()
        assert progress1["completed_orgs"] == 1
        assert progress1["failed_orgs"] == 0
        assert progress1["percent"] == 100.0

        store.mark_pagination_org_success(target.org.dn, "done", now)
        progress2 = store.pagination_progress()
        assert progress2["completed_orgs"] == 1
        assert progress2["percent"] == 100.0
