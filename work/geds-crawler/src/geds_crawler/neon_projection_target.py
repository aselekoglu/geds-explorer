from __future__ import annotations

import sqlite3
from typing import Any, Iterable

from .public_projection import PUBLIC_TABLE_COLUMNS
from .postgres_projection_target import (
    INSERT_BATCH_SIZE,
    SCHEMA_NAME,
    PostgresProjectionImportTarget,
    _convert,
)


class NeonProjectionImportTarget(PostgresProjectionImportTarget):
    """Neon target with release-id-aware JSONB parameter binding."""

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
        if table == "career_entities_fts":
            target_columns = ("release_id", "entity_id", "title", "organization_name", "ancestor_text")
            converters: tuple[str | None, ...] = (None, None, None, None)
        else:
            target_columns = ("release_id", *columns)
            converters = tuple("jsonb" if column in {"evidence_json", "reasons_json"} else None for column in columns)
        placeholders = ("%s", *("CAST(%s AS jsonb)" if converter == "jsonb" else "%s" for converter in converters))
        sql = f"INSERT INTO {SCHEMA_NAME}.{table} ({', '.join(target_columns)}) VALUES ({', '.join(placeholders)})"
        batch = []
        for row in rows:
            batch.append((release_id, *(_convert(row[column], converter) for column, converter in zip(columns, converters))))
            if len(batch) >= INSERT_BATCH_SIZE:
                cursor.executemany(sql, batch)
                batch.clear()
        if batch:
            cursor.executemany(sql, batch)

