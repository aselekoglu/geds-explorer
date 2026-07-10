from __future__ import annotations

import sqlite3
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from pathlib import Path

from .canonical_models import CanonicalSnapshot, CurrentPerson, PersonChangeEvent, SnapshotMember


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

    def insert_snapshot(
        self,
        snapshot: CanonicalSnapshot,
        members: Iterable[SnapshotMember] = (),
    ) -> None:
        self.db.execute(
            """
            INSERT INTO canonical_snapshots
              (snapshot_id, parent_snapshot_id, as_of_at, source_fingerprint, people_count,
               org_units_count, departments_count, baseline)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
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
