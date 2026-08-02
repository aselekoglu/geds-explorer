from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable

from .public_projection import PUBLIC_TABLE_COLUMNS, PublicProjectionError
from .public_projection_import import (
    PublicProjectionImportPlan,
    PublicProjectionImportTarget,
    postgres_schema_path,
)


SCHEMA_NAME = "geds_public"
INSERT_BATCH_SIZE = 1000


class PostgresProjectionImportTarget(PublicProjectionImportTarget):
    """DB-API target for Neon/Postgres staging and explicit activation.

    The connection is injected so importing stays provider-neutral and the
    crawler package does not require a hosted database driver for local crawl
    or projection tests. The caller owns credentials and must provide a
    read/write import connection; the Vercel runtime uses a separate reader.
    """

    def __init__(self, connection: Any, schema_sql_path: Path | str | None = None):
        self.connection = connection
        self.schema_sql_path = Path(schema_sql_path) if schema_sql_path else postgres_schema_path()

    def stage_public_projection(self, plan: PublicProjectionImportPlan, source: sqlite3.Connection) -> None:
        if not plan.manifest.publishable:
            raise PublicProjectionError("only a complete public projection may be staged for activation")
        schema_sql = self.schema_sql_path.read_text(encoding="utf-8")
        cursor = self.connection.cursor()
        try:
            cursor.execute(schema_sql)
            existing = cursor.execute(
                f"SELECT status FROM {SCHEMA_NAME}.projection_releases WHERE release_id=%s",
                (plan.release_id,),
            ).fetchone()
            if existing and _row_value(existing, "status", 0) == "active":
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
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'staging')""",
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

    def smoke_public_projection(self, plan: PublicProjectionImportPlan) -> None:
        cursor = self.connection.cursor()
        try:
            self._validate_staging(cursor, plan)
            row = cursor.execute(
                f"SELECT snapshot_id,quality_status,publishable FROM {SCHEMA_NAME}.public_meta WHERE release_id=%s",
                (plan.release_id,),
            ).fetchone()
            if row is None or _row_value(row, "snapshot_id", 0) != plan.manifest.snapshot_id:
                raise PublicProjectionError("staged projection smoke test failed")
        finally:
            cursor.close()

    def activate_public_projection(self, plan: PublicProjectionImportPlan) -> None:
        if not plan.manifest.publishable:
            raise PublicProjectionError("preview projections cannot become active")
        cursor = self.connection.cursor()
        try:
            self._validate_staging(cursor, plan)
            cursor.execute(
                f"UPDATE {SCHEMA_NAME}.projection_releases SET status='retired' WHERE status='active'",
            )
            cursor.execute(
                f"""INSERT INTO {SCHEMA_NAME}.active_projection(singleton,release_id,activated_at)
                   VALUES (TRUE,%s,now())
                   ON CONFLICT (singleton) DO UPDATE SET release_id=EXCLUDED.release_id,activated_at=EXCLUDED.activated_at""",
                (plan.release_id,),
            )
            cursor.execute(
                f"""UPDATE {SCHEMA_NAME}.projection_releases
                   SET status='active',activated_at=now() WHERE release_id=%s""",
                (plan.release_id,),
            )
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise
        finally:
            cursor.close()

    def _copy_rows(
        self,
        cursor: Any,
        source: sqlite3.Connection,
        release_id: str,
        table: str,
        where: str,
        params: Iterable[object],
    ) -> None:
        columns = PUBLIC_TABLE_COLUMNS[table]
        rows = source.execute(
            f"SELECT {', '.join(columns)} FROM {table} WHERE {where} ORDER BY {columns[0]}",
            tuple(params),
        )
        target_columns, placeholders, converters = _target_columns(table)
        sql = f"INSERT INTO {SCHEMA_NAME}.{table} ({', '.join(target_columns)}) VALUES ({', '.join(placeholders)})"
        batch = []
        for row in rows:
            batch.append((release_id, *(_convert(row[column], converter) for column, converter in zip(columns, converters))))
            if len(batch) >= INSERT_BATCH_SIZE:
                cursor.executemany(sql, batch)
                batch.clear()
        if batch:
            cursor.executemany(sql, batch)

    def _validate_staging(self, cursor: Any, plan: PublicProjectionImportPlan) -> None:
        expected = plan.manifest.counts
        actual = {
            "departments": cursor.execute(f"SELECT COUNT(*) FROM {SCHEMA_NAME}.departments_current WHERE release_id=%s", (plan.release_id,)).fetchone()[0],
            "organizations": cursor.execute(f"SELECT COUNT(*) FROM {SCHEMA_NAME}.organizations_current WHERE release_id=%s", (plan.release_id,)).fetchone()[0],
            "people": cursor.execute(f"SELECT COUNT(*) FROM {SCHEMA_NAME}.people_current WHERE release_id=%s AND presence_status='present'", (plan.release_id,)).fetchone()[0],
            "career_entities": cursor.execute(f"SELECT COUNT(*) FROM {SCHEMA_NAME}.career_entities WHERE release_id=%s", (plan.release_id,)).fetchone()[0],
        }
        if {key: int(value) for key, value in actual.items()} != expected:
            raise PublicProjectionError(f"staged projection row-count mismatch: expected {expected}, got {actual}")


def _target_columns(table: str) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str | None, ...]]:
    columns = PUBLIC_TABLE_COLUMNS[table]
    if table == "career_entities_fts":
        # search_document is generated by PostgreSQL and must not be inserted.
        target = ("release_id", "entity_id", "title", "organization_name", "ancestor_text")
        return target, tuple("%s" for _ in target), (None, None, None, None)
    converters = tuple("jsonb" if column in {"evidence_json", "reasons_json"} else None for column in columns)
    target = ("release_id", *columns)
    return target, tuple("%s" if converter is None else "CAST(%s AS jsonb)" for converter in converters for _ in [0]), (None, *converters)


def _convert(value: Any, converter: str | None) -> Any:
    if converter == "jsonb":
        return json.dumps(value if not isinstance(value, str) else json.loads(value), ensure_ascii=False)
    return value


def _row_value(row: Any, key: str, index: int) -> Any:
    if isinstance(row, dict):
        return row[key]
    return row[index]

