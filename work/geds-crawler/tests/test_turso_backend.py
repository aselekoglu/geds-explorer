from __future__ import annotations

import importlib.util
from pathlib import Path


API_DIR = Path(__file__).parents[2] / "geds-career-atlas" / "api"


def _module():
    spec = importlib.util.spec_from_file_location("geds_turso_backend", API_DIR / "turso_backend.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_adapt_sql_translates_public_postgres_contract_to_sqlite():
    module = _module()
    sql = "SELECT p.name FROM geds_public.people_current p WHERE p.release_id=%s AND p.name ILIKE %s"

    assert module.adapt_sql(sql) == (
        "SELECT p.name FROM main.people_current p "
        "WHERE p.snapshot_id=? AND LOWER(p.name) LIKE LOWER(?)"
    )


def test_turso_result_behaves_like_the_api_rows():
    module = _module()
    result = module.TursoResult([{"id": 1}, {"id": 2}])

    assert result.fetchone() == {"id": 1}
    assert result.fetchall() == [{"id": 2}]
    assert result.fetchone() is None
