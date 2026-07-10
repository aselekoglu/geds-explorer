from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from geds_crawler.canonical_resolver import (
    CanonicalValidationError,
    resolve_completed_run,
)
from geds_crawler.models import Department, OrgUnit, PersonIndex
from geds_crawler.store import SnapshotStore


def _create_snapshot(path: Path, person_name: str, source_suffix: str) -> None:
    department = Department("Department", "dc=department", "https://example.test/dept")
    org = OrgUnit(
        name="Organization",
        dn="ou=organization,dc=department",
        parent_dn=None,
        department_dn=department.dn,
        depth=1,
        org_path="Department / Organization",
        source_url="https://example.test/org",
    )
    person = PersonIndex(
        display_name=person_name,
        title="Title",
        org_dn=org.dn,
        department_dn=department.dn,
        department_name=department.name,
        org_unit=org.name,
        org_path=org.org_path,
        source_url=f"https://example.test/people/{source_suffix}",
    )
    with SnapshotStore(path) as store:
        store.init_schema()
        store.db.execute(
            "INSERT INTO crawl_runs (id, started_at, status) VALUES (?, ?, ?)",
            (f"run-{source_suffix}", "2026-07-09T00:00:00+00:00", "finished"),
        )
        store.upsert_department(department, f"run-{source_suffix}", "2026-07-09T00:00:00+00:00")
        store.upsert_org_unit(org, f"run-{source_suffix}", "2026-07-09T00:00:00+00:00")
        store.upsert_person(person, f"run-{source_suffix}", "2026-07-09T00:00:00+00:00")
        store.commit()


def _create_control_run(
    control_db: Path,
    run_id: str,
    output_dir: Path | str,
    base_paths: list[Path],
) -> None:
    control_db.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(control_db) as con:
        con.executescript(
            """
            CREATE TABLE crawl_runs (
                id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                crawl_kind TEXT NOT NULL,
                output_dir TEXT NOT NULL
            );
            CREATE TABLE run_pagination_seeds (
                run_id TEXT NOT NULL,
                org_dn TEXT NOT NULL,
                base_db_path TEXT NOT NULL
            );
            """
        )
        con.execute(
            "INSERT INTO crawl_runs (id, status, crawl_kind, output_dir) VALUES (?, ?, ?, ?)",
            (run_id, "finished", "pagination_backfill", str(output_dir)),
        )
        for index, base_path in enumerate(base_paths):
            con.execute(
                "INSERT INTO run_pagination_seeds (run_id, org_dn, base_db_path) VALUES (?, ?, ?)",
                (run_id, f"ou=organization-{index}", str(base_path)),
            )


def _insert_pagination_org(overlay: Path, status: str) -> None:
    with sqlite3.connect(overlay) as con:
        con.execute(
            """
            INSERT INTO pagination_orgs (
                org_dn, department_dn, department_name, org_name, org_path, source_url,
                base_db_path, base_people_count, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "ou=organization,dc=department",
                "dc=department",
                "Department",
                "Organization",
                "Department / Organization",
                "https://example.test/org",
                "base.sqlite",
                25,
                status,
            ),
        )


def _completed_backfill_with_two_bases(tmp_path):
    control_db = tmp_path / "control.sqlite"
    run_id = "backfill-run"
    base_one = tmp_path / "base-one.sqlite"
    base_two = tmp_path / "base-two.sqlite"
    output_dir = tmp_path / "output"
    overlay = output_dir / "geds.sqlite"
    output_dir.mkdir()

    _create_snapshot(base_one, "Base One", "base-one")
    _create_snapshot(base_two, "Base Two", "base-two")
    _create_snapshot(overlay, "Overlay", "overlay")
    _insert_pagination_org(overlay, "completed")
    _create_control_run(control_db, run_id, output_dir, [base_two, base_one, base_one])
    return control_db, run_id, base_one, base_two, overlay


def _backfill_with_pending_page(tmp_path):
    control_db = tmp_path / "control.sqlite"
    run_id = "backfill-run"
    base = tmp_path / "base.sqlite"
    output_dir = tmp_path / "output"
    overlay = output_dir / "staging.sqlite"
    output_dir.mkdir()

    _create_snapshot(base, "Base", "base")
    _create_snapshot(overlay, "Overlay", "overlay")
    _insert_pagination_org(overlay, "pending")
    _create_control_run(control_db, run_id, output_dir, [base])
    return control_db, run_id


def test_resolve_completed_backfill_uses_every_distinct_seed_base(tmp_path):
    control_db, run_id, base_one, base_two, overlay = _completed_backfill_with_two_bases(tmp_path)
    resolved = resolve_completed_run(control_db, run_id)
    assert resolved.base_db_paths == (base_one.resolve(), base_two.resolve())
    assert resolved.overlay_db_paths == (overlay.resolve(),)
    assert resolved.reader().people(limit=10)["total"] == 3


def test_resolver_rejects_incomplete_backfill(tmp_path):
    control_db, run_id = _backfill_with_pending_page(tmp_path)
    with pytest.raises(CanonicalValidationError, match="not complete"):
        resolve_completed_run(control_db, run_id)


def test_resolver_rejects_failed_backfill(tmp_path):
    control_db, run_id = _backfill_with_pending_page(tmp_path)
    with sqlite3.connect(tmp_path / "output" / "staging.sqlite") as con:
        con.execute("UPDATE pagination_orgs SET status = 'failed'")

    with pytest.raises(CanonicalValidationError, match="not complete"):
        resolve_completed_run(control_db, run_id)


def test_resolver_rejects_backfill_without_pagination_organizations(tmp_path):
    control_db = tmp_path / "control.sqlite"
    base = tmp_path / "base.sqlite"
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    _create_snapshot(base, "Base", "base")
    _create_snapshot(output_dir / "geds.sqlite", "Overlay", "overlay")
    _create_control_run(control_db, "backfill-run", output_dir, [base])

    with pytest.raises(CanonicalValidationError, match="no pagination organizations"):
        resolve_completed_run(control_db, "backfill-run")


def test_resolver_rejects_base_without_required_snapshot_tables(tmp_path):
    control_db = tmp_path / "control.sqlite"
    base = tmp_path / "base.sqlite"
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    with sqlite3.connect(base) as con:
        con.execute("CREATE TABLE unrelated (id INTEGER PRIMARY KEY)")
    _create_snapshot(output_dir / "geds.sqlite", "Overlay", "overlay")
    _insert_pagination_org(output_dir / "geds.sqlite", "completed")
    _create_control_run(control_db, "backfill-run", output_dir, [base])

    with pytest.raises(CanonicalValidationError, match="missing required tables"):
        resolve_completed_run(control_db, "backfill-run")


def test_resolver_rejects_zero_byte_base_database(tmp_path):
    control_db = tmp_path / "control.sqlite"
    base = tmp_path / "base.sqlite"
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    base.touch()
    _create_snapshot(output_dir / "geds.sqlite", "Overlay", "overlay")
    _insert_pagination_org(output_dir / "geds.sqlite", "completed")
    _create_control_run(control_db, "backfill-run", output_dir, [base])

    with pytest.raises(CanonicalValidationError, match="missing required tables"):
        resolve_completed_run(control_db, "backfill-run")


def test_resolver_rejects_invalid_preferred_output_database(tmp_path):
    control_db = tmp_path / "control.sqlite"
    base = tmp_path / "base.sqlite"
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    _create_snapshot(base, "Base", "base")
    (output_dir / "geds.sqlite").write_text("not a sqlite database", encoding="utf-8")
    _create_snapshot(output_dir / "staging.sqlite", "Fallback", "fallback")
    _insert_pagination_org(output_dir / "staging.sqlite", "completed")
    _create_control_run(control_db, "backfill-run", output_dir, [base])

    with pytest.raises(CanonicalValidationError, match="invalid output database"):
        resolve_completed_run(control_db, "backfill-run")


def test_resolver_resolves_relative_output_from_project_root_not_cwd(tmp_path, monkeypatch):
    project_root = tmp_path / "project"
    control_db = project_root / "control" / "state" / "control.sqlite"
    base = project_root / "snapshots" / "base.sqlite"
    output_dir = project_root / "outputs" / "backfill"
    output_dir.mkdir(parents=True)
    _create_snapshot(base, "Base", "base")
    overlay = output_dir / "geds.sqlite"
    _create_snapshot(overlay, "Overlay", "overlay")
    _insert_pagination_org(overlay, "completed")
    _create_control_run(control_db, "backfill-run", Path("outputs") / "backfill", [base])
    monkeypatch.chdir(tmp_path)

    resolved = resolve_completed_run(control_db, "backfill-run")

    assert resolved.overlay_db_paths == (overlay.resolve(),)
