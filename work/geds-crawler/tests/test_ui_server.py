from __future__ import annotations

import json
import threading
from urllib.error import HTTPError
from urllib.request import urlopen

import pytest

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
    legacy_metrics_index = body.index('id="legacy-metrics-section"')
    active_db_index = body.index('id="active-db"')

    assert explore_index < legacy_metrics_index
    assert explore_index < active_db_index
    assert 'id="workspace-operate-overview"' in body
    overview_chunk = body[
        body.index('id="workspace-operate-overview"') : body.index('id="workspace-operate-crawlers"')
    ]
    assert 'id="active-db"' not in overview_chunk


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
