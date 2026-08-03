"""Explicit Turso entrypoint; the existing Neon ``index.py`` stays unchanged."""

from __future__ import annotations

import os
import sys
from typing import Any

from fastapi import HTTPException

API_DIR = os.path.dirname(__file__)
if API_DIR not in sys.path:
    sys.path.insert(0, API_DIR)

import index as _public
from turso_backend import TursoConnection, TursoError


def _schema() -> str:
    value = os.environ.get("GEDS_PUBLIC_PROJECTION_SCHEMA", "main")
    if value != "main":
        raise RuntimeError("Turso projection must use the main SQLite schema")
    return value


def _connect():
    url = os.environ.get("GEDS_PUBLIC_TURSO_DATABASE_URL") or os.environ.get("TURSO_DATABASE_URL")
    token = os.environ.get("GEDS_PUBLIC_TURSO_AUTH_TOKEN") or os.environ.get("TURSO_AUTH_TOKEN")
    if not url or not token:
        raise HTTPException(503, "Turso public database is not configured")
    try:
        return TursoConnection(url, token)
    except TursoError as exc:
        raise HTTPException(503, "Turso public database is unavailable") from exc


def _active(con) -> dict[str, Any]:
    if not isinstance(con, TursoConnection):
        raise HTTPException(503, "Turso public database is unavailable")
    row = con.execute(
        """SELECT snapshot_id,taxonomy_version,quality_status,as_of_at,
                  people_count,org_units_count,departments_count,
                  projection_version,release_kind,publishable
           FROM public_meta WHERE singleton=1"""
    ).fetchone()
    if row is None:
        raise HTTPException(503, "public projection is not active")
    snapshot_id = str(row["snapshot_id"])
    return {
        "release_id": snapshot_id,
        "snapshot_id": snapshot_id,
        "as_of_at": row["as_of_at"],
        "quality_status": row["quality_status"],
        "release_kind": row["release_kind"],
        "publishable": bool(row["publishable"]),
        "taxonomy_version": row["taxonomy_version"],
        "departments_count": int(row["departments_count"]),
        "organizations_count": int(row["org_units_count"]),
        "people_count": int(row["people_count"]),
        "career_entities_count": None,
        "projection_version": row["projection_version"],
        "schema_version": "geds-public.v1",
    }


_public._schema = _schema
_public._connect = _connect
_public._active = _active
app = _public.app
