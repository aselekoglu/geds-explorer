from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from .neon_projection_target import NeonProjectionImportTarget
from .postgres_projection_target import INSERT_BATCH_SIZE, SCHEMA_NAME, _convert
from .public_projection import PUBLIC_TABLE_COLUMNS, PublicProjectionError
from .public_projection_import import PublicProjectionImportPlan, postgres_schema_path


class NeonPreviewProjectionImportTarget(NeonProjectionImportTarget):
    """Neon staging target that accepts labelled previews but never activates them."""

    def stage_public_projection(
        self,
        plan: PublicProjectionImportPlan,
        source: sqlite3.Connection,
    ) -> None:
        if plan.manifest.release_kind != "preview" and not plan.manifest.publishable:
            raise PublicProjectionError("only labelled previews or complete projections may be staged")
        schema_sql = self.schema_sql_path.read_text(encoding="utf-8")
        cursor = self.connection.cursor()
        try:
            cursor.execute(schema_sql)
            existing = cursor.execute(
                f"SELECT status FROM {SCHEMA_NAME}.projection_releases WHERE release_id=%s",
                (plan.release_id,),
            ).fetchone()
            if existing and _row_value(existing, 0) == "active":
                raise PublicProjectionError("projection release is already active")
            if existing:
                cursor.execute(
                    f"DELETE FROM {SCHEMA_NAME}.projection_releases WHERE release_id=%s",
                    (plan.release_id,),
                )
            manifest = plan.manifest
            cursor.execute(
                f"""INSERT INTO {SCHEMA_NAME}.projection_releases (
                    release_id,schema_version,projection_version,snapshot_id,as_of_at,quality_status,
                    release_kind,publishable,taxonomy_version,departments_count,organizations_count,
                    people_count,career_entities_count,data_sha256,status
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'staging')""",
                (
                    plan.release_id,
                    manifest.schema_version,
                    manifest.projection_version,
                    manifest.snapshot_id,
                    manifest.as_of_at,
                    manifest.quality_status,
                    manifest.release_kind,
                    manifest.publishable,
                    manifest.taxonomy_version,
                    manifest.counts["departments"],
                    manifest.counts["organizations"],
                    manifest.counts["people"],
                    manifest.counts["career_entities"],
                    manifest.data_sha256,
                ),
            )
            cursor.execute(
                f"""INSERT INTO {SCHEMA_NAME}.public_meta (
                    release_id,singleton,snapshot_id,taxonomy_version,quality_status,as_of_at,
                    people_count,org_units_count,departments_count,projection_version,release_kind,publishable
                ) VALUES (%s,TRUE,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    plan.release_id,
                    manifest.snapshot_id,
                    manifest.taxonomy_version,
                    manifest.quality_status,
                    manifest.as_of_at,
                    manifest.counts["people"],
                    manifest.counts["organizations"],
                    manifest.counts["departments"],
                    manifest.projection_version,
                    manifest.release_kind,
                    manifest.publishable,
                ),
            )
            self._copy_rows(cursor, source, plan.release_id, "canonical_snapshots", "snapshot_id = ?", (manifest.snapshot_id,))
            self._copy_rows(cursor, source, plan.release_id, "departments_current", "snapshot_id = ?", (manifest.snapshot_id,))
            self._copy_rows(cursor, source, plan.release_id, "organizations_current", "snapshot_id = ?", (manifest.snapshot_id,))
            self._copy_rows(cursor, source, plan.release_id, "people_current", "snapshot_id = ? AND presence_status = 'present'", (manifest.snapshot_id,))
            self._copy_rows(cursor, source, plan.release_id, "career_entities", "snapshot_id = ?", (manifest.snapshot_id,))
            self._copy_rows(cursor, source, plan.release_id, "career_entities_fts", "entity_id IN (SELECT entity_id FROM career_entities)", ())
            self._copy_rows(cursor, source, plan.release_id, "career_matches", "entity_id IN (SELECT entity_id FROM career_entities)", ())
            self._copy_rows(cursor, source, plan.release_id, "vacancy_signals", "snapshot_id = ?", (manifest.snapshot_id,))
            self._validate_staging(cursor, plan)
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise
        finally:
            cursor.close()


def _row_value(row: Any, index: int) -> Any:
    if isinstance(row, dict):
        return row["status"]
    return row[index]
