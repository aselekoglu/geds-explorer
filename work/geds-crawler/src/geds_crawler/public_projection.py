from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable


PUBLIC_PROJECTION_VERSION = "public-projection.v1"
PUBLIC_SCHEMA_VERSION = "geds-public.v1"
PROJECTION_FILENAME = "geds-public.sqlite"
MANIFEST_FILENAME = "manifest.json"

# Explicit allow-list: the public artifact is rebuilt from selected columns;
# it is never made by copying the canonical database and redacting afterwards.
PUBLIC_TABLE_COLUMNS: dict[str, tuple[str, ...]] = {
    "public_meta": (
        "singleton", "snapshot_id", "taxonomy_version", "quality_status",
        "as_of_at", "people_count", "org_units_count", "departments_count",
        "projection_version", "release_kind", "publishable",
    ),
    "canonical_snapshots": (
        "snapshot_id", "as_of_at", "people_count", "org_units_count",
        "departments_count", "quality_status",
    ),
    "departments_current": (
        "department_dn", "department_id", "name", "source_url", "snapshot_id",
    ),
    "organizations_current": (
        "org_dn", "org_id", "name", "parent_dn", "department_dn", "depth",
        "canonical_path_json", "source_url", "direct_people_count",
        "descendant_people_count", "child_count", "descendant_org_count",
        "snapshot_id",
    ),
    "people_current": (
        "source_url", "display_name", "title", "org_path", "org_dn",
        "department_dn", "department_name", "org_unit", "canonical_path_json",
        "snapshot_id", "presence_status",
    ),
    "career_entities": (
        "entity_id", "entity_kind", "org_id", "title", "organization_name",
        "ancestor_text", "snapshot_id",
    ),
    "career_entities_fts": (
        "entity_id", "title", "organization_name", "ancestor_text",
    ),
    "career_matches": (
        "entity_id", "category_id", "score", "confidence", "evidence_json",
        "taxonomy_version",
    ),
    "vacancy_signals": (
        "entity_id", "source_text", "title", "org_id", "snapshot_id",
        "confidence", "reasons_json",
    ),
}

PUBLIC_COUNT_KEYS = ("departments", "organizations", "people", "career_entities")
PUBLIC_SNAPSHOT_TABLES = {
    "canonical_snapshots", "departments_current", "organizations_current",
    "people_current", "career_entities", "vacancy_signals",
}

PUBLIC_FTS_INTERNAL_TABLES = {
    "career_entities_fts_config",
    "career_entities_fts_content",
    "career_entities_fts_data",
    "career_entities_fts_docsize",
    "career_entities_fts_idx",
}

class PublicProjectionError(ValueError):
    """Raised when a public projection is unsafe or inconsistent."""


@dataclass(frozen=True)
class PublicProjectionManifest:
    schema_version: str
    projection_version: str
    snapshot_id: str
    as_of_at: str
    quality_status: str
    release_kind: str
    publishable: bool
    taxonomy_version: str
    counts: dict[str, int]
    data_sha256: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def export_public_projection(
    master_db: Path | str,
    output_dir: Path | str,
    *,
    allow_partial_preview: bool = False,
) -> PublicProjectionManifest:
    """Export a validated, allow-listed public SQLite projection."""

    source_path = Path(master_db).resolve()
    target_dir = Path(output_dir).resolve()
    if not source_path.is_file():
        raise PublicProjectionError(f"canonical master database does not exist: {source_path}")
    target_dir.mkdir(parents=True, exist_ok=True)
    if tuple(target_dir.iterdir()):
        raise PublicProjectionError(f"projection output directory is not empty: {target_dir}")

    target_path = target_dir / PROJECTION_FILENAME
    with _open_read_only(source_path) as source:
        _require_source_tables(source)
        snapshot = _source_snapshot(source)
        quality_status = str(snapshot["quality_status"])
        if quality_status != "complete" and not allow_partial_preview:
            raise PublicProjectionError(
                "public projection requires a complete snapshot; "
                "use --allow-partial-preview only for a labelled preview"
            )
        counts = _source_counts(source, str(snapshot["snapshot_id"]))
        declared = {
            "departments": int(snapshot["departments_count"]),
            "organizations": int(snapshot["org_units_count"]),
            "people": int(snapshot["people_count"]),
        }
        for key in declared:
            if counts[key] != declared[key]:
                raise PublicProjectionError(f"{key} row-count does not match the canonical snapshot")
        _create_projection(source, target_path, snapshot, counts)

    with _open_read_only(target_path) as projection:
        data_sha256 = _data_sha256(projection)
    manifest = PublicProjectionManifest(
        schema_version=PUBLIC_SCHEMA_VERSION,
        projection_version=PUBLIC_PROJECTION_VERSION,
        snapshot_id=str(snapshot["snapshot_id"]),
        as_of_at=str(snapshot["as_of_at"]),
        quality_status=quality_status,
        release_kind="public" if quality_status == "complete" else "preview",
        publishable=quality_status == "complete",
        taxonomy_version=str(snapshot["taxonomy_version"]),
        counts=counts,
        data_sha256=data_sha256,
    )
    (target_dir / MANIFEST_FILENAME).write_text(
        json.dumps(manifest.as_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return validate_public_projection(target_dir, allow_partial_preview=allow_partial_preview)


def validate_public_projection(
    projection_dir: Path | str,
    *,
    allow_partial_preview: bool = False,
) -> PublicProjectionManifest:
    """Validate schema, privacy, counts, snapshot binding, and content hash."""

    directory = Path(projection_dir).resolve()
    manifest_path = directory / MANIFEST_FILENAME
    database_path = directory / PROJECTION_FILENAME
    if not manifest_path.is_file() or not database_path.is_file():
        raise PublicProjectionError(
            f"projection must contain {MANIFEST_FILENAME} and {PROJECTION_FILENAME}: {directory}"
        )
    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest = PublicProjectionManifest(
            schema_version=str(raw["schema_version"]),
            projection_version=str(raw["projection_version"]),
            snapshot_id=str(raw["snapshot_id"]),
            as_of_at=str(raw["as_of_at"]),
            quality_status=str(raw["quality_status"]),
            release_kind=str(raw["release_kind"]),
            publishable=bool(raw["publishable"]),
            taxonomy_version=str(raw["taxonomy_version"]),
            counts={str(key): int(value) for key, value in dict(raw["counts"]).items()},
            data_sha256=str(raw["data_sha256"]),
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise PublicProjectionError(f"invalid projection manifest: {manifest_path}") from exc

    if manifest.schema_version != PUBLIC_SCHEMA_VERSION:
        raise PublicProjectionError(f"unsupported public schema: {manifest.schema_version}")
    if manifest.projection_version != PUBLIC_PROJECTION_VERSION:
        raise PublicProjectionError(f"unsupported projection version: {manifest.projection_version}")
    if set(manifest.counts) != set(PUBLIC_COUNT_KEYS):
        raise PublicProjectionError("projection manifest counts do not match the public contract")
    if manifest.quality_status != "complete" and not allow_partial_preview:
        raise PublicProjectionError("preview projection requires explicit preview validation")
    if manifest.release_kind not in {"public", "preview"}:
        raise PublicProjectionError(f"unsupported projection release kind: {manifest.release_kind}")
    if manifest.publishable != (manifest.quality_status == "complete"):
        raise PublicProjectionError("projection publishability does not match quality status")

    with _open_read_only(database_path) as con:
        _validate_projection_schema(con)
        _validate_projection_meta(con, manifest)
        _validate_snapshot_binding(con, manifest.snapshot_id)
        counts = _projection_counts(con)
        if counts != manifest.counts:
            raise PublicProjectionError(f"projection row-count mismatch: expected {manifest.counts}, got {counts}")
        if _data_sha256(con) != manifest.data_sha256:
            raise PublicProjectionError("projection data hash mismatch")
    return manifest


def _create_projection(source: sqlite3.Connection, target_path: Path, snapshot: sqlite3.Row, counts: dict[str, int]) -> None:
    snapshot_id = str(snapshot["snapshot_id"])
    quality_status = str(snapshot["quality_status"])
    release_kind = "public" if quality_status == "complete" else "preview"
    with sqlite3.connect(target_path) as target:
        target.executescript(
            """
            CREATE TABLE public_meta (
              singleton INTEGER PRIMARY KEY CHECK (singleton = 1), snapshot_id TEXT NOT NULL,
              taxonomy_version TEXT NOT NULL, quality_status TEXT NOT NULL, as_of_at TEXT NOT NULL,
              people_count INTEGER NOT NULL, org_units_count INTEGER NOT NULL, departments_count INTEGER NOT NULL,
              projection_version TEXT NOT NULL, release_kind TEXT NOT NULL CHECK (release_kind IN ('public', 'preview')),
              publishable INTEGER NOT NULL CHECK (publishable IN (0, 1))
            );
            CREATE TABLE canonical_snapshots (
              snapshot_id TEXT PRIMARY KEY, as_of_at TEXT NOT NULL, people_count INTEGER NOT NULL,
              org_units_count INTEGER NOT NULL, departments_count INTEGER NOT NULL, quality_status TEXT NOT NULL
            );
            CREATE TABLE departments_current (
              department_dn TEXT PRIMARY KEY, department_id TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
              source_url TEXT NOT NULL, snapshot_id TEXT NOT NULL
            );
            CREATE TABLE organizations_current (
              org_dn TEXT PRIMARY KEY, org_id TEXT NOT NULL UNIQUE, name TEXT NOT NULL, parent_dn TEXT,
              department_dn TEXT NOT NULL, depth INTEGER NOT NULL, canonical_path_json TEXT NOT NULL,
              source_url TEXT NOT NULL, direct_people_count INTEGER NOT NULL, descendant_people_count INTEGER NOT NULL,
              child_count INTEGER NOT NULL, descendant_org_count INTEGER NOT NULL, snapshot_id TEXT NOT NULL
            );
            CREATE TABLE people_current (
              source_url TEXT PRIMARY KEY, display_name TEXT NOT NULL, title TEXT, org_path TEXT NOT NULL,
              org_dn TEXT NOT NULL, department_dn TEXT NOT NULL, department_name TEXT NOT NULL, org_unit TEXT NOT NULL,
              canonical_path_json TEXT NOT NULL, snapshot_id TEXT NOT NULL, presence_status TEXT NOT NULL
            );
            CREATE TABLE career_entities (
              entity_id TEXT PRIMARY KEY, entity_kind TEXT NOT NULL, org_id TEXT, title TEXT NOT NULL,
              organization_name TEXT NOT NULL, ancestor_text TEXT NOT NULL, snapshot_id TEXT NOT NULL
            );
            CREATE VIRTUAL TABLE career_entities_fts USING fts5(
              entity_id UNINDEXED, title, organization_name, ancestor_text,
              tokenize='unicode61 remove_diacritics 2'
            );
            CREATE TABLE career_matches (
              entity_id TEXT NOT NULL, category_id TEXT NOT NULL, score INTEGER NOT NULL,
              confidence TEXT NOT NULL, evidence_json TEXT NOT NULL, taxonomy_version TEXT NOT NULL,
              PRIMARY KEY (entity_id, category_id)
            );
            CREATE TABLE vacancy_signals (
              entity_id TEXT PRIMARY KEY, source_text TEXT NOT NULL, title TEXT NOT NULL, org_id TEXT,
              snapshot_id TEXT NOT NULL, confidence TEXT NOT NULL, reasons_json TEXT NOT NULL
            );
            CREATE INDEX idx_public_org_parent_name ON organizations_current(parent_dn, name COLLATE NOCASE);
            CREATE INDEX idx_public_people_org_title ON people_current(org_dn, title COLLATE NOCASE);
            """
        )
        target.execute(
            "INSERT INTO public_meta VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                snapshot_id, str(snapshot["taxonomy_version"]), quality_status, str(snapshot["as_of_at"]),
                counts["people"], counts["organizations"], counts["departments"],
                PUBLIC_PROJECTION_VERSION, release_kind, int(quality_status == "complete"),
            ),
        )
        _copy_rows(source, target, "canonical_snapshots", "snapshot_id = ?", (snapshot_id,))
        _copy_rows(source, target, "departments_current", "snapshot_id = ?", (snapshot_id,))
        _copy_rows(source, target, "organizations_current", "snapshot_id = ?", (snapshot_id,))
        _copy_rows(source, target, "people_current", "snapshot_id = ? AND presence_status = 'present'", (snapshot_id,))
        _copy_rows(source, target, "career_entities", "snapshot_id = ?", (snapshot_id,))
        target.execute(
            "INSERT INTO career_entities_fts (entity_id, title, organization_name, ancestor_text) "
            "SELECT entity_id, title, organization_name, ancestor_text FROM career_entities ORDER BY entity_id"
        )
        _copy_rows(source, target, "career_matches", "entity_id IN (SELECT entity_id FROM career_entities)", ())
        _copy_rows(source, target, "vacancy_signals", "snapshot_id = ?", (snapshot_id,))
        target.commit()


def _copy_rows(source: sqlite3.Connection, target: sqlite3.Connection, table: str, where: str, params: Iterable[object]) -> None:
    columns = PUBLIC_TABLE_COLUMNS[table]
    quoted = ", ".join(columns)
    rows = source.execute(
        f"SELECT {quoted} FROM {table} WHERE {where} ORDER BY {columns[0]}", tuple(params)
    )
    placeholders = ", ".join("?" for _ in columns)
    target.executemany(
        f"INSERT INTO {table} ({quoted}) VALUES ({placeholders})",
        (tuple(row[column] for column in columns) for row in rows),
    )


def _source_snapshot(source: sqlite3.Connection) -> sqlite3.Row:
    row = source.execute(
        """SELECT snapshots.snapshot_id,snapshots.as_of_at,snapshots.people_count,
                  snapshots.org_units_count,snapshots.departments_count,snapshots.quality_status,
                  state.taxonomy_version
           FROM career_index_state AS state
           JOIN canonical_snapshots AS snapshots ON snapshots.snapshot_id=state.snapshot_id
           WHERE state.singleton=1"""
    ).fetchone()
    if row is None:
        raise PublicProjectionError("canonical master has no current indexed snapshot")
    return row


def _source_counts(source: sqlite3.Connection, snapshot_id: str) -> dict[str, int]:
    return {
        "departments": int(source.execute("SELECT COUNT(*) FROM departments_current WHERE snapshot_id=?", (snapshot_id,)).fetchone()[0]),
        "organizations": int(source.execute("SELECT COUNT(*) FROM organizations_current WHERE snapshot_id=?", (snapshot_id,)).fetchone()[0]),
        "people": int(source.execute("SELECT COUNT(*) FROM people_current WHERE snapshot_id=? AND presence_status='present'", (snapshot_id,)).fetchone()[0]),
        "career_entities": int(source.execute("SELECT COUNT(*) FROM career_entities WHERE snapshot_id=?", (snapshot_id,)).fetchone()[0]),
    }


def _projection_counts(con: sqlite3.Connection) -> dict[str, int]:
    return {
        "departments": int(con.execute("SELECT COUNT(*) FROM departments_current").fetchone()[0]),
        "organizations": int(con.execute("SELECT COUNT(*) FROM organizations_current").fetchone()[0]),
        "people": int(con.execute("SELECT COUNT(*) FROM people_current WHERE presence_status='present'").fetchone()[0]),
        "career_entities": int(con.execute("SELECT COUNT(*) FROM career_entities").fetchone()[0]),
    }


def _data_sha256(con: sqlite3.Connection) -> str:
    digest = hashlib.sha256()
    for table in sorted(PUBLIC_TABLE_COLUMNS):
        if table == "public_meta":
            continue
        columns = PUBLIC_TABLE_COLUMNS[table]
        digest.update(f"table:{table}\n".encode("utf-8"))
        order = ", ".join(columns)
        for row in con.execute(f"SELECT {', '.join(columns)} FROM {table} ORDER BY {order}"):
            payload = {column: row[column] for column in columns}
            digest.update((json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8"))
    return digest.hexdigest()


def _require_source_tables(con: sqlite3.Connection) -> None:
    required = {
        "canonical_snapshots", "career_index_state", "departments_current",
        "organizations_current", "people_current", "career_entities",
        "career_matches", "vacancy_signals",
    }
    actual = {str(row[0]) for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    missing = sorted(required - actual)
    if missing:
        raise PublicProjectionError(f"canonical master is missing indexed tables: {', '.join(missing)}")


def _validate_projection_schema(con: sqlite3.Connection) -> None:
    actual_tables = {str(row[0]) for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    expected_tables = set(PUBLIC_TABLE_COLUMNS) | PUBLIC_FTS_INTERNAL_TABLES
    missing_tables = expected_tables - actual_tables
    unexpected_tables = actual_tables - expected_tables
    if missing_tables or unexpected_tables:
        details = []
        if missing_tables:
            details.append(f"missing={','.join(sorted(missing_tables))}")
        if unexpected_tables:
            details.append(f"unexpected={','.join(sorted(unexpected_tables))}")
        raise PublicProjectionError("public projection table allow-list failed: " + "; ".join(details))
    for table, expected_columns in PUBLIC_TABLE_COLUMNS.items():
        actual_columns = tuple(str(row[1]) for row in con.execute(f"PRAGMA table_info({table})"))
        if actual_columns != expected_columns:
            raise PublicProjectionError(f"public projection column allow-list failed for {table}: {actual_columns}")
        if any(_looks_private(column) for column in actual_columns):
            raise PublicProjectionError(f"private column found in public table {table}")


def _validate_projection_meta(con: sqlite3.Connection, manifest: PublicProjectionManifest) -> None:
    row = con.execute("SELECT * FROM public_meta WHERE singleton=1").fetchone()
    if row is None:
        raise PublicProjectionError("public projection metadata row is missing")
    for key in ("snapshot_id", "taxonomy_version", "quality_status", "as_of_at", "projection_version", "release_kind"):
        if str(row[key]) != str(getattr(manifest, key)):
            raise PublicProjectionError(f"public metadata mismatch for {key}")
    if bool(row["publishable"]) != manifest.publishable:
        raise PublicProjectionError("public metadata mismatch for publishable")


def _validate_snapshot_binding(con: sqlite3.Connection, snapshot_id: str) -> None:
    count = int(con.execute("SELECT COUNT(*) FROM canonical_snapshots WHERE snapshot_id=?", (snapshot_id,)).fetchone()[0])
    if count != 1:
        raise PublicProjectionError("public projection snapshot manifest is not singular")
    for table in PUBLIC_SNAPSHOT_TABLES - {"canonical_snapshots"}:
        other = int(con.execute(f"SELECT COUNT(*) FROM {table} WHERE snapshot_id != ?", (snapshot_id,)).fetchone()[0])
        if other:
            raise PublicProjectionError(f"public projection contains rows from another snapshot: {table}")


def _looks_private(column: str) -> bool:
    normalized = column.casefold()
    return any(token in normalized for token in (
        "email", "phone", "telephone", "fax", "address", "crawl", "control",
        "queue", "error", "run_id", "last_seen", "source_fingerprint", "source_path",
    ))


def _open_read_only(path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA query_only=ON")
    return con

