from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence


@dataclass(frozen=True)
class LeadRules:
    version: str
    possible_team_lead: tuple[str, ...]
    career_conversation_lead: tuple[str, ...]
    exclude: tuple[str, ...]


@dataclass(frozen=True)
class LeadSuggestion:
    kind: str
    confidence: str
    title: str
    org_id: str
    source_url: str
    reasons: tuple[str, ...]


def load_lead_rules(path: Path | str) -> LeadRules:
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    return LeadRules(
        version=str(document["version"]),
        possible_team_lead=tuple(_normalize(value) for value in document["possible_team_lead"]),
        career_conversation_lead=tuple(_normalize(value) for value in document["career_conversation_lead"]),
        exclude=tuple(_normalize(value) for value in document["exclude"]),
    )


def infer_lead(
    title: str,
    person_org_id: str,
    target_org_id: str,
    source_url: str,
    rules: LeadRules,
    *,
    parent_org_ids: Sequence[str] = (),
) -> LeadSuggestion | None:
    normalized = _normalize(title)
    if not normalized or any(term in normalized for term in rules.exclude):
        return None

    kind = _matching_kind(normalized, rules)
    if kind is None:
        return None

    if person_org_id == target_org_id:
        confidence = "high"
        reasons = ("Observed leadership title", "Same organization as this team")
    elif person_org_id in parent_org_ids:
        confidence = "medium"
        reasons = ("Observed leadership title", "Located in a parent organization")
    else:
        return None

    return LeadSuggestion(kind, confidence, title, person_org_id, source_url, reasons)


def infer_leads(
    org_id: str,
    people: Iterable[Mapping[str, object]],
    rules: LeadRules,
    *,
    parent_org_ids: Sequence[str] = (),
) -> tuple[LeadSuggestion, ...]:
    suggestions = (
        infer_lead(
            str(person.get("title") or ""),
            str(person.get("org_id") or ""),
            org_id,
            str(person.get("source_url") or ""),
            rules,
            parent_org_ids=parent_org_ids,
        )
        for person in people
    )
    ranked = sorted(
        (lead for lead in suggestions if lead is not None),
        key=lambda lead: (0 if lead.confidence == "high" else 1, lead.title.casefold(), lead.source_url),
    )
    return tuple(ranked[:3])


def _matching_kind(normalized_title: str, rules: LeadRules) -> str | None:
    if any(term in normalized_title for term in rules.possible_team_lead):
        return "possible_team_lead"
    if any(term in normalized_title for term in rules.career_conversation_lead):
        return "career_conversation_lead"
    return None


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    return " ".join("".join(char for char in decomposed if not unicodedata.combining(char)).split())
