from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from pathlib import Path

from .canonical_models import (
    CanonicalDepartment,
    CanonicalOrganization,
    CanonicalPerson,
    CanonicalSnapshot,
    CanonicalSource,
    CurrentPerson,
    PersonChangeEvent,
    SnapshotMember,
)


class CanonicalStore:
    """Transactional storage for canonical person snapshots and their history."""

    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)
        self.con: sqlite3.Connection | None = None

    def __enter__(self) -> "CanonicalStore":
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.con = sqlite3.connect(self.db_path)
        self.con.row_factory = sqlite3.Row
        self.con.execute("PRAGMA foreign_keys = ON")
        self.con.execute("PRAGMA journal_mode = WAL")
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self.con is not None:
            self.con.close()
            self.con = None

    @property
    def db(self) -> sqlite3.Connection:
        if self.con is None:
            raise RuntimeError("CanonicalStore must be used as a context manager")
        return self.con

    def init_schema(self) -> None:
        self.db.executescript(
            """
            CREATE TABLE IF NOT EXISTS canonical_snapshots (
              snapshot_id TEXT PRIMARY KEY,
              parent_snapshot_id TEXT,
              as_of_at TEXT NOT NULL,
              source_fingerprint TEXT NOT NULL,
              people_count INTEGER NOT NULL CHECK (people_count >= 0),
              org_units_count INTEGER NOT NULL CHECK (org_units_count >= 0),
              departments_count INTEGER NOT NULL CHECK (departments_count >= 0),
              baseline INTEGER NOT NULL CHECK (baseline IN (0, 1)),
              quality_status TEXT NOT NULL DEFAULT 'complete',
              quality_warnings_json TEXT NOT NULL DEFAULT '[]',
              fallback_org_count INTEGER NOT NULL DEFAULT 0,
              root_count INTEGER NOT NULL DEFAULT 0,
              missing_parent_count INTEGER NOT NULL DEFAULT 0,
              cycle_count INTEGER NOT NULL DEFAULT 0,
              max_depth INTEGER NOT NULL DEFAULT 0,
              FOREIGN KEY (parent_snapshot_id) REFERENCES canonical_snapshots(snapshot_id)
            );

            CREATE TABLE IF NOT EXISTS canonical_snapshot_members (
              snapshot_id TEXT NOT NULL,
              source_url TEXT NOT NULL,
              display_name TEXT NOT NULL,
              title TEXT,
              org_path TEXT NOT NULL,
              PRIMARY KEY (snapshot_id, source_url),
              FOREIGN KEY (snapshot_id) REFERENCES canonical_snapshots(snapshot_id)
            );

            CREATE TABLE IF NOT EXISTS people_current (
              source_url TEXT PRIMARY KEY,
              display_name TEXT NOT NULL,
              title TEXT,
              org_path TEXT NOT NULL,
              org_dn TEXT NOT NULL DEFAULT '',
              department_dn TEXT NOT NULL DEFAULT '',
              department_name TEXT NOT NULL DEFAULT '',
              org_unit TEXT NOT NULL DEFAULT '',
              canonical_path_json TEXT NOT NULL DEFAULT '[]',
              last_seen_at TEXT NOT NULL DEFAULT '',
              snapshot_id TEXT NOT NULL,
              missing_streak INTEGER NOT NULL DEFAULT 0,
              presence_status TEXT NOT NULL DEFAULT 'present',
              FOREIGN KEY (snapshot_id) REFERENCES canonical_snapshots(snapshot_id)
            );

            CREATE TABLE IF NOT EXISTS canonical_snapshot_sources (
              snapshot_id TEXT NOT NULL,
              source_path TEXT NOT NULL,
              source_role TEXT NOT NULL CHECK (source_role IN ('base', 'overlay')),
              precedence INTEGER NOT NULL,
              source_sha256 TEXT NOT NULL,
              PRIMARY KEY (snapshot_id, source_path),
              FOREIGN KEY (snapshot_id) REFERENCES canonical_snapshots(snapshot_id)
            );

            CREATE TABLE IF NOT EXISTS departments_current (
              department_dn TEXT PRIMARY KEY,
              department_id TEXT NOT NULL UNIQUE,
              name TEXT NOT NULL,
              source_url TEXT NOT NULL,
              snapshot_id TEXT NOT NULL,
              FOREIGN KEY (snapshot_id) REFERENCES canonical_snapshots(snapshot_id)
            );

            CREATE TABLE IF NOT EXISTS organizations_current (
              org_dn TEXT PRIMARY KEY,
              org_id TEXT NOT NULL UNIQUE,
              name TEXT NOT NULL,
              parent_dn TEXT,
              department_dn TEXT NOT NULL,
              depth INTEGER NOT NULL,
              canonical_path_json TEXT NOT NULL,
              source_url TEXT NOT NULL,
              direct_people_count INTEGER NOT NULL,
              descendant_people_count INTEGER NOT NULL,
              child_count INTEGER NOT NULL,
              descendant_org_count INTEGER NOT NULL,
              snapshot_id TEXT NOT NULL,
              FOREIGN KEY (snapshot_id) REFERENCES canonical_snapshots(snapshot_id)
            );

            CREATE TABLE IF NOT EXISTS person_change_events (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              snapshot_id TEXT NOT NULL,
              person_key TEXT NOT NULL,
              event_type TEXT NOT NULL,
              occurred_at TEXT NOT NULL,
              details_json TEXT NOT NULL,
              FOREIGN KEY (snapshot_id) REFERENCES canonical_snapshots(snapshot_id)
            );

            CREATE TABLE IF NOT EXISTS canonical_state (
              singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
              current_snapshot_id TEXT,
              FOREIGN KEY (current_snapshot_id) REFERENCES canonical_snapshots(snapshot_id)
            );

            CREATE INDEX IF NOT EXISTS idx_person_change_events_person_time
              ON person_change_events (person_key, occurred_at);
            CREATE INDEX IF NOT EXISTS idx_person_change_events_snapshot_type
              ON person_change_events (snapshot_id, event_type);
            """
        )
        for column, definition in (
            ("missing_streak", "INTEGER NOT NULL DEFAULT 0"),
            ("presence_status", "TEXT NOT NULL DEFAULT 'present'"),
            ("org_dn", "TEXT NOT NULL DEFAULT ''"),
            ("department_dn", "TEXT NOT NULL DEFAULT ''"),
            ("department_name", "TEXT NOT NULL DEFAULT ''"),
            ("org_unit", "TEXT NOT NULL DEFAULT ''"),
            ("canonical_path_json", "TEXT NOT NULL DEFAULT '[]'"),
            ("last_seen_at", "TEXT NOT NULL DEFAULT ''"),
        ):
            self._ensure_column("people_current", column, definition)
        for column, definition in (
            ("quality_status", "TEXT NOT NULL DEFAULT 'complete'"),
            ("quality_warnings_json", "TEXT NOT NULL DEFAULT '[]'"),
            ("fallback_org_count", "INTEGER NOT NULL DEFAULT 0"),
            ("root_count", "INTEGER NOT NULL DEFAULT 0"),
            ("missing_parent_count", "INTEGER NOT NULL DEFAULT 0"),
            ("cycle_count", "INTEGER NOT NULL DEFAULT 0"),
            ("max_depth", "INTEGER NOT NULL DEFAULT 0"),
        ):
            self._ensure_column("canonical_snapshots", column, definition)
        self.db.executescript(
            """
            CREATE INDEX IF NOT EXISTS idx_org_current_parent_name
              ON organizations_current (parent_dn, name COLLATE NOCASE);
            CREATE INDEX IF NOT EXISTS idx_org_current_department_depth
              ON organizations_current (department_dn, depth);
            CREATE INDEX IF NOT EXISTS idx_people_current_org_title
              ON people_current (org_dn, title COLLATE NOCASE);
            CREATE INDEX IF NOT EXISTS idx_people_current_department
              ON people_current (department_dn);
            """
        )
        self.db.execute(
            "INSERT INTO canonical_state (singleton, current_snapshot_id) VALUES (1, NULL) "
            "ON CONFLICT(singleton) DO NOTHING"
        )
        self.db.commit()

    @contextmanager
    def transaction(self) -> Iterator[None]:
        if self.db.in_transaction:
            raise RuntimeError("CanonicalStore transaction cannot be nested")

        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield
        except BaseException:
            self.db.rollback()
            raise
        else:
            self.db.commit()

    def current_snapshot(self) -> str | None:
        row = self.db.execute(
            "SELECT current_snapshot_id FROM canonical_state WHERE singleton = 1"
        ).fetchone()
        return None if row is None else row["current_snapshot_id"]

    def current_manifest(self) -> dict | None:
        snapshot_id = self.current_snapshot()
        if snapshot_id is None:
            return None
        row = self.db.execute(
            "SELECT * FROM canonical_snapshots WHERE snapshot_id = ?",
            (snapshot_id,),
        ).fetchone()
        return None if row is None else dict(row)

    def quality_warnings(self) -> tuple[str, ...]:
        manifest = self.current_manifest()
        if manifest is None:
            return ()
        values = json.loads(str(manifest["quality_warnings_json"]))
        return tuple(str(value) for value in values)

    def insert_snapshot(
        self,
        snapshot: CanonicalSnapshot,
        members: Iterable[SnapshotMember] = (),
    ) -> None:
        self.db.execute(
            """
            INSERT INTO canonical_snapshots
              (snapshot_id, parent_snapshot_id, as_of_at, source_fingerprint, people_count,
               org_units_count, departments_count, baseline, quality_status,
               quality_warnings_json, fallback_org_count, root_count,
               missing_parent_count, cycle_count, max_depth)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot.snapshot_id,
                snapshot.parent_snapshot_id,
                snapshot.as_of_at,
                snapshot.source_fingerprint,
                snapshot.people_count,
                snapshot.org_units_count,
                snapshot.departments_count,
                snapshot.baseline,
                snapshot.quality_status,
                json.dumps(
                    snapshot.quality_warnings,
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
                snapshot.fallback_org_count,
                snapshot.root_count,
                snapshot.missing_parent_count,
                snapshot.cycle_count,
                snapshot.max_depth,
            ),
        )
        rows = []
        for member in members:
            if member.snapshot_id != snapshot.snapshot_id:
                raise ValueError("snapshot member must belong to the inserted snapshot")
            rows.append(
                (
                    member.snapshot_id,
                    member.source_url,
                    member.display_name,
                    member.title,
                    member.org_path,
                )
            )
        self.db.executemany(
            """
            INSERT INTO canonical_snapshot_members
              (snapshot_id, source_url, display_name, title, org_path)
            VALUES (?, ?, ?, ?, ?)
            """,
            rows,
        )

    def insert_sources(self, sources: Iterable[CanonicalSource]) -> None:
        self.db.executemany(
            """
            INSERT INTO canonical_snapshot_sources
              (snapshot_id, source_path, source_role, precedence, source_sha256)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (
                    source.snapshot_id,
                    source.source_path,
                    source.source_role,
                    source.precedence,
                    source.source_sha256,
                )
                for source in sources
            ],
        )

    def set_current_snapshot(self, snapshot_id: str) -> None:
        self.db.execute(
            "UPDATE canonical_state SET current_snapshot_id = ? WHERE singleton = 1",
            (snapshot_id,),
        )

    def replace_current_people(self, people: Iterable[CurrentPerson]) -> None:
        rows = [
            (
                person.source_url,
                person.display_name,
                person.title,
                person.org_path,
                person.snapshot_id,
            )
            for person in people
        ]
        self.db.execute("DELETE FROM people_current")
        self.db.executemany(
            """
            INSERT INTO people_current (source_url, display_name, title, org_path, snapshot_id)
            VALUES (?, ?, ?, ?, ?)
            """,
            rows,
        )

    def replace_current_projection(
        self,
        departments: Iterable[CanonicalDepartment],
        organizations: Iterable[CanonicalOrganization],
        people: Iterable[CanonicalPerson],
    ) -> None:
        self.db.execute("DELETE FROM people_current")
        self.db.execute("DELETE FROM organizations_current")
        self.db.execute("DELETE FROM departments_current")
        self.db.executemany(
            """
            INSERT INTO departments_current
              (department_dn, department_id, name, source_url, snapshot_id)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (
                    department.dn,
                    department.department_id,
                    department.name,
                    department.source_url,
                    department.snapshot_id,
                )
                for department in departments
            ],
        )
        self.db.executemany(
            """
            INSERT INTO organizations_current
              (org_dn, org_id, name, parent_dn, department_dn, depth,
               canonical_path_json, source_url, direct_people_count,
               descendant_people_count, child_count, descendant_org_count,
               snapshot_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    organization.dn,
                    organization.org_id,
                    organization.name,
                    organization.parent_dn,
                    organization.department_dn,
                    organization.depth,
                    json.dumps(
                        organization.canonical_path,
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ),
                    organization.source_url,
                    organization.direct_people_count,
                    organization.descendant_people_count,
                    organization.child_count,
                    organization.descendant_org_count,
                    organization.snapshot_id,
                )
                for organization in organizations
            ],
        )
        self.db.executemany(
            """
            INSERT INTO people_current
              (source_url, display_name, title, org_path, org_dn, department_dn,
               department_name, org_unit, canonical_path_json, last_seen_at,
               snapshot_id, missing_streak, presence_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 'present')
            """,
            [
                (
                    person.source_url,
                    person.display_name,
                    person.title,
                    " / ".join(person.canonical_path),
                    person.org_dn,
                    person.department_dn,
                    person.department_name,
                    person.org_unit,
                    json.dumps(
                        person.canonical_path,
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ),
                    person.last_seen_at,
                    person.snapshot_id,
                )
                for person in people
            ],
        )

    def append_events(self, events: Iterable[PersonChangeEvent]) -> None:
        self.db.executemany(
            """
            INSERT INTO person_change_events
              (snapshot_id, person_key, event_type, occurred_at, details_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (
                    event.snapshot_id,
                    event.person_key,
                    event.event_type,
                    event.occurred_at,
                    event.details_json,
                )
                for event in events
            ],
        )

    def index_names(self) -> set[str]:
        return {
            row["name"]
            for row in self.db.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index' AND name IS NOT NULL"
            )
        }

    def table_names(self) -> set[str]:
        return {
            row["name"]
            for row in self.db.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }

    def _ensure_column(self, table: str, column: str, definition: str) -> None:
        columns = {
            row["name"]
            for row in self.db.execute(f"PRAGMA table_info({table})")
        }
        if column not in columns:
            self.db.execute(
                f"ALTER TABLE {table} ADD COLUMN {column} {definition}"
            )
