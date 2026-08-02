from __future__ import annotations

import importlib.util
from pathlib import Path

from fastapi.testclient import TestClient


API_PATH = Path(__file__).parents[2] / "geds-career-atlas" / "api" / "index.py"


def _api_module():
    spec = importlib.util.spec_from_file_location("geds_vercel_api_contract", API_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_vercel_api_exposes_same_origin_get_routes_without_database_secret(monkeypatch):
    monkeypatch.delenv("GEDS_PUBLIC_DATABASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    module = _api_module()

    routes = {route.path for route in module.app.routes}
    assert "/api/meta" in routes
    assert "/api/search" in routes
    assert "/api/orgs/{org_id}/people" in routes
    response = TestClient(module.app).get("/api/meta")
    assert response.status_code == 503
    assert response.json() == {"detail": "public database is not configured"}
