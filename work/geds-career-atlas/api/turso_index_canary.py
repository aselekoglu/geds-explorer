"""Preview-only Turso entrypoint with a fixed SQLite main schema."""

from __future__ import annotations

import os
import sys

API_DIR = os.path.dirname(__file__)
if API_DIR not in sys.path:
    sys.path.insert(0, API_DIR)

import turso_index as _turso


def _schema() -> str:
    return "main"


_turso._public._schema = _schema
app = _turso.app


@app.middleware("http")
async def _normalize_vercel_function_path(request, call_next):
    """Map Vercel's Python-function prefix to the app's existing /api routes."""
    path = request.scope.get("path", "")
    prefix = "/api/turso_index_canary"
    if path == prefix or path.startswith(prefix + "/"):
        path = path[len(prefix):] or "/"
    if not path.startswith("/api/") and path != "/api":
        path = "/api" + path
    request.scope["path"] = path
    return await call_next(request)
