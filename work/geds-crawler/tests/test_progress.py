import sqlite3

from geds_crawler.cli import main
from geds_crawler.models import OrgUnit
from geds_crawler.progress import format_progress_line, read_snapshot_status
from geds_crawler.store import SnapshotStore


def test_read_snapshot_status_counts_core_tables_and_queue_states(tmp_path):
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
        store.db.execute(
            "INSERT INTO crawl_runs (id, started_at, request_count, status) VALUES (?, ?, ?, ?)",
            ("run-1", "2026-07-08T12:00:00+00:00", 42, "running"),
        )
        store.enqueue_org(org, "Shared Services Canada")
        store.commit()

    status = read_snapshot_status(db_path)

    assert status.departments == 0
    assert status.org_units == 0
    assert status.people == 0
    assert status.errors == 0
    assert status.request_count == 42
    assert status.queue == {"pending": 1}
    assert status.run_status == "running"


def test_format_progress_line_names_current_org_and_counts():
    line = format_progress_line(
        event="done",
        org_path="Shared Services Canada / Cloud Services",
        depth=1,
        request_count=15,
        org_count=94,
        people_count=222,
        queue_done=14,
        queue_pending=80,
        error_count=0,
    )

    assert "done" in line
    assert "requests=15" in line
    assert "orgs=94" in line
    assert "people=222" in line
    assert "done=14" in line
    assert "pending=80" in line
    assert 'org="Shared Services Canada / Cloud Services"' in line


def test_status_command_reports_missing_database_without_traceback(tmp_path, capsys):
    missing = tmp_path / "missing.sqlite"

    exit_code = main(["status", "--db", str(missing)])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "Database not found" in captured.err
    assert str(missing.resolve()) in captured.err
