from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .ui_queries import SnapshotReader


class CanonicalValidationError(ValueError):
    """Raised when a completed run cannot be promoted to a canonical snapshot."""


_BASE_REQUIRED_TABLES = frozenset(
    {
        "crawl_runs",
        "departments",
        "org_units",
        "people_index",
        "crawl_queue",
        "crawl_errors",
    }
)
_OVERLAY_REQUIRED_TABLES = _BASE_REQUIRED_TABLES | {"pagination_orgs"}
_SUCCESS_ORG_STATUSES = frozenset({"completed", "finished"})
_FALLBACK_ORG_STATUSES = frozenset({"failed"})


@dataclass(frozen=True)
class OverlayQuality:
    successful_org_dns: frozenset[str]
    fallback_org_dns: frozenset[str]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class ResolvedSnapshot:
    """The complete, ordered source lineage for a promoted backfill run."""

    base_db_paths: tuple[Path, ...]
    overlay_db_paths: tuple[Path, ...]
    members: tuple[Path, ...]
    quality: OverlayQuality = OverlayQuality(frozenset(), frozenset(), ())

    def reader(self) -> SnapshotReader:
        return SnapshotReader(
            self.base_db_paths[0],
            self.overlay_db_paths,
            additional_base_db_paths=self.base_db_paths[1:],
        )

    def iter_people(self):
        from .canonical_projection import iter_projected_people

        return iter_projected_people(self)

    def iter_orgs(self):
        from .canonical_projection import iter_projected_orgs

        return iter_projected_orgs(self)

    def iter_departments(self):
        from .canonical_projection import iter_projected_departments

        return iter_projected_departments(self)


def resolve_completed_run(control_db: Path, run_id: str) -> ResolvedSnapshot:
    """Resolve a fully completed pagination-backfill run into source databases.

    Promotion is deliberately strict: all frozen base snapshots must remain
    available and every organization in the output overlay must be completed.
    """

    resolved_control_db = Path(control_db).resolve()
    if not resolved_control_db.is_file():
        raise CanonicalValidationError(
            f"Control database does not exist: {resolved_control_db}"
        )

    try:
        with _open_read_only(resolved_control_db) as con:
            _require_tables(
                con,
                {"crawl_runs", "run_pagination_seeds"},
                "control database",
            )
            run = con.execute(
                """
                SELECT status, crawl_kind, output_dir
                FROM crawl_runs
                WHERE id = ?
                """,
                (run_id,),
            ).fetchone()
            if run is None:
                raise CanonicalValidationError(f"Crawl run not found: {run_id}")
            if run["status"] != "finished":
                raise CanonicalValidationError(
                    f"Crawl run {run_id} is not finished (status: {run['status']!r})"
                )
            if run["crawl_kind"] != "pagination_backfill":
                raise CanonicalValidationError(
                    f"Crawl run {run_id} is not a pagination backfill"
                )

            base_paths = _resolve_base_paths(con, run_id)
            overlay_path = _resolve_overlay_path(
                resolved_control_db,
                Path(run["output_dir"]),
            )
    except sqlite3.Error as exc:
        raise CanonicalValidationError(
            f"Could not read canonical lineage for run {run_id}: {exc}"
        ) from exc

    quality = _read_overlay_quality(overlay_path)
    overlay_paths = (overlay_path,)
    return ResolvedSnapshot(
        base_db_paths=base_paths,
        overlay_db_paths=overlay_paths,
        members=(*base_paths, *overlay_paths),
        quality=quality,
    )


def _resolve_base_paths(con: sqlite3.Connection, run_id: str) -> tuple[Path, ...]:
    rows = con.execute(
        """
        SELECT DISTINCT base_db_path
        FROM run_pagination_seeds
        WHERE run_id = ?
        ORDER BY base_db_path
        """,
        (run_id,),
    ).fetchall()
    if not rows:
        raise CanonicalValidationError(
            f"Crawl run {run_id} has no pagination seed base databases"
        )

    base_paths = tuple(Path(row["base_db_path"]).resolve() for row in rows)
    missing = [path for path in base_paths if not path.is_file()]
    if missing:
        paths = ", ".join(str(path) for path in missing)
        raise CanonicalValidationError(f"Seed base database does not exist: {paths}")
    for base_path in base_paths:
        _validate_database_schema(
            base_path,
            "base database",
            _BASE_REQUIRED_TABLES,
        )
    return base_paths


def _resolve_overlay_path(control_db: Path, output_dir: Path) -> Path:
    if output_dir.is_absolute():
        resolved_output_dir = output_dir.resolve()
    else:
        resolved_output_dir = (control_db.parents[2] / output_dir).resolve()
    for name in ("geds.sqlite", "staging.sqlite"):
        candidate = resolved_output_dir / name
        if candidate.is_file():
            return candidate.resolve()
    raise CanonicalValidationError(
        f"Completed backfill output has no geds.sqlite or staging.sqlite: {resolved_output_dir}"
    )


def _read_overlay_quality(overlay_path: Path) -> OverlayQuality:
    try:
        with _open_read_only(overlay_path) as con:
            _require_tables(con, _OVERLAY_REQUIRED_TABLES, "output database")
            rows = con.execute(
                "SELECT org_dn, status FROM pagination_orgs ORDER BY org_dn"
            ).fetchall()
    except sqlite3.Error as exc:
        raise CanonicalValidationError(
            f"invalid output database {overlay_path}: {exc}"
        ) from exc

    if not rows:
        raise CanonicalValidationError(
            f"Backfill overlay has no pagination organizations: {overlay_path}"
        )

    non_terminal = [
        str(row["status"])
        for row in rows
        if row["status"] not in _SUCCESS_ORG_STATUSES | _FALLBACK_ORG_STATUSES
    ]
    if non_terminal:
        status_values = ", ".join(sorted(set(non_terminal)))
        raise CanonicalValidationError(
            "Backfill overlay is not complete; "
            f"non-terminal organization statuses: {status_values}"
        )

    successful = frozenset(
        str(row["org_dn"])
        for row in rows
        if row["status"] in _SUCCESS_ORG_STATUSES
    )
    fallback = frozenset(
        str(row["org_dn"])
        for row in rows
        if row["status"] in _FALLBACK_ORG_STATUSES
    )
    return OverlayQuality(
        successful_org_dns=successful,
        fallback_org_dns=fallback,
        warnings=tuple(
            f"partial_overlay_base_fallback:{org_dn}"
            for org_dn in sorted(fallback)
        ),
    )


def _validate_database_schema(
    db_path: Path,
    label: str,
    required_tables: Iterable[str],
) -> None:
    try:
        with _open_read_only(db_path) as con:
            _require_tables(con, required_tables, label)
    except sqlite3.Error as exc:
        raise CanonicalValidationError(
            f"invalid {label} {db_path}: {exc}"
        ) from exc


def _require_tables(
    con: sqlite3.Connection,
    required_tables: Iterable[str],
    label: str,
) -> None:
    actual_tables = {
        row["name"]
        for row in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    missing = sorted(set(required_tables) - actual_tables)
    if missing:
        raise CanonicalValidationError(
            f"{label} is missing required tables: {', '.join(missing)}"
        )


def _open_read_only(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(
        f"file:{db_path.as_posix()}?mode=ro",
        uri=True,
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    return connection
