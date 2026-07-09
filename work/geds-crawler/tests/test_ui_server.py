from __future__ import annotations

import json
import sqlite3
import threading
from urllib.error import HTTPError
from urllib.request import urlopen

import pytest

from geds_crawler.control_store import ControlStore
from geds_crawler.models import Department, OrgUnit, PersonIndex
from geds_crawler.store import SnapshotStore
from geds_crawler.ui_server import create_server
from test_ui_queries import _create_snapshot


@pytest.fixture
def running_server(tmp_path):
    db_path = tmp_path / "snapshot.sqlite"
    _create_snapshot(db_path)
    server = create_server(db_path, "127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def _get_json(url):
    with urlopen(url, timeout=2) as response:
        return response.status, json.load(response)


def _get_root_html(base_url: str) -> str:
    with urlopen(f"{base_url}/", timeout=2) as response:
        assert response.status == 200
        return response.read().decode("utf-8")


def test_status_and_people_endpoints(running_server):
    status_code, status = _get_json(f"{running_server}/api/status")
    people_code, people = _get_json(f"{running_server}/api/people?q=developer")

    assert status_code == 200
    assert status["people"] == 1
    assert people_code == 200
    assert people["total"] == 1
    serialized = json.dumps(people).lower()
    assert "email" not in serialized
    assert "phone" not in serialized


def test_filters_and_pagination_are_parsed(running_server):
    _, queue = _get_json(f"{running_server}/api/queue?status=pending&limit=1&offset=0")
    _, departments = _get_json(f"{running_server}/api/departments")

    assert queue["total"] == 1
    assert queue["limit"] == 1
    assert departments == ["Shared Services Canada"]


def test_root_serves_dashboard_html(running_server):
    body = _get_root_html(running_server)

    assert body.lower().startswith("<!doctype html>")
    assert "GEDS" in body
    assert "/api/status" in body


def test_dashboard_uses_command_center_information_architecture(running_server):
    body = _get_root_html(running_server)

    assert 'class="app-shell"' in body
    assert 'aria-label="Primary workspace navigation"' in body
    assert 'data-route="#/operate/overview"' in body
    assert 'data-route="#/operate/crawlers"' in body
    assert 'data-route="#/operate/history"' in body
    assert 'data-route="#/plan/coverage"' in body
    assert 'data-route="#/plan/schedules"' in body
    assert 'data-route="#/explore/snapshot"' in body
    assert "Operate" in body
    assert "Plan" in body
    assert "Explore Data" in body


def test_dashboard_contains_guided_creation_flows(running_server):
    body = _get_root_html(running_server)

    assert 'id="start-crawler-drawer"' in body
    assert 'aria-modal="true"' in body
    assert 'id="open-start-crawler"' in body
    assert "Select target" in body
    assert "Review estimate" in body
    assert "Configure options" in body
    assert "Confirm start" in body
    assert 'id="new-schedule-drawer"' in body
    assert 'id="open-new-schedule"' in body
    assert "Advanced cron" in body
    assert "Next run preview" in body


def test_dashboard_isolates_snapshot_data_in_explore_workspace(running_server):
    body = _get_root_html(running_server)

    explore_index = body.index('id="workspace-explore-snapshot"')
    legacy_metrics_index = body.index('id="data-explorer-summary"')
    active_db_index = body.index('id="active-db"')
    active_view_index = body.index('id="overview-select-container"')

    assert explore_index < legacy_metrics_index
    assert explore_index < active_db_index
    assert explore_index < active_view_index
    assert 'id="workspace-operate-overview"' in body
    overview_chunk = body[
        body.index('id="workspace-operate-overview"') : body.index('id="workspace-operate-crawlers"')
    ]
    assert 'id="active-db"' not in overview_chunk
    assert 'id="overview-select-container"' not in overview_chunk


def test_snapshot_workspace_is_a_dark_data_explorer(running_server):
    body = _get_root_html(running_server)

    assert 'id="data-explorer-summary"' in body
    assert "Dataset overview" in body
    assert "Browse data" in body
    assert "function updateDataSourceContext()" in body
    assert ".main-stage .workspace," in body
    assert ".main-stage input, .main-stage select {" in body
    assert 'refresh: async () => { await refreshRuns(); await refresh(); }' in body
    assert "snapshotLoading: false" in body
    assert "snapshotRefreshQueued: false" in body
    assert "if (state.snapshotLoading) {" in body


def test_dashboard_wires_hash_routes_and_current_refresh_target(running_server):
    body = _get_root_html(running_server)

    assert 'window.addEventListener("hashchange"' in body
    assert 'window.location.hash = button.dataset.route' in body
    assert 'refreshCurrentRoute().catch' in body
    assert 'function setLastUpdated()' in body
    assert 'id="last-updated"' in body
    assert 'last-refresh' not in body


def test_dashboard_has_accessibility_and_responsive_hooks(running_server):
    body = _get_root_html(running_server)

    assert ":focus-visible" in body
    assert "@media (max-width: 760px)" in body
    assert 'id="mobile-nav-toggle"' in body
    assert 'aria-expanded="false"' in body
    assert 'role="status"' in body
    assert 'aria-live="polite"' in body
    assert "status-label" in body


def test_dashboard_contains_pagination_elements(running_server):
    body = _get_root_html(running_server)
    assert "job-crawl-kind" in body
    assert "job-source-db" in body
    assert "pagination-orgs-panel" in body
    assert "formatDurationRange" in body
    assert "formatRunEta" in body
    assert "pagination_metrics.known_pending_pages" in body
    assert "pagination_metrics.active_org" in body
    assert "pagination_metrics.pages_pending" not in body


def test_unknown_route_returns_json_404(running_server):
    with pytest.raises(HTTPError) as exc:
        urlopen(f"{running_server}/not-found", timeout=2)

    assert exc.value.code == 404
    assert json.loads(exc.value.read()) == {"error": "Not found"}


def _create_finished_source(db_path, code, department_name, person_name):
    department_dn = f"OU={code},O=GC,C=CA"
    org_dn = f"OU=TEAM,OU={code},O=GC,C=CA"
    source_url = f"https://geds-sage.gc.ca/en/GEDS?pgid=014&dn={code}"
    with SnapshotStore(db_path) as store:
        store.init_schema()
        store.db.execute(
            """
            INSERT INTO crawl_runs (id, started_at, finished_at, request_count, status)
            VALUES (?, '2026-07-09T00:00:00+00:00', '2026-07-09T00:01:00+00:00', 1, 'finished')
            """,
            (f"run-{code}",),
        )
        store.upsert_department(
            Department(department_name, department_dn, source_url),
            f"run-{code}",
            "2026-07-09T00:00:00+00:00",
        )
        org = OrgUnit(
            "Team",
            org_dn,
            department_dn,
            department_dn,
            1,
            f"{department_name} / Team",
            source_url,
        )
        store.upsert_org_unit(org, f"run-{code}", "2026-07-09T00:00:00+00:00")
        store.upsert_person(
            PersonIndex(
                person_name,
                "Analyst",
                org_dn,
                department_dn,
                department_name,
                "Team",
                f"{department_name} / Team",
                f"https://geds-sage.gc.ca/en/GEDS?pgid=015&dn={code}-person",
            ),
            f"run-{code}",
            "2026-07-09T00:00:00+00:00",
        )
        store.commit()
    return department_dn, org_dn, source_url


def test_selected_backfill_view_combines_every_frozen_base_database(tmp_path):
    base_one = tmp_path / "base-one.sqlite"
    base_two = tmp_path / "base-two.sqlite"
    dept_one, org_one, url_one = _create_finished_source(
        base_one, "ONE", "Department One", "Person One"
    )
    dept_two, org_two, url_two = _create_finished_source(
        base_two, "TWO", "Department Two", "Person Two"
    )
    output_dir = tmp_path / "backfill"
    overlay = output_dir / "geds.sqlite"
    with SnapshotStore(overlay) as store:
        store.init_schema()
        store.db.execute(
            """
            INSERT INTO crawl_runs (id, started_at, request_count, status)
            VALUES ('backfill-run', '2026-07-09T01:00:00+00:00', 3, 'running')
            """
        )
        store.upsert_person(
            PersonIndex(
                "New Person",
                "Manager",
                org_two,
                dept_two,
                "Department Two",
                "Team",
                "Department Two / Team",
                "https://geds-sage.gc.ca/en/GEDS?pgid=015&dn=new-person",
            ),
            "backfill-run",
            "2026-07-09T01:00:00+00:00",
        )
        store.commit()

    control_db = tmp_path / "control.sqlite"
    with ControlStore(control_db) as control:
        control.init_schema()
        job_id = control.create_job(
            "Mixed Backfill",
            set(),
            1.0,
            "independent",
            str(output_dir),
            crawl_kind="pagination_backfill",
            source_db_path=str(base_one),
        )
        run_id = control.create_run(job_id, status="finished")
        control.db.execute("DELETE FROM run_pagination_seeds WHERE run_id = ?", (run_id,))
        for department_dn, org_dn, source_url, base_path, name in (
            (dept_one, org_one, url_one, base_one, "Department One"),
            (dept_two, org_two, url_two, base_two, "Department Two"),
        ):
            control.db.execute(
                """
                INSERT INTO run_pagination_seeds (
                    run_id, org_dn, source_url, department_dn, department_name,
                    org_name, org_path, base_db_path, base_people_count, seeded_at
                ) VALUES (?, ?, ?, ?, ?, 'Team', ?, ?, 25, '2026-07-09T01:00:00+00:00')
                """,
                (
                    run_id,
                    org_dn,
                    source_url,
                    department_dn,
                    name,
                    f"{name} / Team",
                    str(base_path),
                ),
            )
        control.db.commit()

    with sqlite3.connect(overlay) as stage:
        stage.execute(
            """
            UPDATE crawl_runs
            SET id = ?, heartbeat_at = '2026-07-09T01:02:03+00:00'
            WHERE id = 'backfill-run'
            """,
            (run_id,),
        )
        stage.commit()

    server = create_server(control_db, "127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        root = f"http://127.0.0.1:{server.server_address[1]}"
        _, status = _get_json(f"{root}/api/status?run_id={run_id}")
        _, departments = _get_json(f"{root}/api/departments?run_id={run_id}")
        _, runs = _get_json(f"{root}/api/control/runs")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    assert status["run_status"] == "finished"
    assert status["departments"] == 2
    assert status["org_units"] == 2
    assert status["people"] == 3
    assert departments == ["Department One", "Department Two"]
    selected_run = next(run for run in runs if run["id"] == run_id)
    assert selected_run["heartbeat_at"] == "2026-07-09T01:02:03+00:00"
    assert selected_run["configured_rps"] == 1.0
