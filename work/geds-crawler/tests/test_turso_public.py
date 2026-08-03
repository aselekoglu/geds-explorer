from __future__ import annotations

import sys
from pathlib import Path


API_DIR = Path(__file__).parents[2] / "geds-career-atlas" / "api"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))


def test_turso_search_uses_safe_prefix_fts_query():
    import turso_public

    assert turso_public._match_query("Cyber & Data") == '"cyber"* AND "data"*'


def test_turso_search_hydrates_fts_organization_rows():
    import turso_public

    class Result:
        def __init__(self, rows):
            self.rows = rows

        def fetchall(self):
            return self.rows

    class Connection:
        def execute(self, sql, params=()):
            if "career_entities_fts" in sql:
                return Result([{"entity_id": "org:org-1", "title": "", "organization_name": "Cybersecurity", "ancestor_text": ""}])
            return Result([{"org_id": "org-1", "name": "Cybersecurity", "department_name": "Parks Canada"}])

    active = {
        "snapshot_id": "snapshot-1",
        "quality_status": "partial_overlay",
        "taxonomy_version": "1.0.0",
    }
    result = turso_public._turso_search(Connection(), "cyber", 20, active)

    assert result["items"][0]["entity_id"] == "org:org-1"
    assert result["items"][0]["organization_name"] == "Cybersecurity"
    assert result["quality_status"] == "partial_overlay"
