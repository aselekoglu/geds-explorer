import sqlite3

from geds_crawler.models import OrgUnit
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
