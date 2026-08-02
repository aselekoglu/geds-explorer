from __future__ import annotations

import hashlib
import json
import os
import re
from functools import lru_cache
from typing import Any, Callable
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse


app = FastAPI(title="GEDS Career Atlas public API", docs_url="/api/docs", openapi_url="/api/openapi.json")

MAX_PAGE_SIZE = 200
MAX_CONSTELLATION_SIZE = 2000
CLASSIFICATION_RE = re.compile(r"(?<![A-Z0-9])(EC|CO|IT|CS)[- ]?(\d{1,2})(?!\d)", re.IGNORECASE)
OFFICIAL_GEDS_HOST = "geds-sage.gc.ca"

TOURS = (
    {
        "id": "ai",
        "title": {"en": "Explore AI in government", "fr": "Explorer l'IA au gouvernement"},
        "description": {"en": "Follow observed data-science and artificial-intelligence teams.", "fr": "Suivez les equipes observees de science des donnees et d'intelligence artificielle."},
        "categories": ["data-ai-research"],
        "initial_focus": "QJ_S2gMb4E6L-xwExLbMoQ",
        "stops": [{"org_id": "QJ_S2gMb4E6L-xwExLbMoQ", "note": {"en": "Observed analytics and data-science titles.", "fr": "Titres observes en analytique et science des donnees."}}],
    },
    {
        "id": "software",
        "title": {"en": "Find software delivery teams", "fr": "Trouver les equipes de livraison logicielle"},
        "description": {"en": "Trace product, engineering, platform, and delivery work.", "fr": "Parcourez le travail lie aux produits, a l'ingenierie, aux plateformes et a la livraison."},
        "categories": ["software-digital"],
        "initial_focus": "WtHHBZIPdvfAB4oMthqmtA",
        "stops": [{"org_id": "WtHHBZIPdvfAB4oMthqmtA", "note": {"en": "Observed product-delivery and support titles.", "fr": "Titres observes en livraison de produits et soutien."}}],
    },
    {
        "id": "cybersecurity",
        "title": {"en": "Navigate cybersecurity", "fr": "Naviguer la cybersecurite"},
        "description": {"en": "Explore security operations, infrastructure, and trust teams.", "fr": "Explorez les equipes d'operations de securite, d'infrastructure et de confiance."},
        "categories": ["cybersecurity-security"],
        "initial_focus": "9KfFy5Stq9melrsWhybJ6g",
        "stops": [{"org_id": "9KfFy5Stq9melrsWhybJ6g", "note": {"en": "Observed cyber-security operations organization.", "fr": "Organisation observee des operations de cybersecurite."}}],
    },
    {
        "id": "policy",
        "title": {"en": "Walk public-policy pathways", "fr": "Parcourir les voies des politiques publiques"},
        "description": {"en": "See where policy, regulation, legislation, and programs appear.", "fr": "Voyez ou apparaissent les politiques, la reglementation, la legislation et les programmes."},
        "categories": ["policy-programs-regulation"],
        "initial_focus": "3YEszULIIk7_gEhiki4NvQ",
        "stops": [{"org_id": "3YEszULIIk7_gEhiki4NvQ", "note": {"en": "Observed legislative and regulatory organization names.", "fr": "Noms d'organisations observes en legislation et reglementation."}}],
    },
    {
        "id": "data",
        "title": {"en": "Discover data careers", "fr": "Decouvrir les carrieres en donnees"},
        "description": {"en": "Follow analytics, measurement, business-intelligence, and data teams.", "fr": "Suivez les equipes d'analytique, de mesure, d'intelligence d'affaires et de donnees."},
        "categories": ["data-ai-research"],
        "initial_focus": "QJ_S2gMb4E6L-xwExLbMoQ",
        "stops": [{"org_id": "QJ_S2gMb4E6L-xwExLbMoQ", "note": {"en": "Observed analytics-services organization.", "fr": "Organisation observee de services analytiques."}}],
    },
)


@lru_cache(maxsize=1)
def _schema() -> str:
    value = os.environ.get("GEDS_PUBLIC_PROJECTION_SCHEMA", "geds_public")
    if not re.fullmatch(r"[a-z_][a-z0-9_]*", value):
        raise RuntimeError("invalid public projection schema configuration")
    return value


def _connect():
    url = os.environ.get("GEDS_PUBLIC_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not url:
        raise HTTPException(503, "public database is not configured")
    try:
        import psycopg
        from psycopg.rows import dict_row

        return psycopg.connect(url, row_factory=dict_row)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(503, "public database is unavailable") from exc


def _read(operation: Callable[[Any], Any]) -> Any:
    with _connect() as con:
        return operation(con)


def _active(con) -> dict[str, Any]:
    schema = _schema()
    row = con.execute(
        f"""SELECT r.release_id,r.snapshot_id,r.as_of_at,r.quality_status,r.release_kind,r.publishable,
                   r.taxonomy_version,r.departments_count,r.organizations_count,r.people_count,
                   r.career_entities_count,r.projection_version,r.schema_version
            FROM {schema}.active_projection a
            JOIN {schema}.projection_releases r ON r.release_id=a.release_id
            WHERE a.singleton=TRUE"""
    ).fetchone()
    if row is None:
        raise HTTPException(503, "public projection is not active")
    return dict(row)


def _bounded(value: int, maximum: int) -> int:
    return max(1, min(int(value), maximum))


def _etag(active: dict[str, Any], *parts: object) -> str:
    value = "|".join([str(active["snapshot_id"]), *(str(part).casefold() for part in parts)])
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:20]


def _official_url(value: str | None) -> str:
    parsed = urlparse(value or "")
    return value or "" if parsed.scheme == "https" and parsed.hostname == OFFICIAL_GEDS_HOST else ""


def _person_id(source_url: str) -> str:
    return hashlib.sha256(source_url.encode("utf-8")).hexdigest()[:20]


def _classifications(title: str | None) -> list[str]:
    values: list[str] = []
    for group, level in CLASSIFICATION_RE.findall(title or ""):
        value = f"{group.upper()}-{int(level):02d}"
        if value not in values:
            values.append(value)
    return values


def _json_value(value: Any, fallback: Any) -> Any:
    if value is None:
        return fallback
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return fallback


def _node(row: dict[str, Any], quality_status: str) -> dict[str, Any]:
    return {
        "org_id": str(row["org_id"]),
        "name": str(row["name"]),
        "parent_id": row.get("parent_id"),
        "depth": int(row["depth"]),
        "child_count": int(row["child_count"]),
        "direct_people_count": int(row["direct_people_count"]),
        "descendant_people_count": int(row["descendant_people_count"]),
        "descendant_org_count": int(row.get("descendant_org_count") or 0),
        "match_count": int(row.get("match_count") or 0),
        "quality_status": quality_status,
        "vacancy_count": int(row.get("vacancy_count") or 0),
        "has_more": bool(row.get("has_more", False)),
    }


def _search_item(row: dict[str, Any], score: int, evidence: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "entity_id": str(row["entity_id"]),
        "entity_kind": str(row["entity_kind"]),
        "org_id": row.get("org_id"),
        "title": str(row.get("title") or ""),
        "organization_name": str(row.get("organization_name") or ""),
        "department_name": str(row.get("department_name") or ""),
        "display_name": str(row.get("display_name") or ""),
        "source_url": _official_url(row.get("source_url")),
        "score": int(score),
        "confidence": "high" if score >= 100 else "medium" if score >= 60 else "exploratory" if score >= 25 else "none",
        "evidence": evidence or [],
        "vacancy_signal": bool(row.get("vacancy_signal", False)),
    }


def _search_result(items: list[dict[str, Any]], active: dict[str, Any], limit: int, *etag_parts: object, interpretation: dict[str, Any] | None = None) -> dict[str, Any]:
    items.sort(key=lambda item: (-int(item["score"]), str(item["entity_id"])))
    return {
        "items": items[:limit],
        "limit": limit,
        "snapshot_id": str(active["snapshot_id"]),
        "quality_status": str(active["quality_status"]),
        "etag": _etag(active, *etag_parts),
        "interpretation": interpretation or {},
    }


def _direct_interpretation(query: str, active: dict[str, Any]) -> dict[str, Any]:
    return {
        "original_query": query,
        "normalized_query": query.casefold(),
        "category_ids": [],
        "expanded_terms": [],
        "evidence": [],
        "taxonomy_version": str(active["taxonomy_version"]),
    }


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'wasm-unsafe-eval'; style-src 'self'; connect-src 'self'; img-src 'self' data: blob:"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


@app.get("/api/meta")
def meta():
    def read(con):
        active = _active(con)
        return {key: active[key] for key in ("snapshot_id", "taxonomy_version", "quality_status", "as_of_at", "people_count", "organizations_count", "departments_count") if key in active} | {"org_units_count": active["organizations_count"]}

    return _read(read)


@app.get("/api/departments")
def departments():
    def read(con):
        active = _active(con)
        rows = con.execute(f"SELECT department_id,name FROM {_schema()}.departments_current WHERE release_id=%s ORDER BY name,department_id", (active["release_id"],)).fetchall()
        return {"items": [dict(row) for row in rows], "snapshot_id": active["snapshot_id"], "quality_status": active["quality_status"], "etag": _etag(active, "departments")}

    return _read(read)


def _children(parent_id: str | None, limit: int):
    limit = _bounded(limit, MAX_PAGE_SIZE)

    def read(con):
        active = _active(con)
        schema = _schema()
        if parent_id is None:
            rows = con.execute(
                f"""SELECT o.org_id,o.name,NULL AS parent_id,o.depth,o.child_count,o.direct_people_count,
                          o.descendant_people_count,o.descendant_org_count
                   FROM {schema}.organizations_current o
                   WHERE o.release_id=%s AND o.parent_dn IS NULL
                   ORDER BY o.name,o.org_id LIMIT %s""",
                (active["release_id"], limit),
            ).fetchall()
        else:
            rows = con.execute(
                f"""SELECT child.org_id,child.name,parent.org_id AS parent_id,child.depth,child.child_count,
                          child.direct_people_count,child.descendant_people_count,child.descendant_org_count
                   FROM {schema}.organizations_current child
                   JOIN {schema}.organizations_current parent ON parent.release_id=child.release_id AND parent.org_dn=child.parent_dn
                   WHERE child.release_id=%s AND parent.org_id=%s
                   ORDER BY child.name,child.org_id LIMIT %s""",
                (active["release_id"], parent_id, limit),
            ).fetchall()
        return {"items": [_node(dict(row), str(active["quality_status"])) for row in rows], "limit": limit, "snapshot_id": active["snapshot_id"], "quality_status": active["quality_status"], "etag": _etag(active, "children", parent_id or "root", limit)}

    return _read(read)


@app.get("/api/orgs/root/children")
def root_children(limit: int = Query(50, ge=1, le=200)):
    return _children(None, limit)


@app.get("/api/orgs/{org_id}/children")
def children(org_id: str, limit: int = Query(50, ge=1, le=200)):
    return _children(org_id, limit)


@app.get("/api/orgs/{org_id}/ancestors")
def ancestors(org_id: str):
    def read(con):
        active = _active(con)
        schema = _schema()
        rows = con.execute(
            f"""WITH RECURSIVE lineage AS (
                   SELECT org_dn,parent_dn,0 AS ordinal FROM {schema}.organizations_current
                   WHERE release_id=%s AND org_id=%s
                   UNION ALL
                   SELECT parent.org_dn,parent.parent_dn,lineage.ordinal+1
                   FROM {schema}.organizations_current parent JOIN lineage ON parent.org_dn=lineage.parent_dn
                   WHERE parent.release_id=%s
               )
               SELECT o.org_id,o.name,p.org_id AS parent_id,o.depth,o.child_count,o.direct_people_count,
                      o.descendant_people_count,o.descendant_org_count
               FROM lineage JOIN {schema}.organizations_current o ON o.release_id=%s AND o.org_dn=lineage.org_dn
               LEFT JOIN {schema}.organizations_current p ON p.release_id=o.release_id AND p.org_dn=o.parent_dn
               ORDER BY lineage.ordinal DESC""",
            (active["release_id"], org_id, active["release_id"], active["release_id"]),
        ).fetchall()
        if not rows:
            raise HTTPException(404, "organization not found")
        items = [_node(dict(row), str(active["quality_status"])) for row in rows]
        return {"items": items, "limit": len(items), "snapshot_id": active["snapshot_id"], "quality_status": active["quality_status"], "etag": _etag(active, "ancestors", org_id)}

    return _read(read)


@app.get("/api/orgs/{org_id}/profile")
def profile(org_id: str):
    def read(con):
        active = _active(con)
        schema = _schema()
        row = con.execute(
            f"""SELECT o.name,o.department_dn,d.name AS department_name,o.canonical_path_json,
                      o.direct_people_count,o.descendant_people_count,o.child_count,o.source_url
               FROM {schema}.organizations_current o
               JOIN {schema}.departments_current d ON d.release_id=o.release_id AND d.department_dn=o.department_dn
               WHERE o.release_id=%s AND o.org_id=%s""",
            (active["release_id"], org_id),
        ).fetchone()
        if row is None:
            raise HTTPException(404, "organization not found")
        vacancies = con.execute(
            f"""SELECT v.source_text,v.title,v.org_id,p.source_url,v.confidence,v.reasons_json
               FROM {schema}.vacancy_signals v JOIN {schema}.people_current p
                 ON p.release_id=v.release_id AND v.entity_id='person:' || p.source_url
               WHERE v.release_id=%s AND v.org_id=%s
               ORDER BY v.title,v.entity_id""",
            (active["release_id"], org_id),
        ).fetchall()
        return {
            "org_id": org_id,
            "name": row["name"],
            "department_name": row["department_name"],
            "canonical_path": _json_value(row["canonical_path_json"], []),
            "direct_people_count": int(row["direct_people_count"]),
            "descendant_people_count": int(row["descendant_people_count"]),
            "child_count": int(row["child_count"]),
            "snapshot_id": active["snapshot_id"],
            "snapshot_as_of": active["as_of_at"],
            "quality_status": active["quality_status"],
            "source_url": _official_url(row["source_url"]),
            "conversation_leads": [],
            "vacancy_signals": [
                {"marker": item["source_text"], "title": item["title"], "org_id": item["org_id"], "observed_at": str(active["as_of_at"]).split("T", 1)[0], "source_url": _official_url(item["source_url"]), "confidence": item["confidence"], "reasons": _json_value(item["reasons_json"], []), "live_competition_verified": False}
                for item in vacancies
            ],
        }

    return _read(read)


@app.get("/api/orgs/{org_id}/people")
def people(
    org_id: str,
    q: str = Query("", max_length=160),
    classification: str | None = Query(None, pattern=r"^(?:EC|CO|IT|CS)-\d{2}$"),
    sort: str = Query("name", pattern=r"^(?:name|title)$"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0, le=1000000),
):
    limit = _bounded(limit, MAX_PAGE_SIZE)

    def read(con):
        active = _active(con)
        schema = _schema()
        organization = con.execute(f"SELECT org_id,name,org_dn FROM {schema}.organizations_current WHERE release_id=%s AND org_id=%s", (active["release_id"], org_id)).fetchone()
        if organization is None:
            raise HTTPException(404, "organization not found")
        rows = con.execute(
            f"""SELECT display_name,title,source_url FROM {schema}.people_current
               WHERE release_id=%s AND org_dn=%s AND presence_status='present'
               ORDER BY display_name,source_url""",
            (active["release_id"], organization["org_dn"]),
        ).fetchall()
        all_people = []
        for row in rows:
            title = str(row["title"] or "")
            observed = _classifications(title)
            person = {"person_id": _person_id(str(row["source_url"])), "display_name": str(row["display_name"]), "observed_title": title, "observed_classifications": observed, "org_id": organization["org_id"], "organization_name": organization["name"], "snapshot_id": active["snapshot_id"], "snapshot_as_of": active["as_of_at"], "source_url": _official_url(row["source_url"])}
            folded = f"{person['display_name']} {title}".casefold()
            if (not q or q.casefold() in folded) and (classification is None or classification in observed):
                all_people.append(person)
        all_people.sort(key=lambda person: ((person["observed_title"].casefold(), person["display_name"].casefold()) if sort == "title" else (person["display_name"].casefold(), person["observed_title"].casefold()), person["person_id"]))
        available = sorted({value for row in rows for value in _classifications(row["title"])})
        return {"items": all_people[offset:offset + limit], "total": len(all_people), "limit": limit, "offset": offset, "available_classifications": available, "snapshot_id": active["snapshot_id"], "quality_status": active["quality_status"], "etag": _etag(active, "people", org_id, q, classification or "all", sort, limit, offset)}

    return _read(read)


@app.get("/api/search")
def search(q: str = Query(min_length=1, max_length=240), limit: int = Query(20, ge=1, le=200)):
    limit = _bounded(limit, MAX_PAGE_SIZE)

    def read(con):
        active = _active(con)
        schema = _schema()
        items: list[dict[str, Any]] = []
        org_rows = con.execute(
            f"""SELECT o.org_id,o.name,d.name AS department_name FROM {schema}.organizations_current o
               LEFT JOIN {schema}.departments_current d ON d.release_id=o.release_id AND d.department_dn=o.department_dn
               WHERE o.release_id=%s AND (o.name ILIKE %s OR o.canonical_path_json ILIKE %s)
               ORDER BY o.name LIMIT %s""",
            (active["release_id"], f"%{q}%", f"%{q}%", limit),
        ).fetchall()
        for row in org_rows:
            exact = str(row["name"]).casefold() == q.casefold()
            items.append(_search_item({"entity_id": f"org:{row['org_id']}", "entity_kind": "organization", "org_id": row["org_id"], "title": "", "organization_name": row["name"], "department_name": row["department_name"]}, 1000 if exact else 500, [{"field": "organization", "matched_phrase": q, "source_text": row["name"], "weight": 500, "category_id": "direct-search"}]))
        people_rows = con.execute(
            f"""SELECT p.source_url,p.display_name,p.title,o.org_id,o.name AS organization_name,d.name AS department_name
               FROM {schema}.people_current p
               LEFT JOIN {schema}.organizations_current o ON o.release_id=p.release_id AND o.org_dn=p.org_dn
               LEFT JOIN {schema}.departments_current d ON d.release_id=p.release_id AND d.department_dn=p.department_dn
               WHERE p.release_id=%s AND p.presence_status='present'
                 AND (p.display_name ILIKE %s OR COALESCE(p.title,'') ILIKE %s)
               ORDER BY p.display_name LIMIT %s""",
            (active["release_id"], f"%{q}%", f"%{q}%", limit),
        ).fetchall()
        for row in people_rows:
            display_name = str(row["display_name"])
            field = "display_name" if q.casefold() in display_name.casefold() else "title"
            items.append(_search_item({"entity_id": f"person:{row['source_url']}", "entity_kind": "person", "org_id": row["org_id"], "title": row["title"], "organization_name": row["organization_name"], "department_name": row["department_name"], "display_name": display_name, "source_url": row["source_url"]}, 1000 if display_name.casefold() == q.casefold() else 450, [{"field": field, "matched_phrase": q, "source_text": display_name if field == "display_name" else str(row["title"] or ""), "weight": 450, "category_id": "direct-search"}]))
        return _search_result(items, active, limit, "search", q, limit, interpretation=_direct_interpretation(q, active))

    return _read(read)


@app.get("/api/roles")
def roles(org_id: str | None = None, limit: int = Query(50, ge=1, le=200)):
    limit = _bounded(limit, MAX_PAGE_SIZE)

    def read(con):
        active = _active(con)
        schema = _schema()
        params: list[Any] = [active["release_id"]]
        filter_sql = ""
        if org_id is not None:
            filter_sql = " AND e.org_id=%s"
            params.append(org_id)
        params.append(limit)
        rows = con.execute(
            f"""SELECT e.entity_id,e.entity_kind,e.org_id,e.title,e.organization_name,
                      COALESCE(d.name,'') AS department_name,
                      CASE WHEN v.entity_id IS NULL THEN FALSE ELSE TRUE END AS vacancy_signal
               FROM {schema}.career_entities e
               LEFT JOIN {schema}.vacancy_signals v ON v.release_id=e.release_id AND v.entity_id=e.entity_id
               LEFT JOIN {schema}.organizations_current o ON o.release_id=e.release_id AND o.org_id=e.org_id
               LEFT JOIN {schema}.departments_current d ON d.release_id=e.release_id AND d.department_dn=o.department_dn
               WHERE e.release_id=%s AND e.entity_kind='person'{filter_sql}
               ORDER BY e.title,e.entity_id LIMIT %s""",
            params,
        ).fetchall()
        items = [_search_item(dict(row), 0) for row in rows]
        return _search_result(items, active, limit, "roles", org_id or "all", limit)

    return _read(read)


@app.get("/api/constellation")
def constellation(q: str = Query(min_length=1, max_length=240), limit: int = Query(200, ge=1, le=2000)):
    return search(q, limit)


@app.get("/api/constellation/slice")
def constellation_slice(root_id: str | None = None, max_depth: int = Query(1, ge=1, le=12), limit: int = Query(200, ge=1, le=2000), category: str | None = Query(None, max_length=80)):
    limit = _bounded(limit, MAX_CONSTELLATION_SIZE)
    max_depth = _bounded(max_depth, 12)

    def read(con):
        active = _active(con)
        schema = _schema()
        if root_id is None:
            rows = con.execute(
                f"""SELECT o.org_id,o.name,NULL AS parent_id,o.depth,o.child_count,o.direct_people_count,
                          o.descendant_people_count,o.descendant_org_count
                   FROM {schema}.organizations_current o WHERE o.release_id=%s AND o.parent_dn IS NULL
                   ORDER BY o.name,o.org_id LIMIT %s""",
                (active["release_id"], limit + 1),
            ).fetchall()
        else:
            rows = con.execute(
                f"""WITH RECURSIVE slice(org_dn,level) AS (
                         SELECT org_dn,0 FROM {schema}.organizations_current WHERE release_id=%s AND org_id=%s
                         UNION ALL
                         SELECT child.org_dn,slice.level+1 FROM {schema}.organizations_current child JOIN slice ON child.parent_dn=slice.org_dn
                         WHERE child.release_id=%s AND slice.level < %s
                     )
                     SELECT o.org_id,o.name,p.org_id AS parent_id,o.depth,o.child_count,o.direct_people_count,
                            o.descendant_people_count,o.descendant_org_count
                     FROM slice JOIN {schema}.organizations_current o ON o.release_id=%s AND o.org_dn=slice.org_dn
                     LEFT JOIN {schema}.organizations_current p ON p.release_id=o.release_id AND p.org_dn=o.parent_dn
                     ORDER BY o.depth,o.name,o.org_id LIMIT %s""",
                (active["release_id"], root_id, active["release_id"], max_depth, active["release_id"], limit + 1),
            ).fetchall()
        truncated = len(rows) > limit
        items = [_node(dict(row), str(active["quality_status"])) for row in rows[:limit]]
        visible_children: dict[str, int] = {}
        for item in items:
            if item["parent_id"] is not None:
                visible_children[str(item["parent_id"])] = visible_children.get(str(item["parent_id"]), 0) + 1
        for item in items:
            item["has_more"] = int(item["child_count"]) > visible_children.get(str(item["org_id"]), 0)
        return {"nodes": items, "limit": limit, "truncated": truncated, "snapshot_id": active["snapshot_id"], "quality_status": active["quality_status"], "etag": _etag(active, "constellation-slice", root_id or "root", max_depth, limit, category or "all")}

    return _read(read)


@app.get("/api/tours")
def tours():
    def read(con):
        active = _active(con)
        schema = _schema()
        available = {str(row["org_id"]) for row in con.execute(f"SELECT org_id FROM {schema}.organizations_current WHERE release_id=%s", (active["release_id"],)).fetchall()}
        items = []
        for tour in TOURS:
            item = dict(tour)
            item["stops"] = [{**stop, "available": stop["org_id"] in available} for stop in tour["stops"]]
            items.append(item)
        return {"items": items, "snapshot_id": active["snapshot_id"], "quality_status": active["quality_status"], "etag": _etag(active, "tours", "1.0.0")}

    return _read(read)


@app.get("/api/vacancy-signals")
def vacancy_signals(limit: int = Query(50, ge=1, le=200)):
    def read(con):
        active = _active(con)
        schema = _schema()
        rows = con.execute(
            f"""SELECT v.source_text,v.title,v.org_id,o.name AS organization_name,p.source_url,v.confidence,v.reasons_json
               FROM {schema}.vacancy_signals v
               JOIN {schema}.organizations_current o ON o.release_id=v.release_id AND o.org_id=v.org_id
               JOIN {schema}.people_current p ON p.release_id=v.release_id AND v.entity_id='person:' || p.source_url
               WHERE v.release_id=%s ORDER BY o.name,v.title,v.entity_id LIMIT %s""",
            (active["release_id"], _bounded(limit, MAX_PAGE_SIZE)),
        ).fetchall()
        items = [{"marker": row["source_text"], "title": row["title"], "org_id": row["org_id"], "organization_name": row["organization_name"], "observed_at": str(active["as_of_at"]).split("T", 1)[0], "source_url": _official_url(row["source_url"]), "confidence": row["confidence"], "reasons": _json_value(row["reasons_json"], []), "live_competition_verified": False} for row in rows]
        return {"items": items, "limit": _bounded(limit, MAX_PAGE_SIZE), "snapshot_id": active["snapshot_id"], "quality_status": active["quality_status"], "etag": _etag(active, "vacancy-signals", limit)}

    return _read(read)

