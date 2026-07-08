from __future__ import annotations

import json
import threading
from urllib.error import HTTPError
from urllib.request import urlopen, Request
import pytest

from geds_crawler.control_store import ControlStore
from geds_crawler.ui_server import create_server
from geds_crawler.models import Department


@pytest.fixture
def running_control_server(tmp_path):
    control_db = tmp_path / "control.sqlite"
    with ControlStore(control_db) as store:
        store.init_schema()
        # Seed catalog
        catalog = [
            Department(name="Shared Services Canada", dn="OU=SSC-SPC,O=GC,C=CA", source_url="url1"),
            Department(name="ISED", dn="OU=ISED-ISDE,O=GC,C=CA", source_url="url2"),
        ]
        store.upsert_catalog(catalog)
        
    server = create_server(control_db, "127.0.0.1", 0)
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
        return response.status, json.load(response), response.headers


def _post_json(url, data):
    body = json.dumps(data).encode("utf-8")
    req = Request(url, data=body, headers={"Content-Type": "application/json"})
    with urlopen(req, timeout=2) as response:
        return response.status, json.load(response), response.headers


def test_control_overview_and_catalog(running_control_server):
    status_code, data, headers = _get_json(f"{running_control_server}/api/control/overview")
    assert status_code == 200
    assert "active_workers" in data
    assert "configured_rps" in data
    assert "measured_rps" in data


def test_control_job_mutations_and_schedules(running_control_server):
    # 1. Create a job
    job_data = {
        "name": "CRTC Job",
        "department_dns": ["OU=SSC-SPC,O=GC,C=CA"],
        "rate_limit_seconds": 1.5,
        "traffic_policy": "queue",
        "output_dir": "/tmp/crtc",
    }
    status, data, headers = _post_json(f"{running_control_server}/api/control/jobs", job_data)
    
    assert status == 200
    assert "job_id" in data
    # Verify the unauthenticated warning in response
    assert "warning" in data
    assert "unauthenticated" in data["warning"]
    
    # 2. List jobs
    status_get, jobs_list, _ = _get_json(f"{running_control_server}/api/control/jobs")
    assert status_get == 200
    assert len(jobs_list) == 1
    assert jobs_list[0]["name"] == "CRTC Job"


def test_control_run_mutations(running_control_server):
    # Create a job first
    job_data = {
        "name": "SSC Job",
        "department_dns": ["OU=SSC-SPC,O=GC,C=CA"],
        "rate_limit_seconds": 1.0,
        "traffic_policy": "independent",
        "output_dir": "/tmp/ssc",
    }
    _, job_resp, _ = _post_json(f"{running_control_server}/api/control/jobs", job_data)
    job_id = job_resp["job_id"]
    
    # Create a run
    status, run_resp, _ = _post_json(f"{running_control_server}/api/control/runs", {"job_id": job_id})
    assert status == 200
    run_id = run_resp["run_id"]
    
    # Stop the run
    status_stop, stop_resp, _ = _post_json(f"{running_control_server}/api/control/runs/{run_id}/stop", {})
    assert status_stop == 200
    assert stop_resp["status"] == "stopping"
