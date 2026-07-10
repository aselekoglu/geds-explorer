from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from .ui_queries import SnapshotReader


class CanonicalValidationError(ValueError):
    """Raised when a completed run cannot be promoted to a canonical snapshot."""


@dataclass(frozen=True)
class ResolvedSnapshot:
    """The complete, ordered source lineage for a promoted backfill run."""

    base_db_paths: tuple[Path, ...]
    overlay_db_paths: tuple[Path, ...]
    members: tuple[Path, ...]

    def reader(self) -> SnapshotReader:
        return SnapshotReader(
            self.base_db_paths[0],
            self.overlay_db_paths,
            additional_base_db_paths=self.base_db_paths[1:],
        )


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
            overlay_path = _resolve_overlay_path(Path(run["output_dir"]))
    except sqlite3.Error as exc:
        raise CanonicalValidationError(
            f"Could not read canonical lineage for run {run_id}: {exc}"
        ) from exc

    _validate_overlay_complete(overlay_path)
    overlay_paths = (overlay_path,)
    return ResolvedSnapshot(
        base_db_paths=base_paths,
        overlay_db_paths=overlay_paths,
        members=(*base_paths, *overlay_paths),
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
    return base_paths


def _resolve_overlay_path(output_dir: Path) -> Path:
    resolved_output_dir = output_dir.resolve()
    for name in ("geds.sqlite", "staging.sqlite"):
        candidate = resolved_output_dir / name
        if candidate.is_file():
            return candidate.resolve()
    raise CanonicalValidationError(
        f"Completed backfill output has no geds.sqlite or staging.sqlite: {resolved_output_dir}"
    )


def _validate_overlay_complete(overlay_path: Path) -> None:
    try:
        with _open_read_only(overlay_path) as con:
            statuses = [
                row["status"]
                for row in con.execute("SELECT status FROM pagination_orgs")
            ]
    except sqlite3.Error as exc:
        raise CanonicalValidationError(
            f"Could not validate backfill overlay {overlay_path}: {exc}"
        ) from exc

    incomplete = [status for status in statuses if status != "completed"]
    if incomplete:
        status_values = ", ".join(sorted({str(status) for status in incomplete}))
        raise CanonicalValidationError(
            f"Backfill overlay is not complete; non-completed organization statuses: {status_values}"
        )


def _open_read_only(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(
        f"file:{db_path.as_posix()}?mode=ro",
        uri=True,
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    return connection
