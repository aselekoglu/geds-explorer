from __future__ import annotations

import sqlite3
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .canonical_resolver import ResolvedSnapshot


def iter_projected_people(
    resolved: ResolvedSnapshot,
) -> Iterator[dict[str, Any]]:
    """Yield the safe person projection for a terminal pagination overlay.

    A successful target is replaced by its overlay rows. A failed target keeps
    its complete base rows and discards any partial overlay observations.
    """

    successful = resolved.quality.successful_org_dns
    selected: dict[str, dict[str, Any]] = {}
    for row in _dedupe_rows(
        resolved.base_db_paths,
        table="people_index",
        key="source_url",
    ):
        if str(row["org_dn"]) not in successful:
            selected[str(row["source_url"])] = row
    for row in _dedupe_rows(
        resolved.overlay_db_paths,
        table="people_index",
        key="source_url",
    ):
        if str(row["org_dn"]) in successful:
            selected[str(row["source_url"])] = row
    yield from (selected[key] for key in sorted(selected))


def iter_projected_orgs(
    resolved: ResolvedSnapshot,
) -> Iterator[dict[str, Any]]:
    """Yield organization metadata with successful targets overlaying base."""

    successful = resolved.quality.successful_org_dns
    selected = {
        str(row["dn"]): row
        for row in _dedupe_rows(
            resolved.base_db_paths,
            table="org_units",
            key="dn",
        )
    }
    for row in _dedupe_rows(
        resolved.overlay_db_paths,
        table="org_units",
        key="dn",
    ):
        if str(row["dn"]) in successful:
            selected[str(row["dn"])] = row
    yield from (selected[key] for key in sorted(selected))


def iter_projected_departments(
    resolved: ResolvedSnapshot,
) -> Iterator[dict[str, Any]]:
    """Yield one deterministic department record per DN."""

    selected = {
        str(row["dn"]): row
        for row in _dedupe_rows(
            resolved.base_db_paths,
            table="departments",
            key="dn",
        )
    }
    for row in _dedupe_rows(
        resolved.overlay_db_paths,
        table="departments",
        key="dn",
    ):
        selected[str(row["dn"])] = row
    yield from (selected[key] for key in sorted(selected))


def _dedupe_rows(
    db_paths: Sequence[Path],
    *,
    table: str,
    key: str,
) -> tuple[dict[str, Any], ...]:
    allowed = {
        ("people_index", "source_url"),
        ("org_units", "dn"),
        ("departments", "dn"),
    }
    if (table, key) not in allowed:
        raise ValueError(f"unsupported canonical projection: {table}.{key}")

    selected: dict[str, tuple[tuple[str, str], dict[str, Any]]] = {}
    for db_path in sorted(
        (Path(path).resolve() for path in db_paths),
        key=lambda path: path.as_posix().casefold(),
    ):
        with _open_read_only(db_path) as con:
            rows = con.execute(
                f"SELECT * FROM {table} ORDER BY {key}"
            ).fetchall()
        for sqlite_row in rows:
            row = dict(sqlite_row)
            identity = str(row[key])
            rank = (
                str(row.get("last_seen") or ""),
                db_path.as_posix().casefold(),
            )
            current = selected.get(identity)
            if current is None or rank > current[0]:
                selected[identity] = (rank, row)
    return tuple(selected[identity][1] for identity in sorted(selected))


def _open_read_only(db_path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(
        f"file:{db_path.as_posix()}?mode=ro",
        uri=True,
    )
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA query_only=ON")
    return con
