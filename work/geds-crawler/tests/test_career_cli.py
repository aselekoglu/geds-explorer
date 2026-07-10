from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from geds_crawler.career_cli import main
from geds_crawler.models import Department, OrgUnit, PersonIndex, PaginationTarget
from geds_crawler.store import SnapshotStore


def test_publish_command_writes_master_and_reports_manifest(tmp_path, capsys):
    base = tmp_path / "base.sqlite"
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    overlay = output_dir / "geds.sqlite"
    control_db = tmp_path / "control.sqlite"
    run_id = "backfill-run"
    department = Department(
        "Department",
        "OU=Department,O=GC,C=CA",
        "https://example.test/department",
    )
    organization = OrgUnit(
        "Team",
        f"OU=Team,{department.dn}",
        department.dn,
        department.dn,
        1,
        "Department / Team",
        "https://example.test/team",
    )
    _create_snapshot(base, department, organization, "base-person")
    _create_snapshot(overlay, department, organization, "overlay-person")
    with SnapshotStore(overlay) as store:
        store.seed_pagination_target(
            PaginationTarget(
                organization,
                department.name,
                str(base),
                1,
            ),
            "2026-07-10T00:00:00+00:00",
        )
        store.db.execute(
            "UPDATE pagination_orgs SET status='completed' WHERE org_dn=?",
            (organization.dn,),
        )
        store.commit()
    _create_control(control_db, run_id, output_dir, base, organization.dn)
    master = tmp_path / "master.sqlite"

    code = main(
        [
            "publish",
            "--control-db",
            str(control_db),
            "--run-id",
            run_id,
            "--master-db",
            str(master),
            "--as-of",
            "2026-07-10T00:00:00+00:00",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["snapshot_id"]
    assert payload["people_count"] == 1
    assert payload["org_units_count"] == 1
    assert payload["departments_count"] == 1
    assert payload["quality_status"] == "complete"
    assert master.is_file()


def _create_snapshot(
    path: Path,
    department: Department,
    organization: OrgUnit,
    person_url: str,
) -> None:
    with SnapshotStore(path) as store:
        store.init_schema()
        store.db.execute(
            "INSERT INTO crawl_runs (id, started_at, status) VALUES (?,?,?)",
            ("run", "2026-07-10T00:00:00+00:00", "finished"),
        )
        store.upsert_department(
            department,
            "run",
            "2026-07-10T00:00:00+00:00",
        )
        store.upsert_org_unit(
            organization,
            "run",
            "2026-07-10T00:00:00+00:00",
        )
        store.upsert_person(
            PersonIndex(
                "Ada Lovelace",
                "Analyst",
                organization.dn,
                department.dn,
                department.name,
                organization.name,
                organization.org_path,
                person_url,
            ),
            "run",
            "2026-07-10T00:00:00+00:00",
        )
        store.commit()


def _create_control(
    path: Path,
    run_id: str,
    output_dir: Path,
    base: Path,
    org_dn: str,
) -> None:
    with sqlite3.connect(path) as con:
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
            "INSERT INTO crawl_runs VALUES (?,?,?,?)",
            (run_id, "finished", "pagination_backfill", str(output_dir)),
        )
        con.execute(
            "INSERT INTO run_pagination_seeds VALUES (?,?,?)",
            (run_id, org_dn, str(base)),
        )
