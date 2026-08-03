"""Small read-only SQL-over-HTTP adapter for the public Turso projection."""

from __future__ import annotations

import base64
import json
import os
import re
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


_ILIKE_RE = re.compile(r"(\b(?:[A-Za-z_]\w*\.)?[A-Za-z_]\w*|COALESCE\([^)]*\))\s+ILIKE\s+\?", re.IGNORECASE)


class TursoError(RuntimeError):
    """Raised when a read-only Turso request cannot be completed."""


class TursoResult:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows
        self._position = 0

    def fetchone(self) -> dict[str, Any] | None:
        if self._position >= len(self._rows):
            return None
        row = self._rows[self._position]
        self._position += 1
        return row

    def fetchall(self) -> list[dict[str, Any]]:
        rows = self._rows[self._position :]
        self._position = len(self._rows)
        return rows


def is_turso_backend() -> bool:
    return os.environ.get("GEDS_PUBLIC_BACKEND", "neon").casefold() == "turso"


def _http_url(value: str) -> str:
    url = value.strip()
    if url.startswith("libsql://"):
        url = "https://" + url.removeprefix("libsql://")
    return url.rstrip("/") + "/v2/pipeline"


def _argument(value: Any) -> dict[str, str]:
    if value is None:
        return {"type": "null"}
    if isinstance(value, bool):
        return {"type": "integer", "value": "1" if value else "0"}
    if isinstance(value, int):
        return {"type": "integer", "value": str(value)}
    if isinstance(value, float):
        return {"type": "float", "value": repr(value)}
    return {"type": "text", "value": str(value)}


def _decode(value: dict[str, Any]) -> Any:
    kind = value.get("type")
    if kind == "null":
        return None
    if kind == "integer":
        return int(value["value"])
    if kind == "float":
        return float(value["value"])
    if kind == "blob":
        return base64.b64decode(value.get("base64", ""))
    return value.get("value")


def adapt_sql(sql: str) -> str:
    """Translate the small Postgres-shaped public query contract to SQLite."""

    translated = sql.replace("%s", "?")
    translated = re.sub(r"\brelease_id\b", "snapshot_id", translated)
    translated = translated.replace("geds_public.", "main.")
    translated = _ILIKE_RE.sub(r"LOWER(\1) LIKE LOWER(?)", translated)
    return translated


class TursoConnection:
    """DB-API-shaped read connection backed by Turso SQL over HTTP."""

    def __init__(self, database_url: str, auth_token: str, timeout: float = 15.0) -> None:
        if not database_url or not auth_token:
            raise TursoError("Turso database URL and read-only token are required")
        self._endpoint = _http_url(database_url)
        self._auth_token = auth_token
        self._timeout = timeout

    def __enter__(self) -> "TursoConnection":
        return self

    def __exit__(self, *_exc: object) -> None:
        return None

    def execute(self, sql: str, params: Iterable[Any] = ()) -> TursoResult:
        statement = {
            "type": "execute",
            "stmt": {"sql": adapt_sql(sql), "args": [_argument(value) for value in params]},
        }
        payload = json.dumps({"requests": [statement, {"type": "close"}]}).encode("utf-8")
        request = Request(
            self._endpoint,
            data=payload,
            headers={
                "Authorization": f"Bearer {self._auth_token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self._timeout) as response:
                raw = response.read()
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            raise TursoError("Turso public database request failed") from exc

        try:
            envelope = json.loads(raw.decode("utf-8"))
            result = envelope["results"][0]
            if result.get("type") == "error":
                raise TursoError(str(result.get("error", {}).get("message", "Turso SQL error")))
            body = result["response"]["result"]
            columns = [str(column["name"]) for column in body.get("cols", [])]
            rows = [dict(zip(columns, (_decode(value) for value in row))) for row in body.get("rows", [])]
            return TursoResult(rows)
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise TursoError("Turso returned an invalid SQL response") from exc
