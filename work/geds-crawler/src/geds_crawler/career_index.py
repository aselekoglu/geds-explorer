from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable

from .career_matcher import CareerMatcher, MatchEntity, confidence_for
from .career_taxonomy import CareerTaxonomy, QueryInterpretation, load_taxonomy, normalize_text, tokenize


@dataclass(frozen=True)
class VacancySignal:
    confidence: str
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class IndexBuildReport:
    snapshot_id: str
    taxonomy_version: str
    organization_count: int
    people_count: int
    entity_count: int
    vacancy_signal_count: int


@dataclass(frozen=True)
class _IndexEntity:
    entity_id: str
    entity_kind: str
    org_id: str | None
    title: str
    organization_name: str
    ancestor_text: str
    snapshot_id: str
    display_name: str = ""

    @property
    def match_entity(self) -> MatchEntity:
        return MatchEntity(
            id=self.entity_id,
            kind=self.entity_kind,
            title=self.title,
            organization=self.organization_name,
            ancestors=tuple(part for part in self.ancestor_text.split(" / ") if part),
        )


def build_career_index(master_db: Path | str, taxonomy_path: Path | str) -> IndexBuildReport:
    taxonomy = load_taxonomy(taxonomy_path)
    db_path = Path(master_db)
    if not db_path.exists():
        raise ValueError(f"canonical master database does not exist: {db_path}")

    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    try:
        manifest = _current_manifest(con)
        entities, organization_count, people_count = _current_entities(con, manifest["snapshot_id"])
        matcher = CareerMatcher(taxonomy)
        _build_transactional_index(con, entities, matcher, taxonomy, manifest["snapshot_id"])
    finally:
        con.close()

    vacancy_count = sum(
        parse_vacancy_signal(entity.display_name, entity.title).confidence != "none"
        for entity in entities
        if entity.entity_kind == "person"
    )
    return IndexBuildReport(
        snapshot_id=str(manifest["snapshot_id"]),
        taxonomy_version=taxonomy.version,
        organization_count=organization_count,
        people_count=people_count,
        entity_count=len(entities),
        vacancy_signal_count=vacancy_count,
    )


def current_index_state(master_db: Path | str) -> dict[str, object]:
    con = sqlite3.connect(master_db)
    con.row_factory = sqlite3.Row
    try:
        row = con.execute("SELECT * FROM career_index_state WHERE singleton = 1").fetchone()
    except sqlite3.OperationalError as exc:
        raise ValueError("career index has not been built") from exc
    finally:
        con.close()
    if row is None:
        raise ValueError("career index has not been built")
    return dict(row)


def parse_vacancy_signal(display_name: str, title: str | None) -> VacancySignal:
    tokens = tokenize(display_name)
    markers = {"vacant", "vacancy", "inoccupe", "inoccupee", "inocuppe"}
    normalized_markers = {normalize_text(marker) for marker in markers}
    marker_tokens = tuple(token for token in tokens if token in normalized_markers)
    if not marker_tokens:
        return VacancySignal("none", ())

    allowed = normalized_markers | {"position", "poste"}
    remaining = tuple(token for token in tokens if token not in normalized_markers)
    if all(token in allowed or token.isdigit() for token in remaining):
        reasons = tuple(sorted({f"placeholder_marker:{token}" for token in marker_tokens}))
        if remaining:
            reasons += ("placeholder_shape:allowed_remaining_tokens",)
        return VacancySignal("high", reasons)
    return VacancySignal("none", ())


def _current_manifest(con: sqlite3.Connection) -> sqlite3.Row:
    row = con.execute(
        """
        SELECT snapshots.*
        FROM canonical_state AS state
        JOIN canonical_snapshots AS snapshots ON snapshots.snapshot_id = state.current_snapshot_id
        WHERE state.singleton = 1
        """
    ).fetchone()
    if row is None:
        raise ValueError("canonical master has no current snapshot")
    return row


def _current_entities(
    con: sqlite3.Connection,
    snapshot_id: str,
) -> tuple[list[_IndexEntity], int, int]:
    organizations = con.execute(
        """
        SELECT org_dn, org_id, name, canonical_path_json
        FROM organizations_current
        WHERE snapshot_id = ?
        ORDER BY org_id
        """,
        (snapshot_id,),
    ).fetchall()
    by_dn = {row["org_dn"]: row for row in organizations}
    entities: list[_IndexEntity] = []
    for row in organizations:
        path = tuple(json.loads(row["canonical_path_json"]))
        entities.append(
            _IndexEntity(
                entity_id=f"org:{row['org_id']}",
                entity_kind="organization",
                org_id=str(row["org_id"]),
                title="",
                organization_name=str(row["name"]),
                ancestor_text=" / ".join(path[:-1]),
                snapshot_id=snapshot_id,
            )
        )

    people = con.execute(
        """
        SELECT source_url, display_name, title, org_dn, org_unit
        FROM people_current
        WHERE snapshot_id = ? AND presence_status = 'present'
        ORDER BY source_url
        """,
        (snapshot_id,),
    ).fetchall()
    for row in people:
        organization = by_dn.get(row["org_dn"])
        path = tuple(json.loads(organization["canonical_path_json"])) if organization else ()
        entities.append(
            _IndexEntity(
                entity_id=f"person:{row['source_url']}",
                entity_kind="person",
                org_id=None if organization is None else str(organization["org_id"]),
                title="" if row["title"] is None else str(row["title"]),
                organization_name=str(organization["name"]) if organization else str(row["org_unit"]),
                ancestor_text=" / ".join(path),
                snapshot_id=snapshot_id,
                display_name=str(row["display_name"]),
            )
        )
    return entities, len(organizations), len(people)


def _build_transactional_index(
    con: sqlite3.Connection,
    entities: Iterable[_IndexEntity],
    matcher: CareerMatcher,
    taxonomy: CareerTaxonomy,
    snapshot_id: str,
) -> None:
    entity_list = list(entities)
    _drop_next_tables(con)
    con.execute("BEGIN IMMEDIATE")
    try:
        _create_next_tables(con)
        for entity in entity_list:
            _insert_entity(con, entity)
            _insert_matches(con, entity, matcher, taxonomy)
            _insert_vacancy_signal(con, entity)
        _validate_next_tables(con, len(entity_list), snapshot_id)
        _swap_next_tables(con, snapshot_id, taxonomy.version, entity_list)
    except BaseException:
        con.rollback()
        raise
    else:
        con.commit()


def _drop_next_tables(con: sqlite3.Connection) -> None:
    for table in ("career_entities_fts_next", "career_matches_next", "vacancy_signals_next", "career_entities_next"):
        con.execute(f"DROP TABLE IF EXISTS {table}")


def _create_next_tables(con: sqlite3.Connection) -> None:
    con.executescript(
        """
        CREATE TABLE career_entities_next (
          entity_id TEXT PRIMARY KEY,
          entity_kind TEXT NOT NULL CHECK (entity_kind IN ('person', 'organization')),
          org_id TEXT,
          title TEXT NOT NULL,
          organization_name TEXT NOT NULL,
          ancestor_text TEXT NOT NULL,
          normalized_title TEXT NOT NULL,
          normalized_organization TEXT NOT NULL,
          normalized_ancestors TEXT NOT NULL,
          snapshot_id TEXT NOT NULL,
          FOREIGN KEY (snapshot_id) REFERENCES canonical_snapshots(snapshot_id)
        );
        CREATE VIRTUAL TABLE career_entities_fts_next USING fts5(
          entity_id UNINDEXED,
          title,
          organization_name,
          ancestor_text,
          tokenize='unicode61 remove_diacritics 2'
        );
        CREATE TABLE career_matches_next (
          entity_id TEXT NOT NULL,
          category_id TEXT NOT NULL,
          score INTEGER NOT NULL,
          confidence TEXT NOT NULL,
          evidence_json TEXT NOT NULL,
          taxonomy_version TEXT NOT NULL,
          PRIMARY KEY(entity_id, category_id),
          FOREIGN KEY (entity_id) REFERENCES career_entities_next(entity_id)
        );
        CREATE TABLE vacancy_signals_next (
          entity_id TEXT PRIMARY KEY,
          source_text TEXT NOT NULL,
          title TEXT NOT NULL,
          org_id TEXT,
          snapshot_id TEXT NOT NULL,
          confidence TEXT NOT NULL,
          reasons_json TEXT NOT NULL,
          FOREIGN KEY (entity_id) REFERENCES career_entities_next(entity_id),
          FOREIGN KEY (snapshot_id) REFERENCES canonical_snapshots(snapshot_id)
        );
        """
    )


def _insert_entity(con: sqlite3.Connection, entity: _IndexEntity) -> None:
    con.execute(
        """
        INSERT INTO career_entities_next
          (entity_id, entity_kind, org_id, title, organization_name, ancestor_text,
           normalized_title, normalized_organization, normalized_ancestors, snapshot_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            entity.entity_id,
            entity.entity_kind,
            entity.org_id,
            entity.title,
            entity.organization_name,
            entity.ancestor_text,
            normalize_text(entity.title),
            normalize_text(entity.organization_name),
            normalize_text(entity.ancestor_text),
            entity.snapshot_id,
        ),
    )
    con.execute(
        """
        INSERT INTO career_entities_fts_next (entity_id, title, organization_name, ancestor_text)
        VALUES (?, ?, ?, ?)
        """,
        (entity.entity_id, entity.title, entity.organization_name, entity.ancestor_text),
    )


def _insert_matches(
    con: sqlite3.Connection,
    entity: _IndexEntity,
    matcher: CareerMatcher,
    taxonomy: CareerTaxonomy,
) -> None:
    for category in taxonomy.categories:
        interpretation = QueryInterpretation(
            original_query=category.id,
            normalized_query=normalize_text(category.id),
            category_ids=(category.id,),
            expanded_terms=tuple(sorted(term.normalized for term in category.terms)),
            evidence=(),
            taxonomy_version=taxonomy.version,
        )
        result = matcher.match_entity(entity.match_entity, interpretation)
        if category.id not in result.category_ids:
            continue
        evidence = tuple(item for item in result.evidence if item.category_id == category.id)
        score = sum(item.weight for item in evidence)
        if evidence and all(item.field == "ancestor" for item in evidence):
            score = min(score, 60)
        con.execute(
            """
            INSERT INTO career_matches_next
              (entity_id, category_id, score, confidence, evidence_json, taxonomy_version)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                entity.entity_id,
                category.id,
                score,
                confidence_for(score),
                json.dumps([asdict(item) for item in evidence], ensure_ascii=False, separators=(",", ":")),
                taxonomy.version,
            ),
        )


def _insert_vacancy_signal(con: sqlite3.Connection, entity: _IndexEntity) -> None:
    if entity.entity_kind != "person":
        return
    signal = parse_vacancy_signal(entity.display_name, entity.title)
    if signal.confidence == "none":
        return
    con.execute(
        """
        INSERT INTO vacancy_signals_next
          (entity_id, source_text, title, org_id, snapshot_id, confidence, reasons_json)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            entity.entity_id,
            entity.display_name,
            entity.title,
            entity.org_id,
            entity.snapshot_id,
            signal.confidence,
            json.dumps(signal.reasons, ensure_ascii=False, separators=(",", ":")),
        ),
    )


def _validate_next_tables(con: sqlite3.Connection, expected_entities: int, snapshot_id: str) -> None:
    entity_count = con.execute("SELECT COUNT(*) FROM career_entities_next").fetchone()[0]
    fts_count = con.execute("SELECT COUNT(*) FROM career_entities_fts_next").fetchone()[0]
    if entity_count != expected_entities or fts_count != expected_entities:
        raise ValueError("career index row-count validation failed")
    invalid_snapshot_rows = con.execute(
        "SELECT COUNT(*) FROM career_entities_next WHERE snapshot_id != ?", (snapshot_id,)
    ).fetchone()[0]
    if invalid_snapshot_rows:
        raise ValueError("career index snapshot validation failed")
    foreign_keys = con.execute("PRAGMA foreign_key_check").fetchall()
    if foreign_keys:
        raise ValueError("career index foreign-key validation failed")


def _swap_next_tables(
    con: sqlite3.Connection,
    snapshot_id: str,
    taxonomy_version: str,
    entities: list[_IndexEntity],
) -> None:
    for table in ("career_entities_fts", "career_matches", "vacancy_signals", "career_entities"):
        con.execute(f"DROP TABLE IF EXISTS {table}")
    con.execute("ALTER TABLE career_entities_next RENAME TO career_entities")
    con.execute("ALTER TABLE career_entities_fts_next RENAME TO career_entities_fts")
    con.execute("ALTER TABLE career_matches_next RENAME TO career_matches")
    con.execute("ALTER TABLE vacancy_signals_next RENAME TO vacancy_signals")
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS career_index_state (
          singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
          snapshot_id TEXT NOT NULL,
          taxonomy_version TEXT NOT NULL,
          entity_count INTEGER NOT NULL,
          organization_count INTEGER NOT NULL,
          people_count INTEGER NOT NULL,
          vacancy_signal_count INTEGER NOT NULL,
          built_at TEXT NOT NULL,
          FOREIGN KEY (snapshot_id) REFERENCES canonical_snapshots(snapshot_id)
        )
        """
    )
    organization_count = sum(entity.entity_kind == "organization" for entity in entities)
    people_count = sum(entity.entity_kind == "person" for entity in entities)
    vacancy_count = con.execute("SELECT COUNT(*) FROM vacancy_signals").fetchone()[0]
    con.execute(
        """
        INSERT INTO career_index_state
          (singleton, snapshot_id, taxonomy_version, entity_count, organization_count,
           people_count, vacancy_signal_count, built_at)
        VALUES (1, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(singleton) DO UPDATE SET
          snapshot_id=excluded.snapshot_id,
          taxonomy_version=excluded.taxonomy_version,
          entity_count=excluded.entity_count,
          organization_count=excluded.organization_count,
          people_count=excluded.people_count,
          vacancy_signal_count=excluded.vacancy_signal_count,
          built_at=excluded.built_at
        """,
        (
            snapshot_id,
            taxonomy_version,
            len(entities),
            organization_count,
            people_count,
            vacancy_count,
            datetime.now(UTC).isoformat(),
        ),
    )
