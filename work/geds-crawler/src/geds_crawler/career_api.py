from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .career_api_models import serialize
from .career_repository import CareerRepository


def create_career_app(master_db: Path | str, frontend_dir: Path | str | None = None) -> FastAPI:
    app = FastAPI(title="GEDS Career Atlas API", docs_url="/api/docs", openapi_url="/api/openapi.json")
    app.state.repository = CareerRepository(master_db)

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'wasm-unsafe-eval'; style-src 'self'; connect-src 'self' blob:; img-src 'self' data: blob:"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

    def repository(request: Request) -> CareerRepository:
        return request.app.state.repository

    def payload(value):
        body = serialize(value)
        headers = {"ETag": body["etag"]} if isinstance(body, dict) and body.get("etag") else {}
        return JSONResponse(body, headers=headers)

    @app.get("/api/meta")
    def meta(request: Request):
        return JSONResponse(repository(request).meta())

    @app.get("/api/search")
    def search(request: Request, q: str = Query(min_length=1, max_length=240), limit: int = Query(20, ge=1, le=200)):
        return payload(repository(request).search(query=q, limit=limit))

    @app.get("/api/departments")
    def departments(request: Request):
        return payload(repository(request).departments())

    @app.get("/api/orgs/root/children")
    def root_children(request: Request, limit: int = Query(50, ge=1, le=200)):
        return payload(repository(request).children(parent_id=None, limit=limit))

    @app.get("/api/orgs/{org_id}/children")
    def children(request: Request, org_id: str, limit: int = Query(50, ge=1, le=200)):
        return payload(repository(request).children(parent_id=org_id, limit=limit))

    @app.get("/api/orgs/{org_id}/ancestors")
    def ancestors(request: Request, org_id: str):
        try:
            return payload(repository(request).ancestors(org_id))
        except KeyError as exc:
            raise HTTPException(404, "organization not found") from exc

    @app.get("/api/orgs/{org_id}/profile")
    def profile(request: Request, org_id: str):
        try:
            return JSONResponse(serialize(repository(request).team_profile(org_id)))
        except KeyError as exc:
            raise HTTPException(404, "organization not found") from exc

    @app.get("/api/orgs/{org_id}/people")
    def people(
        request: Request,
        org_id: str,
        q: str = Query("", max_length=160),
        classification: str | None = Query(None, pattern=r"^(?:EC|CO|IT|CS)-\d{2}$"),
        sort: str = Query("name", pattern=r"^(?:name|title)$"),
        limit: int = Query(50, ge=1, le=200),
        offset: int = Query(0, ge=0, le=1000000),
    ):
        try:
            return payload(
                repository(request).people(
                    org_id=org_id,
                    query=q,
                    classification=classification,
                    sort=sort,
                    limit=limit,
                    offset=offset,
                )
            )
        except KeyError as exc:
            raise HTTPException(404, "organization not found") from exc

    @app.get("/api/roles")
    def roles(request: Request, org_id: str | None = None, limit: int = Query(50, ge=1, le=200)):
        return payload(repository(request).roles(org_id=org_id, limit=limit))

    @app.get("/api/vacancy-signals")
    def vacancy_signals(request: Request, limit: int = Query(50, ge=1)):
        return payload(repository(request).vacancy_signals(limit=limit))

    @app.get("/api/constellation/slice")
    def constellation_slice(request: Request, root_id: str | None = None, max_depth: int = Query(1, ge=1, le=12), limit: int = Query(200, ge=1, le=2000), category: str | None = Query(None, max_length=80)):
        return payload(repository(request).constellation_slice(root_id=root_id, max_depth=max_depth, limit=limit, category=category))

    @app.get("/api/constellation")
    def constellation(request: Request, q: str = Query(min_length=1, max_length=240), limit: int = Query(200, ge=1)):
        return payload(repository(request).constellation(query=q, limit=limit))

    @app.get("/api/tours")
    def tours(request: Request):
        return payload(repository(request).tours())

    if frontend_dir is not None:
        path = Path(frontend_dir)
        if path.is_dir():
            app.mount("/", StaticFiles(directory=str(path), html=True), name="frontend")
    return app
