from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from .career_leads import LeadSuggestion, infer_leads, load_lead_rules
from .career_taxonomy import load_taxonomy, normalize_text


MAX_PAGE_SIZE = 200
MAX_CONSTELLATION_SIZE = 2000


@dataclass(frozen=True)
class SearchItem:
    entity_id: str
    entity_kind: str
    org_id: str | None
    title: str
    organization_name: str
    score: int
    confidence: str
    evidence: tuple[dict, ...]


@dataclass(frozen=True)
class SearchResult:
    items: tuple[SearchItem, ...]
    limit: int
    snapshot_id: str
    quality_status: str
    etag: str


@dataclass(frozen=True)
class OrgNode:
    org_id: str
    name: str
    parent_id: str | None
    depth: int
    child_count: int
    descendant_people_count: int


@dataclass(frozen=True)
class OrgPage:
    items: tuple[OrgNode, ...]
    limit: int
    snapshot_id: str
    quality_status: str
    etag: str


@dataclass(frozen=True)
class ConstellationSlice:
    nodes: tuple[OrgNode, ...]
    limit: int
    truncated: bool
    snapshot_id: str
    quality_status: str
    etag: str


@dataclass(frozen=True)
class TeamProfile:
    org_id: str
    name: str
    department_name: str
    canonical_path: tuple[str, ...]
    direct_people_count: int
    descendant_people_count: int
    child_count: int
    snapshot_id: str
    snapshot_as_of: str
    quality_status: str
    conversation_leads: tuple[LeadSuggestion, ...]
    vacancy_signals: tuple["VacancySignal", ...]


@dataclass(frozen=True)
class VacancySignal:
    marker: str
    title: str
    org_id: str
    observed_at: str
    source_url: str
    confidence: str
    reasons: tuple[str, ...]
    live_competition_verified: bool = False


@dataclass(frozen=True)
class DepartmentItem:
    department_id: str
    name: str


@dataclass(frozen=True)
class DepartmentResult:
    items: tuple[DepartmentItem, ...]
    snapshot_id: str
    quality_status: str
    etag: str


@dataclass(frozen=True)
class TourResult:
    items: tuple[dict[str, object], ...]
    snapshot_id: str
    quality_status: str
    etag: str


class CareerRepository:
    def __init__(self, master_db: Path | str, taxonomy_path: Path | str | None = None):
        self.master_db = Path(master_db).resolve()
        self.taxonomy_path = Path(taxonomy_path) if taxonomy_path else Path(__file__).parent / "data" / "career_taxonomy.v1.json"
        self.tours_path = Path(__file__).parent / "data" / "career_tours.v1.json"
        self.lead_rules_path = Path(__file__).parent / "data" / "lead_titles.v1.json"

    def connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(f"file:{self.master_db.as_posix()}?mode=ro", uri=True, timeout=2)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA query_only=ON")
        con.execute("PRAGMA busy_timeout=2000")
        return con

    def meta(self) -> dict[str, object]:
        with self.connect() as con:
            return self._meta(con)

    def search(self, *, query: str, limit: int = 20) -> SearchResult:
        limit = _bounded(limit, MAX_PAGE_SIZE)
        taxonomy = load_taxonomy(self.taxonomy_path)
        interpretation = taxonomy.interpret(query)
        with self.connect() as con:
            meta = self._meta(con)
            if not interpretation.category_ids:
                return SearchResult((), limit, str(meta["snapshot_id"]), str(meta["quality_status"]), _etag(meta, query, limit))
            placeholders = ",".join("?" for _ in interpretation.category_ids)
            rows = con.execute(
                f"""
                SELECT e.entity_id, e.entity_kind, e.org_id, e.title, e.organization_name,
                       m.category_id, m.score, m.confidence, m.evidence_json
                FROM career_matches AS m
                JOIN career_entities AS e ON e.entity_id = m.entity_id
                WHERE m.category_id IN ({placeholders})
                ORDER BY m.score DESC, e.entity_id ASC
                """,
                interpretation.category_ids,
            ).fetchall()
        grouped: dict[str, dict] = {}
        for row in rows:
            entry = grouped.setdefault(str(row["entity_id"]), {"row": row, "score": 0, "evidence": []})
            entry["score"] += int(row["score"])
            entry["evidence"].extend(json.loads(row["evidence_json"]))
        items = tuple(
            SearchItem(
                entity_id=key,
                entity_kind=str(value["row"]["entity_kind"]),
                org_id=value["row"]["org_id"],
                title=str(value["row"]["title"]),
                organization_name=str(value["row"]["organization_name"]),
                score=value["score"],
                confidence=_confidence(value["score"]),
                evidence=tuple(value["evidence"]),
            )
            for key, value in sorted(grouped.items(), key=lambda item: (-item[1]["score"], item[0]))[:limit]
        )
        return SearchResult(items, limit, str(meta["snapshot_id"]), str(meta["quality_status"]), _etag(meta, query, limit))

    def children(self, *, parent_id: str | None, limit: int = 50) -> OrgPage:
        limit = _bounded(limit, MAX_PAGE_SIZE)
        with self.connect() as con:
            meta = self._meta(con)
            if parent_id is None:
                rows = con.execute("""SELECT o.org_id,o.name,NULL parent_id,o.depth,o.child_count,o.descendant_people_count FROM organizations_current o WHERE o.snapshot_id=? AND o.parent_dn IS NULL ORDER BY o.name,o.org_id LIMIT ?""", (meta["snapshot_id"], limit)).fetchall()
            else:
                rows = con.execute("""SELECT child.org_id,child.name,parent.org_id parent_id,child.depth,child.child_count,child.descendant_people_count FROM organizations_current child JOIN organizations_current parent ON parent.org_dn=child.parent_dn WHERE child.snapshot_id=? AND parent.org_id=? ORDER BY child.name,child.org_id LIMIT ?""", (meta["snapshot_id"], parent_id, limit)).fetchall()
        items = tuple(OrgNode(str(r["org_id"]), str(r["name"]), r["parent_id"], int(r["depth"]), int(r["child_count"]), int(r["descendant_people_count"])) for r in rows)
        return OrgPage(items, limit, str(meta["snapshot_id"]), str(meta["quality_status"]), _etag(meta, parent_id or "root", limit))

    def team_profile(self, org_id: str) -> TeamProfile:
        with self.connect() as con:
            meta = self._meta(con)
            row = con.execute("""SELECT o.*,d.name department_name FROM organizations_current o JOIN departments_current d ON d.department_dn=o.department_dn WHERE o.snapshot_id=? AND o.org_id=?""", (meta["snapshot_id"], org_id)).fetchone()
            people = con.execute(
                """WITH RECURSIVE lineage(org_dn,parent_dn,org_id,level) AS (
                       SELECT org_dn,parent_dn,org_id,0 FROM organizations_current
                       WHERE snapshot_id=? AND org_id=?
                       UNION ALL
                       SELECT parent.org_dn,parent.parent_dn,parent.org_id,lineage.level+1
                       FROM organizations_current parent JOIN lineage ON parent.org_dn=lineage.parent_dn
                       WHERE parent.snapshot_id=?
                   )
                   SELECT p.title,lineage.org_id,p.source_url,lineage.level
                   FROM lineage JOIN people_current p ON p.org_dn=lineage.org_dn
                   WHERE p.snapshot_id=? AND p.presence_status='present'
                   ORDER BY lineage.level,p.title,p.source_url""",
                (meta["snapshot_id"], org_id, meta["snapshot_id"], meta["snapshot_id"]),
            ).fetchall()
            vacancy_rows = con.execute(
                """SELECT v.source_text,v.title,v.org_id,p.last_seen_at,p.source_url,
                          v.confidence,v.reasons_json
                   FROM vacancy_signals v
                   JOIN people_current p ON v.entity_id='person:' || p.source_url
                   WHERE v.snapshot_id=? AND v.org_id=? AND p.snapshot_id=?
                   ORDER BY v.title,v.entity_id""",
                (meta["snapshot_id"], org_id, meta["snapshot_id"]),
            ).fetchall()
        if row is None:
            raise KeyError(org_id)
        parent_org_ids = tuple(str(person["org_id"]) for person in people if int(person["level"]) > 0)
        leads = infer_leads(
            org_id,
            (
                {"title": person["title"], "org_id": person["org_id"], "source_url": person["source_url"]}
                for person in people
            ),
            load_lead_rules(self.lead_rules_path),
            parent_org_ids=parent_org_ids,
        )
        vacancy_signals = tuple(
            VacancySignal(
                marker=str(vacancy["source_text"]),
                title=str(vacancy["title"]),
                org_id=str(vacancy["org_id"]),
                observed_at=str(vacancy["last_seen_at"]),
                source_url=str(vacancy["source_url"]),
                confidence=str(vacancy["confidence"]),
                reasons=tuple(json.loads(vacancy["reasons_json"])),
            )
            for vacancy in vacancy_rows
        )
        return TeamProfile(org_id, str(row["name"]), str(row["department_name"]), tuple(json.loads(row["canonical_path_json"])), int(row["direct_people_count"]), int(row["descendant_people_count"]), int(row["child_count"]), str(meta["snapshot_id"]), str(meta["as_of_at"]), str(meta["quality_status"]), leads, vacancy_signals)

    def departments(self) -> DepartmentResult:
        with self.connect() as con:
            meta = self._meta(con)
            rows = con.execute("SELECT department_id,name FROM departments_current WHERE snapshot_id=? ORDER BY name,department_id", (meta["snapshot_id"],)).fetchall()
        items = tuple(DepartmentItem(str(row["department_id"]), str(row["name"])) for row in rows)
        return DepartmentResult(items, str(meta["snapshot_id"]), str(meta["quality_status"]), _etag(meta, "departments"))

    def ancestors(self, org_id: str) -> OrgPage:
        profile = self.team_profile(org_id)
        with self.connect() as con:
            meta = self._meta(con)
            row = con.execute("SELECT org_dn FROM organizations_current WHERE snapshot_id=? AND org_id=?", (meta["snapshot_id"], org_id)).fetchone()
            if row is None:
                raise KeyError(org_id)
            chain = con.execute("""WITH RECURSIVE lineage AS (SELECT org_dn,parent_dn,0 ordinal FROM organizations_current WHERE org_dn=? UNION ALL SELECT parent.org_dn,parent.parent_dn,lineage.ordinal+1 FROM organizations_current parent JOIN lineage ON parent.org_dn=lineage.parent_dn) SELECT o.org_id,o.name,p.org_id parent_id,o.depth,o.child_count,o.descendant_people_count,lineage.ordinal FROM lineage JOIN organizations_current o ON o.org_dn=lineage.org_dn LEFT JOIN organizations_current p ON p.org_dn=o.parent_dn ORDER BY lineage.ordinal DESC""", (row["org_dn"],)).fetchall()
        items = tuple(OrgNode(str(r["org_id"]), str(r["name"]), r["parent_id"], int(r["depth"]), int(r["child_count"]), int(r["descendant_people_count"])) for r in chain)
        return OrgPage(items, len(items), profile.snapshot_id, profile.quality_status, _etag(meta, "ancestors", org_id))

    def roles(self, *, org_id: str | None = None, limit: int = 50) -> SearchResult:
        limit = _bounded(limit, MAX_PAGE_SIZE)
        with self.connect() as con:
            meta = self._meta(con)
            sql = "SELECT entity_id,entity_kind,org_id,title,organization_name FROM career_entities WHERE snapshot_id=? AND entity_kind='person'"
            params: list[object] = [meta["snapshot_id"]]
            if org_id is not None:
                sql += " AND org_id=?"; params.append(org_id)
            sql += " ORDER BY title,entity_id LIMIT ?"; params.append(limit)
            rows = con.execute(sql, params).fetchall()
        items = tuple(SearchItem(str(r["entity_id"]), str(r["entity_kind"]), r["org_id"], str(r["title"]), str(r["organization_name"]), 0, "none", ()) for r in rows)
        return SearchResult(items, limit, str(meta["snapshot_id"]), str(meta["quality_status"]), _etag(meta, "roles", org_id or "all", limit))

    def constellation(self, *, query: str, limit: int = 200) -> SearchResult:
        limit = _bounded(limit, MAX_CONSTELLATION_SIZE)
        taxonomy = load_taxonomy(self.taxonomy_path)
        interpretation = taxonomy.interpret(query)
        with self.connect() as con:
            meta = self._meta(con)
            if not interpretation.category_ids:
                return SearchResult((), limit, str(meta["snapshot_id"]), str(meta["quality_status"]), _etag(meta, "constellation", query, limit))
            placeholders = ",".join("?" for _ in interpretation.category_ids)
            rows = con.execute(f"SELECT e.entity_id,e.entity_kind,e.org_id,e.title,e.organization_name,m.score,m.confidence,m.evidence_json FROM career_matches m JOIN career_entities e ON e.entity_id=m.entity_id WHERE m.category_id IN ({placeholders}) ORDER BY m.score DESC,e.entity_id LIMIT ?", (*interpretation.category_ids, limit)).fetchall()
        items = tuple(SearchItem(str(r["entity_id"]), str(r["entity_kind"]), r["org_id"], str(r["title"]), str(r["organization_name"]), int(r["score"]), str(r["confidence"]), tuple(json.loads(r["evidence_json"]))) for r in rows)
        return SearchResult(items, limit, str(meta["snapshot_id"]), str(meta["quality_status"]), _etag(meta, "constellation", query, limit))

    def constellation_slice(self, *, root_id: str | None, max_depth: int = 1, limit: int = 200) -> ConstellationSlice:
        """Return a bounded organization slice for spatial exploration, never the full graph."""
        limit = _bounded(limit, MAX_CONSTELLATION_SIZE)
        max_depth = _bounded(max_depth, 12)
        with self.connect() as con:
            meta = self._meta(con)
            snapshot_id = str(meta["snapshot_id"])
            if root_id is None:
                rows = con.execute(
                    """SELECT o.org_id,o.name,NULL parent_id,o.depth,o.child_count,o.descendant_people_count
                       FROM organizations_current o
                       WHERE o.snapshot_id=? AND o.parent_dn IS NULL
                       ORDER BY o.name,o.org_id LIMIT ?""",
                    (snapshot_id, limit + 1),
                ).fetchall()
            else:
                rows = con.execute(
                    """WITH RECURSIVE slice(org_dn, level) AS (
                           SELECT org_dn, 0 FROM organizations_current WHERE snapshot_id=? AND org_id=?
                           UNION ALL
                           SELECT child.org_dn, slice.level + 1
                           FROM organizations_current child JOIN slice ON child.parent_dn=slice.org_dn
                           WHERE child.snapshot_id=? AND slice.level < ?
                       )
                       SELECT o.org_id,o.name,p.org_id parent_id,o.depth,o.child_count,o.descendant_people_count
                       FROM slice JOIN organizations_current o ON o.org_dn=slice.org_dn
                       LEFT JOIN organizations_current p ON p.org_dn=o.parent_dn
                       ORDER BY o.depth,o.name,o.org_id LIMIT ?""",
                    (snapshot_id, root_id, snapshot_id, max_depth, limit + 1),
                ).fetchall()
        truncated = len(rows) > limit
        rows = rows[:limit]
        nodes = tuple(OrgNode(str(row["org_id"]), str(row["name"]), row["parent_id"], int(row["depth"]), int(row["child_count"]), int(row["descendant_people_count"])) for row in rows)
        return ConstellationSlice(nodes, limit, truncated, snapshot_id, str(meta["quality_status"]), _etag(meta, "constellation-slice", root_id or "root", max_depth, limit))

    def tours(self) -> TourResult:
        document = json.loads(self.tours_path.read_text(encoding="utf-8"))
        with self.connect() as con:
            meta = self._meta(con)
            available_ids = {str(row[0]) for row in con.execute("SELECT org_id FROM organizations_current WHERE snapshot_id=?", (meta["snapshot_id"],)).fetchall()}
        items = []
        for configured in document["tours"]:
            tour = dict(configured)
            tour["stops"] = tuple({**stop, "available": stop["org_id"] in available_ids} for stop in configured["stops"])
            items.append(tour)
        return TourResult(tuple(items), str(meta["snapshot_id"]), str(meta["quality_status"]), _etag(meta, "tours", document["version"]))

    def _meta(self, con: sqlite3.Connection) -> dict[str, object]:
        row = con.execute("""SELECT state.snapshot_id,state.taxonomy_version,s.quality_status,s.as_of_at,s.people_count,s.org_units_count,s.departments_count FROM career_index_state state JOIN canonical_snapshots s ON s.snapshot_id=state.snapshot_id WHERE state.singleton=1""").fetchone()
        if row is None:
            raise ValueError("career index has not been built")
        return dict(row)


def _bounded(value: int, maximum: int) -> int:
    return max(1, min(int(value), maximum))


def _confidence(score: int) -> str:
    return "high" if score >= 100 else "medium" if score >= 60 else "exploratory" if score >= 25 else "none"


def _etag(meta: dict[str, object], *parts: object) -> str:
    value = "|".join([str(meta["snapshot_id"]), *(normalize_text(str(part)) for part in parts)])
    return hashlib.sha256(value.encode()).hexdigest()[:20]
