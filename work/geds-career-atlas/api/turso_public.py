"""Production Turso entrypoint for the public read API.

The existing ``index.py`` remains the Neon-compatible route implementation.
This module reuses its response contract, swaps the connection/active-release
functions for Turso, and replaces the unbounded LIKE search with bounded FTS5
lookups suitable for the remote SQLite projection.
"""

from __future__ import annotations

import os
import re
import sys
from typing import Any

from fastapi import Query


API_DIR = os.path.dirname(__file__)
if API_DIR not in sys.path:
    sys.path.insert(0, API_DIR)

import turso_index as _turso


_public = _turso._public
app = _turso.app


def _match_query(value: str) -> str:
    tokens = re.findall(r"[\wÀ-ÖØ-öø-ÿ]+", value.casefold(), flags=re.UNICODE)
    return " AND ".join('"' + token.replace('"', '""') + '"*' for token in tokens)


def _turso_search(con: Any, query: str, limit: int, active: dict[str, Any]) -> dict[str, Any]:
    match_query = _match_query(query)
    if not match_query:
        return _public._search_result(
            [], active, limit, "search", query, limit,
            interpretation=_public._direct_interpretation(query, active),
        )

    schema = _public._schema()
    fts_rows = con.execute(
        f"""SELECT entity_id,title,organization_name,ancestor_text
            FROM {schema}.career_entities_fts
            WHERE career_entities_fts MATCH %s
            LIMIT %s""",
        (match_query, limit),
    ).fetchall()
    entity_ids = [str(row["entity_id"]) for row in fts_rows]
    org_ids = [entity_id[4:] for entity_id in entity_ids if entity_id.startswith("org:")]
    person_urls = [entity_id[7:] for entity_id in entity_ids if entity_id.startswith("person:")]

    organizations: dict[str, dict[str, Any]] = {}
    if org_ids:
        placeholders = ",".join("%s" for _ in org_ids)
        rows = con.execute(
            f"""SELECT o.org_id,o.name,d.name AS department_name
                FROM {schema}.organizations_current o
                LEFT JOIN {schema}.departments_current d
                  ON d.snapshot_id=o.snapshot_id AND d.department_dn=o.department_dn
                WHERE o.snapshot_id=%s AND o.org_id IN ({placeholders})""",
            (active["snapshot_id"], *org_ids),
        ).fetchall()
        organizations = {str(row["org_id"]): dict(row) for row in rows}

    people: dict[str, dict[str, Any]] = {}
    if person_urls:
        placeholders = ",".join("%s" for _ in person_urls)
        rows = con.execute(
            f"""SELECT p.source_url,p.display_name,p.title,
                       o.org_id,o.name AS organization_name,
                       COALESCE(p.department_name,d.name,'') AS department_name
                FROM {schema}.people_current p
                LEFT JOIN {schema}.organizations_current o
                  ON o.snapshot_id=p.snapshot_id AND o.org_dn=p.org_dn
                LEFT JOIN {schema}.departments_current d
                  ON d.snapshot_id=p.snapshot_id AND d.department_dn=p.department_dn
                WHERE p.snapshot_id=%s AND p.presence_status='present'
                  AND p.source_url IN ({placeholders})""",
            (active["snapshot_id"], *person_urls),
        ).fetchall()
        people = {str(row["source_url"]): dict(row) for row in rows}

    folded_query = query.casefold()
    items: list[dict[str, Any]] = []
    for fts_row in fts_rows:
        entity_id = str(fts_row["entity_id"])
        if entity_id.startswith("org:"):
            row = organizations.get(entity_id[4:])
            if row is None:
                continue
            name = str(row["name"])
            exact = name.casefold() == folded_query
            source_text = str(fts_row["organization_name"] or fts_row["ancestor_text"] or name)
            items.append(_public._search_item(
                {
                    "entity_id": entity_id,
                    "entity_kind": "organization",
                    "org_id": row["org_id"],
                    "title": "",
                    "organization_name": name,
                    "department_name": row["department_name"],
                },
                1000 if exact else 500,
                [{"field": "organization", "matched_phrase": query, "source_text": source_text, "weight": 500, "category_id": "direct-search"}],
            ))
            continue

        if entity_id.startswith("person:"):
            row = people.get(entity_id[7:])
            if row is None:
                continue
            display_name = str(row["display_name"])
            title = str(row["title"] or "")
            field = "title" if folded_query in title.casefold() else "organization"
            source_text = title if field == "title" else str(row["organization_name"] or "")
            items.append(_public._search_item(
                {
                    "entity_id": entity_id,
                    "entity_kind": "person",
                    "org_id": row["org_id"],
                    "title": title,
                    "organization_name": row["organization_name"],
                    "department_name": row["department_name"],
                    "display_name": display_name,
                    "source_url": row["source_url"],
                },
                1000 if display_name.casefold() == folded_query else 450,
                [{"field": field, "matched_phrase": query, "source_text": source_text, "weight": 450, "category_id": "direct-search"}],
            ))

    return _public._search_result(
        items, active, limit, "search", query, limit,
        interpretation=_public._direct_interpretation(query, active),
    )


for route in list(app.router.routes):
    if getattr(route, "path", None) == "/api/search":
        app.router.routes.remove(route)


@app.get("/api/search")
def search(q: str = Query(min_length=1, max_length=240), limit: int = Query(20, ge=1, le=200)):
    bounded_limit = _public._bounded(limit, _public.MAX_PAGE_SIZE)

    def read(con):
        active = _public._active(con)
        return _turso_search(con, q, bounded_limit, active)

    return _public._read(read)


@app.middleware("http")
async def _normalize_vercel_function_path(request, call_next):
    """Map Vercel's function prefix to the existing /api route contract."""
    path = request.scope.get("path", "")
    prefix = "/api/turso_public"
    if path == prefix or path.startswith(prefix + "/"):
        path = path[len(prefix):] or "/"
    if not path.startswith("/api/") and path != "/api":
        path = "/api" + path
    request.scope["path"] = path
    return await call_next(request)
