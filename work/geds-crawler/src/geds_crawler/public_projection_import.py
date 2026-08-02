from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .public_projection import (
    PROJECTION_FILENAME,
    PUBLIC_TABLE_COLUMNS,
    PublicProjectionError,
    PublicProjectionManifest,
    validate_public_projection,
)


POSTGRES_SCHEMA_FILENAME = "public_projection_postgres.sql"


@dataclass(frozen=True)
class PublicProjectionImportPlan:
    """Validated, idempotent input for a staging import target."""

    projection_dir: Path
    manifest: PublicProjectionManifest
    release_id: str
    table_names: tuple[str, ...]


class PublicProjectionImportTarget(Protocol):
    """Storage-specific half of the staging -> smoke -> active contract.

    A Neon/Postgres implementation owns transactions and parameter binding.
    It must not update the active pointer from ``stage_public_projection``.
    """

    def stage_public_projection(self, plan: PublicProjectionImportPlan, source: sqlite3.Connection) -> None: ...

    def smoke_public_projection(self, plan: PublicProjectionImportPlan) -> None: ...

    def activate_public_projection(self, plan: PublicProjectionImportPlan) -> None: ...


class PublicProjectionImportCoordinator:
    """Keep staging and activation as separate, hard-to-confuse operations."""

    def __init__(self, target: PublicProjectionImportTarget):
        self._target = target
        self._staged_plan: PublicProjectionImportPlan | None = None

    def stage(
        self,
        projection_dir: Path | str,
        *,
        allow_partial_preview: bool = False,
    ) -> PublicProjectionImportPlan:
        plan = build_public_projection_import_plan(
            projection_dir,
            allow_partial_preview=allow_partial_preview,
        )
        with _open_projection_read_only(plan.projection_dir / PROJECTION_FILENAME) as source:
            self._target.stage_public_projection(plan, source)
        self._target.smoke_public_projection(plan)
        self._staged_plan = plan
        return plan

    def activate(self, plan: PublicProjectionImportPlan) -> None:
        if self._staged_plan != plan:
            raise PublicProjectionError(
                "projection must complete staging and smoke before activation"
            )
        self._target.activate_public_projection(plan)
        self._staged_plan = None


def build_public_projection_import_plan(
    projection_dir: Path | str,
    *,
    allow_partial_preview: bool = False,
) -> PublicProjectionImportPlan:
    directory = Path(projection_dir).resolve()
    manifest = validate_public_projection(
        directory,
        allow_partial_preview=allow_partial_preview,
    )
    release_id = f"{manifest.snapshot_id}:{manifest.data_sha256}"
    return PublicProjectionImportPlan(
        projection_dir=directory,
        manifest=manifest,
        release_id=release_id,
        table_names=tuple(PUBLIC_TABLE_COLUMNS),
    )


def postgres_schema_path() -> Path:
    """Return the checked-in Postgres schema used by a hosted import target."""

    return Path(__file__).resolve().parents[2] / "sql" / POSTGRES_SCHEMA_FILENAME


def _open_projection_read_only(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise PublicProjectionError(f"projection database does not exist: {path}")
    con = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA query_only=ON")
    con.execute("PRAGMA busy_timeout=2000")
    return con

