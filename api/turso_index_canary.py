"""Vercel root-level bridge for the Turso preview canary function."""

from pathlib import Path
import sys

_api_dir = Path(__file__).resolve().parents[1] / "work" / "geds-career-atlas" / "api"
if str(_api_dir) not in sys.path:
    sys.path.insert(0, str(_api_dir))

from turso_index_canary import app as _app  # noqa: E402


async def app(scope, receive, send):
    """Normalize Vercel's function prefix before handing off to FastAPI."""
    if scope.get("type") == "http":
        path = scope.get("path", "")
        prefix = "/api/turso_index_canary"
        if path == prefix or path.startswith(prefix + "/"):
            path = path[len(prefix):] or "/"
        if not path.startswith("/api/") and path != "/api":
            path = "/api" + path
        scope = dict(scope)
        scope["path"] = path
    await _app(scope, receive, send)
