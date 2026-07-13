from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from .career_leads import LeadSuggestion, infer_leads, load_lead_rules
from .career_people import PeoplePage, PublicPerson, extract_observed_classifications, official_geds_url, public_person_id
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
    vacancy_signal: bool = False
    department_name: str = ""
    display_name: str = ""
    source_url: str = ""


@dataclass(frozen=True)
class SearchResult:
    items: tuple[SearchItem, ...]
    limit: int
    snapshot_id: str
    quality_status: str
    etag: str
    interpretation: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class OrgNode:
    org_id: str
    name: str
    parent_id: str | None
    depth: int
    child_count: int
    direct_people_count: int
    descendant_people_count: int
    descendant_org_count: int = 0
    match_count: int = 0
    quality_status: str = "unknown"
    vacancy_count: int = 0
    has_more: bool = False


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
    source_url: str
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
class VacancyDiscovery:
    marker: str
    title: str
    org_id: str
    organization_name: str
    observed_at: str
    source_url: str
    confidence: str
    reasons: tuple[str, ...]
    live_competition_verified: bool = False


@dataclass(frozen=True)
class VacancyDiscoveryResult:
    items: tuple[VacancyDiscovery, ...]
    limit: int
    snapshot_id: str
    quality_status: str
    etag: str


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
            rows = []
            if interpretation.category_ids:
                placeholders = ",".join("?" for _ in interpretation.category_ids)
                candidate_limit = max(50, limit * 4)
                rows = con.execute(
                    f"""
                    WITH ranked AS (
                      SELECT entity_id,SUM(score) total_score
                      FROM career_matches
                      WHERE category_id IN ({placeholders})
                      GROUP BY entity_id
                      ORDER BY total_score DESC,entity_id ASC
                      LIMIT ?
                    )
                    SELECT e.entity_id, e.entity_kind, e.org_id, e.title, e.organization_name,e.ancestor_text,COALESCE(d.name,'') department_name,
                           COALESCE(p.display_name,'') display_name,COALESCE(p.source_url,'') source_url,
                           m.category_id, m.score, m.confidence, m.evidence_json,
                           CASE WHEN v.entity_id IS NULL THEN 0 ELSE 1 END vacancy_signal
                    FROM ranked AS ranked
                    JOIN career_matches AS m ON m.entity_id=ranked.entity_id
                    JOIN career_entities AS e ON e.entity_id = m.entity_id
                    LEFT JOIN organizations_current o ON o.org_id=e.org_id AND o.snapshot_id=e.snapshot_id
                    LEFT JOIN departments_current d ON d.department_dn=o.department_dn AND d.snapshot_id=e.snapshot_id
                    LEFT JOIN people_current p ON e.entity_kind='person' AND p.source_url=substr(e.entity_id,8) AND p.snapshot_id=e.snapshot_id
                    LEFT JOIN vacancy_signals AS v ON v.entity_id=e.entity_id AND v.snapshot_id=e.snapshot_id
                    WHERE m.category_id IN ({placeholders})
                    ORDER BY ranked.total_score DESC,e.entity_id ASC,m.category_id ASC
                    """,
                    (*interpretation.category_ids, candidate_limit, *interpretation.category_ids),
                ).fetchall()
            direct_orgs = con.execute(
                """SELECT o.org_id,o.name,COALESCE(d.name,'') department_name,o.canonical_path_json
                   FROM organizations_current o LEFT JOIN departments_current d ON d.department_dn=o.department_dn AND d.snapshot_id=o.snapshot_id
                   WHERE o.snapshot_id=? AND (instr(lower(o.name),lower(?))>0 OR instr(lower(o.canonical_path_json),lower(?))>0)
                   ORDER BY CASE WHEN lower(o.name)=lower(?) THEN 0 ELSE 1 END,o.name COLLATE NOCASE LIMIT ?""",
                (meta["snapshot_id"], query, query, query, limit),
            ).fetchall()
            fts_query = f'"{query.replace(chr(34), chr(34) * 2)}"'
            direct_people = con.execute(
                """SELECT p.source_url,p.display_name,COALESCE(p.title,'') title,o.org_id,COALESCE(o.name,p.org_unit) organization_name,COALESCE(d.name,p.department_name) department_name
                   FROM career_entities_fts
                   JOIN career_entities e ON e.entity_id=career_entities_fts.entity_id
                   JOIN people_current p ON e.entity_kind='person' AND p.source_url=substr(e.entity_id,8) AND p.snapshot_id=e.snapshot_id
                   LEFT JOIN organizations_current o ON o.org_dn=p.org_dn AND o.snapshot_id=p.snapshot_id
                   LEFT JOIN departments_current d ON d.department_dn=p.department_dn AND d.snapshot_id=p.snapshot_id
                   WHERE career_entities_fts MATCH ? AND e.snapshot_id=? AND p.presence_status='present'
                   ORDER BY bm25(career_entities_fts),CASE WHEN lower(p.display_name)=lower(?) THEN 0 ELSE 1 END,p.display_name COLLATE NOCASE LIMIT ?""",
                (fts_query, meta["snapshot_id"], query, limit),
            ).fetchall()
            direct_people += con.execute(
                """SELECT p.source_url,p.display_name,COALESCE(p.title,'') title,o.org_id,COALESCE(o.name,p.org_unit) organization_name,COALESCE(d.name,p.department_name) department_name
                   FROM people_current p
                   LEFT JOIN organizations_current o ON o.org_dn=p.org_dn AND o.snapshot_id=p.snapshot_id
                   LEFT JOIN departments_current d ON d.department_dn=p.department_dn AND d.snapshot_id=p.snapshot_id
                   WHERE p.snapshot_id=? AND p.presence_status='present' AND p.display_name LIKE ('%' || ? || '%') COLLATE NOCASE
                   LIMIT ?""",
                (meta["snapshot_id"], query, limit),
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
                vacancy_signal=bool(value["row"]["vacancy_signal"]),
                department_name=str(value["row"]["department_name"]),
                display_name=str(value["row"]["display_name"]),
                source_url=official_geds_url(str(value["row"]["source_url"])),
            )
            for key, value in grouped.items()
        )
        merged = {item.entity_id: item for item in items}
        for row in direct_orgs:
            entity_id = f"org:{row['org_id']}"
            direct = SearchItem(
                entity_id, "organization", str(row["org_id"]), "", str(row["name"]),
                1000 if str(row["name"]).casefold() == query.casefold() else 500,
                "high", ({"field": "organization", "matched_phrase": query, "source_text": str(row["name"]), "weight": 500, "category_id": "direct-search"},),
                False, str(row["department_name"]),
            )
            existing = merged.get(entity_id)
            if existing:
                direct = SearchItem(direct.entity_id,direct.entity_kind,direct.org_id,direct.title,direct.organization_name,max(direct.score,existing.score),direct.confidence,existing.evidence+direct.evidence,existing.vacancy_signal,direct.department_name)
            merged[entity_id] = direct
        for row in direct_people:
            entity_id = f"person:{row['source_url']}"
            source_text = str(row["display_name"])
            field = "display_name" if query.casefold() in source_text.casefold() else "title"
            direct = SearchItem(
                entity_id, "person", row["org_id"], str(row["title"]), str(row["organization_name"]),
                1000 if source_text.casefold() == query.casefold() else 450,
                "high", ({"field": field, "matched_phrase": query, "source_text": source_text if field == "display_name" else str(row["title"]), "weight": 450, "category_id": "direct-search"},),
                False, str(row["department_name"]), str(row["display_name"]), official_geds_url(str(row["source_url"])),
            )
            existing = merged.get(entity_id)
            if existing:
                direct = SearchItem(direct.entity_id,direct.entity_kind,direct.org_id,direct.title,direct.organization_name,max(direct.score,existing.score),direct.confidence,existing.evidence+direct.evidence,existing.vacancy_signal,direct.department_name,direct.display_name,direct.source_url)
            merged[entity_id] = direct
        ranked = tuple(sorted(merged.values(), key=lambda item: (-item.score, item.entity_id))[:limit])
        return SearchResult(ranked, limit, str(meta["snapshot_id"]), str(meta["quality_status"]), _etag(meta, query, limit), _interpretation_payload(interpretation))

    def children(self, *, parent_id: str | None, limit: int = 50) -> OrgPage:
        limit = _bounded(limit, MAX_PAGE_SIZE)
        with self.connect() as con:
            meta = self._meta(con)
            if parent_id is None:
                rows = con.execute("""SELECT o.org_id,o.name,NULL parent_id,o.depth,o.child_count,o.direct_people_count,o.descendant_people_count FROM organizations_current o WHERE o.snapshot_id=? AND o.parent_dn IS NULL ORDER BY o.name,o.org_id LIMIT ?""", (meta["snapshot_id"], limit)).fetchall()
            else:
                rows = con.execute("""SELECT child.org_id,child.name,parent.org_id parent_id,child.depth,child.child_count,child.direct_people_count,child.descendant_people_count FROM organizations_current child JOIN organizations_current parent ON parent.org_dn=child.parent_dn WHERE child.snapshot_id=? AND parent.org_id=? ORDER BY child.name,child.org_id LIMIT ?""", (meta["snapshot_id"], parent_id, limit)).fetchall()
        items = tuple(OrgNode(org_id=str(r["org_id"]), name=str(r["name"]), parent_id=r["parent_id"], depth=int(r["depth"]), child_count=int(r["child_count"]), direct_people_count=int(r["direct_people_count"]), descendant_people_count=int(r["descendant_people_count"])) for r in rows)
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
        return TeamProfile(org_id, str(row["name"]), str(row["department_name"]), tuple(json.loads(row["canonical_path_json"])), int(row["direct_people_count"]), int(row["descendant_people_count"]), int(row["child_count"]), str(meta["snapshot_id"]), str(meta["as_of_at"]), str(meta["quality_status"]), str(row["source_url"]), leads, vacancy_signals)

    def people(
        self,
        *,
        org_id: str,
        query: str = "",
        classification: str | None = None,
        sort: str = "name",
        limit: int = 50,
        offset: int = 0,
    ) -> PeoplePage:
        limit = _bounded(limit, MAX_PAGE_SIZE)
        offset = max(0, int(offset))
        query_folded = normalize_text(query)
        with self.connect() as con:
            meta = self._meta(con)
            organization = con.execute(
                "SELECT org_dn,org_id,name FROM organizations_current WHERE snapshot_id=? AND org_id=?",
                (meta["snapshot_id"], org_id),
            ).fetchone()
            if organization is None:
                raise KeyError(org_id)
            rows = con.execute(
                """SELECT display_name,title,source_url
                   FROM people_current
                   WHERE snapshot_id=? AND org_dn=? AND presence_status='present'
                   ORDER BY display_name COLLATE NOCASE,source_url""",
                (meta["snapshot_id"], organization["org_dn"]),
            ).fetchall()

        all_people = [
            PublicPerson(
                person_id=public_person_id(str(row["source_url"])),
                display_name=str(row["display_name"]),
                observed_title=str(row["title"] or ""),
                observed_classifications=extract_observed_classifications(row["title"]),
                org_id=str(organization["org_id"]),
                organization_name=str(organization["name"]),
                snapshot_id=str(meta["snapshot_id"]),
                snapshot_as_of=str(meta["as_of_at"]),
                source_url=official_geds_url(str(row["source_url"])),
            )
            for row in rows
        ]
        available = tuple(sorted({value for person in all_people for value in person.observed_classifications}))
        filtered = [
            person
            for person in all_people
            if (not query_folded or query_folded in normalize_text(f"{person.display_name} {person.observed_title}"))
            and (classification is None or classification in person.observed_classifications)
        ]
        if sort == "title":
            filtered.sort(key=lambda person: (person.observed_title.casefold(), person.display_name.casefold(), person.person_id))
        else:
            filtered.sort(key=lambda person: (person.display_name.casefold(), person.observed_title.casefold(), person.person_id))
        total = len(filtered)
        page = tuple(filtered[offset : offset + limit])
        return PeoplePage(
            page,
            total,
            limit,
            offset,
            available,
            str(meta["snapshot_id"]),
            str(meta["quality_status"]),
            _etag(meta, "people", org_id, query, classification or "all", sort, limit, offset),
        )

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
            chain = con.execute("""WITH RECURSIVE lineage AS (SELECT org_dn,parent_dn,0 ordinal FROM organizations_current WHERE org_dn=? UNION ALL SELECT parent.org_dn,parent.parent_dn,lineage.ordinal+1 FROM organizations_current parent JOIN lineage ON parent.org_dn=lineage.parent_dn) SELECT o.org_id,o.name,p.org_id parent_id,o.depth,o.child_count,o.direct_people_count,o.descendant_people_count,lineage.ordinal FROM lineage JOIN organizations_current o ON o.org_dn=lineage.org_dn LEFT JOIN organizations_current p ON p.org_dn=o.parent_dn ORDER BY lineage.ordinal DESC""", (row["org_dn"],)).fetchall()
        items = tuple(OrgNode(org_id=str(r["org_id"]), name=str(r["name"]), parent_id=r["parent_id"], depth=int(r["depth"]), child_count=int(r["child_count"]), direct_people_count=int(r["direct_people_count"]), descendant_people_count=int(r["descendant_people_count"])) for r in chain)
        return OrgPage(items, len(items), profile.snapshot_id, profile.quality_status, _etag(meta, "ancestors", org_id))

    def roles(self, *, org_id: str | None = None, limit: int = 50) -> SearchResult:
        limit = _bounded(limit, MAX_PAGE_SIZE)
        with self.connect() as con:
            meta = self._meta(con)
            sql = "SELECT e.entity_id,e.entity_kind,e.org_id,e.title,e.organization_name,e.ancestor_text,COALESCE(d.name,'') department_name,CASE WHEN v.entity_id IS NULL THEN 0 ELSE 1 END vacancy_signal FROM career_entities e LEFT JOIN vacancy_signals v ON v.entity_id=e.entity_id AND v.snapshot_id=e.snapshot_id LEFT JOIN organizations_current o ON o.org_id=e.org_id AND o.snapshot_id=e.snapshot_id LEFT JOIN departments_current d ON d.department_dn=o.department_dn AND d.snapshot_id=e.snapshot_id WHERE e.snapshot_id=? AND e.entity_kind='person'"
            params: list[object] = [meta["snapshot_id"]]
            if org_id is not None:
                sql += " AND e.org_id=?"; params.append(org_id)
            sql += " ORDER BY e.title,e.entity_id LIMIT ?"; params.append(limit)
            rows = con.execute(sql, params).fetchall()
            match_map: dict[str, dict[str, object]] = {}
            if rows:
                entity_ids = [str(row["entity_id"]) for row in rows]
                placeholders = ",".join("?" for _ in entity_ids)
                for match in con.execute(
                    f"SELECT entity_id,score,evidence_json FROM career_matches WHERE entity_id IN ({placeholders}) ORDER BY entity_id,category_id",
                    entity_ids,
                ).fetchall():
                    grouped = match_map.setdefault(str(match["entity_id"]), {"score": 0, "evidence": []})
                    grouped["score"] = int(grouped["score"]) + int(match["score"])
                    grouped["evidence"].extend(json.loads(match["evidence_json"]))
        items = tuple(
            SearchItem(
                str(r["entity_id"]), str(r["entity_kind"]), r["org_id"], str(r["title"]), str(r["organization_name"]),
                int(match_map.get(str(r["entity_id"]), {}).get("score", 0)),
                _confidence(int(match_map.get(str(r["entity_id"]), {}).get("score", 0))),
                tuple(match_map.get(str(r["entity_id"]), {}).get("evidence", [])), bool(r["vacancy_signal"]), str(r["department_name"]),
            )
            for r in rows
        )
        return SearchResult(items, limit, str(meta["snapshot_id"]), str(meta["quality_status"]), _etag(meta, "roles", org_id or "all", limit))

    def vacancy_signals(self, *, limit: int = 50) -> VacancyDiscoveryResult:
        limit = _bounded(limit, MAX_PAGE_SIZE)
        with self.connect() as con:
            meta = self._meta(con)
            rows = con.execute(
                """SELECT v.source_text,v.title,v.org_id,o.name organization_name,
                          p.last_seen_at,p.source_url,v.confidence,v.reasons_json
                   FROM vacancy_signals v
                   JOIN organizations_current o ON o.org_id=v.org_id AND o.snapshot_id=v.snapshot_id
                   JOIN people_current p ON v.entity_id='person:' || p.source_url AND p.snapshot_id=v.snapshot_id
                   WHERE v.snapshot_id=?
                   ORDER BY o.name,v.title,v.entity_id LIMIT ?""",
                (meta["snapshot_id"], limit),
            ).fetchall()
        items = tuple(
            VacancyDiscovery(
                marker=str(row["source_text"]),
                title=str(row["title"]),
                org_id=str(row["org_id"]),
                organization_name=str(row["organization_name"]),
                observed_at=str(row["last_seen_at"]),
                source_url=str(row["source_url"]),
                confidence=str(row["confidence"]),
                reasons=tuple(json.loads(row["reasons_json"])),
            )
            for row in rows
        )
        return VacancyDiscoveryResult(items, limit, str(meta["snapshot_id"]), str(meta["quality_status"]), _etag(meta, "vacancy-signals", limit))

    def constellation(self, *, query: str, limit: int = 200) -> SearchResult:
        limit = _bounded(limit, MAX_CONSTELLATION_SIZE)
        taxonomy = load_taxonomy(self.taxonomy_path)
        interpretation = taxonomy.interpret(query)
        with self.connect() as con:
            meta = self._meta(con)
            if not interpretation.category_ids:
                return SearchResult((), limit, str(meta["snapshot_id"]), str(meta["quality_status"]), _etag(meta, "constellation", query, limit), _interpretation_payload(interpretation))
            placeholders = ",".join("?" for _ in interpretation.category_ids)
            rows = con.execute(f"SELECT e.entity_id,e.entity_kind,e.org_id,e.title,e.organization_name,e.ancestor_text,COALESCE(d.name,'') department_name,m.score,m.confidence,m.evidence_json,CASE WHEN v.entity_id IS NULL THEN 0 ELSE 1 END vacancy_signal FROM career_matches m JOIN career_entities e ON e.entity_id=m.entity_id LEFT JOIN vacancy_signals v ON v.entity_id=e.entity_id AND v.snapshot_id=e.snapshot_id LEFT JOIN organizations_current o ON o.org_id=e.org_id AND o.snapshot_id=e.snapshot_id LEFT JOIN departments_current d ON d.department_dn=o.department_dn AND d.snapshot_id=e.snapshot_id WHERE m.category_id IN ({placeholders}) ORDER BY m.score DESC,e.entity_id LIMIT ?", (*interpretation.category_ids, limit)).fetchall()
        items = tuple(SearchItem(str(r["entity_id"]), str(r["entity_kind"]), r["org_id"], str(r["title"]), str(r["organization_name"]), int(r["score"]), str(r["confidence"]), tuple(json.loads(r["evidence_json"])), bool(r["vacancy_signal"]), str(r["department_name"])) for r in rows)
        return SearchResult(items, limit, str(meta["snapshot_id"]), str(meta["quality_status"]), _etag(meta, "constellation", query, limit), _interpretation_payload(interpretation))

    def constellation_slice(self, *, root_id: str | None, max_depth: int = 1, limit: int = 200, category: str | None = None) -> ConstellationSlice:
        """Return a bounded organization slice for spatial exploration, never the full graph."""
        limit = _bounded(limit, MAX_CONSTELLATION_SIZE)
        max_depth = _bounded(max_depth, 12)
        with self.connect() as con:
            meta = self._meta(con)
            snapshot_id = str(meta["snapshot_id"])
            if root_id is None:
                rows = con.execute(
                    """SELECT o.org_id,o.name,NULL parent_id,o.depth,o.child_count,o.direct_people_count,o.descendant_people_count,o.descendant_org_count
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
                       SELECT o.org_id,o.name,p.org_id parent_id,o.depth,o.child_count,o.direct_people_count,o.descendant_people_count,o.descendant_org_count
                       FROM slice JOIN organizations_current o ON o.org_dn=slice.org_dn
                       LEFT JOIN organizations_current p ON p.org_dn=o.parent_dn
                       ORDER BY o.depth,o.name,o.org_id LIMIT ?""",
                    (snapshot_id, root_id, snapshot_id, max_depth, limit + 1),
                ).fetchall()
            visible_org_ids = [str(row["org_id"]) for row in rows[:limit]]
            match_counts: dict[str, int] = {}
            vacancy_counts: dict[str, int] = {}
            if visible_org_ids:
                placeholders = ",".join("?" for _ in visible_org_ids)
                if category:
                    match_counts = {
                        str(row["org_id"]): int(row["match_count"])
                        for row in con.execute(
                            f"""SELECT e.org_id,COUNT(*) match_count FROM career_matches m
                                JOIN career_entities e ON e.entity_id=m.entity_id
                                WHERE m.category_id=? AND e.snapshot_id=? AND e.org_id IN ({placeholders})
                                GROUP BY e.org_id""",
                            (category, snapshot_id, *visible_org_ids),
                        ).fetchall()
                    }
                vacancy_counts = {
                    str(row["org_id"]): int(row["vacancy_count"])
                    for row in con.execute(
                        f"SELECT org_id,COUNT(*) vacancy_count FROM vacancy_signals WHERE snapshot_id=? AND org_id IN ({placeholders}) GROUP BY org_id",
                        (snapshot_id, *visible_org_ids),
                    ).fetchall()
                }
        truncated = len(rows) > limit
        rows = rows[:limit]
        visible_children: dict[str, int] = {}
        for row in rows:
            if row["parent_id"] is not None:
                visible_children[str(row["parent_id"])] = visible_children.get(str(row["parent_id"]), 0) + 1
        nodes = tuple(
            OrgNode(
                org_id=str(row["org_id"]), name=str(row["name"]), parent_id=row["parent_id"], depth=int(row["depth"]),
                child_count=int(row["child_count"]), direct_people_count=int(row["direct_people_count"]),
                descendant_people_count=int(row["descendant_people_count"]), descendant_org_count=int(row["descendant_org_count"]),
                match_count=match_counts.get(str(row["org_id"]), 0), quality_status=str(meta["quality_status"]),
                vacancy_count=vacancy_counts.get(str(row["org_id"]), 0),
                has_more=int(row["child_count"]) > visible_children.get(str(row["org_id"]), 0),
            )
            for row in rows
        )
        return ConstellationSlice(nodes, limit, truncated, snapshot_id, str(meta["quality_status"]), _etag(meta, "constellation-slice", root_id or "root", max_depth, limit, category or "all"))

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


def _interpretation_payload(interpretation) -> dict[str, object]:
    return {
        "original_query": interpretation.original_query,
        "normalized_query": interpretation.normalized_query,
        "category_ids": list(interpretation.category_ids),
        "expanded_terms": list(interpretation.expanded_terms),
        "evidence": list(interpretation.evidence),
        "taxonomy_version": interpretation.taxonomy_version,
    }


def _etag(meta: dict[str, object], *parts: object) -> str:
    value = "|".join([str(meta["snapshot_id"]), *(normalize_text(str(part)) for part in parts)])
    return hashlib.sha256(value.encode()).hexdigest()[:20]
