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
    with urlopen(f"{running_server}/", timeout=2) as response:
        body = response.read().decode("utf-8")

    assert body.lower().startswith("<!doctype html>")
    assert "GEDS Snapshot Monitor" in body or "GEDS" in body
    assert "/api/status" in body


def test_dashboard_contains_pagination_elements(running_server):
    with urlopen(f"{running_server}/", timeout=2) as response:
        body = response.read().decode("utf-8")
    assert "job-crawl-kind" in body
    assert "job-source-db" in body
    assert "pagination-orgs-panel" in body
    assert "formatDurationRange" in body
    assert "formatRunEta" in body


def test_unknown_route_returns_json_404(running_server):
    with pytest.raises(HTTPError) as exc:
        urlopen(f"{running_server}/not-found", timeout=2)

    assert exc.value.code == 404
    assert json.loads(exc.value.read()) == {"error": "Not found"}
