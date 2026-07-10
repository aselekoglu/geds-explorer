from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .career_taxonomy import CareerTaxonomy, QueryInterpretation, TaxonomyTerm, normalize_text


WEIGHTS = {
    "title_phrase": 100,
    "organization_phrase": 85,
    "title_synonym": 70,
    "organization_synonym": 55,
    "ancestor_phrase": 25,
}

CONFIDENCE_RANK = {"none": 0, "exploratory": 1, "medium": 2, "high": 3}
FIELD_ORDER = {"title": 0, "organization": 1, "ancestor": 2}


@dataclass(frozen=True)
class MatchEntity:
    id: str
    kind: str
    title: str
    organization: str
    ancestors: tuple[str, ...]


@dataclass(frozen=True)
class MatchEvidence:
    field: str
    matched_phrase: str
    source_text: str
    weight: int
    category_id: str


@dataclass(frozen=True)
class CareerMatch:
    entity_id: str
    category_ids: tuple[str, ...]
    score: int
    confidence: str
    evidence: tuple[MatchEvidence, ...]
    exclusions: tuple[str, ...]
    taxonomy_version: str


@dataclass(frozen=True)
class EvaluationCase:
    id: str
    query: str
    entity: MatchEntity
    expected_categories: tuple[str, ...]
    minimum_confidence: str
    forbidden_categories: tuple[str, ...]


@dataclass(frozen=True)
class EvaluationReport:
    taxonomy_version: str
    total_cases: int
    passed_cases: int
    failed_case_ids: tuple[str, ...]
    forbidden_match_case_ids: tuple[str, ...]
    precision_at_10: dict[str, float]


class CareerMatcher:
    def __init__(self, taxonomy: CareerTaxonomy):
        self.taxonomy = taxonomy
        self.categories_by_id = {category.id: category for category in taxonomy.categories}

    def match_entity(
        self,
        entity: MatchEntity,
        interpretation: QueryInterpretation,
    ) -> CareerMatch:
        evidence: list[MatchEvidence] = []
        exclusions: list[str] = []
        matched_category_ids: set[str] = set()
        seen_evidence: set[tuple[str, str, str, str]] = set()
        fields = _entity_fields(entity)

        for category_id in interpretation.category_ids:
            category = self.categories_by_id.get(category_id)
            if category is None:
                continue

            excluded = _matching_exclusions(category.normalized_exclusions, fields)
            if excluded:
                exclusions.extend(
                    f'{category.id}: exclusion "{phrase}" in {field}'
                    for field, phrase in excluded
                )
                continue

            category_evidence = _match_category(category.id, category.terms, fields)
            for item in category_evidence:
                key = (
                    item.category_id,
                    item.field,
                    normalize_text(item.matched_phrase),
                    normalize_text(item.source_text),
                )
                if key in seen_evidence:
                    continue
                seen_evidence.add(key)
                evidence.append(item)
                matched_category_ids.add(category.id)

        score = sum(item.weight for item in evidence)
        if evidence and all(item.field == "ancestor" for item in evidence):
            score = min(score, 60)
        ordered_evidence = tuple(
            sorted(
                evidence,
                key=lambda item: (-item.weight, FIELD_ORDER[item.field]),
            )
        )
        return CareerMatch(
            entity_id=entity.id,
            category_ids=tuple(sorted(matched_category_ids)),
            score=score,
            confidence=confidence_for(score),
            evidence=ordered_evidence,
            exclusions=tuple(sorted(set(exclusions))),
            taxonomy_version=self.taxonomy.version,
        )


def match_entity(
    entity: MatchEntity,
    interpretation: QueryInterpretation,
    taxonomy: CareerTaxonomy,
) -> CareerMatch:
    return CareerMatcher(taxonomy).match_entity(entity, interpretation)


def confidence_for(score: int) -> str:
    if score >= 100:
        return "high"
    if score >= 60:
        return "medium"
    if score >= 25:
        return "exploratory"
    return "none"


def load_evaluation_cases(path: Path | str) -> tuple[EvaluationCase, ...]:
    source_path = Path(path)
    try:
        payload = json.loads(source_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid evaluation fixture {source_path}: {exc}") from exc
    if not isinstance(payload, list):
        raise ValueError("evaluation fixture must be a list")

    cases: list[EvaluationCase] = []
    seen_ids: set[str] = set()
    for index, raw_case in enumerate(payload):
        if not isinstance(raw_case, dict):
            raise ValueError(f"evaluation case {index} must be an object")
        case_id = _required_string(raw_case, "id", index)
        if case_id in seen_ids:
            raise ValueError(f"duplicate evaluation case id: {case_id}")
        seen_ids.add(case_id)
        minimum_confidence = _required_string(raw_case, "minimum_confidence", index)
        if minimum_confidence not in CONFIDENCE_RANK:
            raise ValueError(f"unknown minimum confidence: {minimum_confidence}")
        entity_raw = raw_case.get("entity")
        if not isinstance(entity_raw, dict):
            raise ValueError(f"evaluation case {case_id!r} requires an entity object")
        ancestors = entity_raw.get("ancestors")
        if not isinstance(ancestors, list) or any(not isinstance(value, str) for value in ancestors):
            raise ValueError(f"evaluation case {case_id!r} has invalid ancestors")
        entity = MatchEntity(
            id=_required_string(entity_raw, "id", index),
            kind=_required_string(entity_raw, "kind", index),
            title=_optional_string(entity_raw, "title"),
            organization=_optional_string(entity_raw, "organization"),
            ancestors=tuple(ancestors),
        )
        cases.append(
            EvaluationCase(
                id=case_id,
                query=_required_string(raw_case, "query", index),
                entity=entity,
                expected_categories=_string_tuple(raw_case, "expected_categories", case_id),
                minimum_confidence=minimum_confidence,
                forbidden_categories=_string_tuple(raw_case, "forbidden_categories", case_id),
            )
        )
    return tuple(cases)


def evaluate_matcher(
    cases: Iterable[EvaluationCase],
    taxonomy: CareerTaxonomy,
) -> EvaluationReport:
    matcher = CareerMatcher(taxonomy)
    case_list = tuple(cases)
    matches: list[tuple[EvaluationCase, CareerMatch]] = []
    failed: list[str] = []
    forbidden: list[str] = []

    for case in case_list:
        result = matcher.match_entity(case.entity, taxonomy.interpret(case.query))
        matches.append((case, result))
        expected_ok = set(case.expected_categories).issubset(result.category_ids)
        confidence_ok = CONFIDENCE_RANK[result.confidence] >= CONFIDENCE_RANK[case.minimum_confidence]
        forbidden_hit = bool(set(case.forbidden_categories) & set(result.category_ids))
        if forbidden_hit:
            forbidden.append(case.id)
        if not expected_ok or not confidence_ok or forbidden_hit:
            failed.append(case.id)

    precision: dict[str, float] = {}
    for category in taxonomy.categories:
        positives = [case for case in case_list if category.id in case.expected_categories]
        if len(positives) < 10:
            continue
        ranked = sorted(
            matches,
            key=lambda item: item[1].score if category.id in item[1].category_ids else 0,
            reverse=True,
        )[:10]
        precision[category.id] = sum(
            category.id in case.expected_categories for case, _ in ranked
        ) / 10

    return EvaluationReport(
        taxonomy_version=taxonomy.version,
        total_cases=len(case_list),
        passed_cases=len(case_list) - len(failed),
        failed_case_ids=tuple(failed),
        forbidden_match_case_ids=tuple(forbidden),
        precision_at_10=precision,
    )


def _entity_fields(entity: MatchEntity) -> tuple[tuple[str, str], ...]:
    return (
        ("title", entity.title),
        ("organization", entity.organization),
        *(("ancestor", ancestor) for ancestor in entity.ancestors),
    )


def _matching_exclusions(
    exclusions: tuple[str, ...],
    fields: tuple[tuple[str, str], ...],
) -> tuple[tuple[str, str], ...]:
    matches: list[tuple[str, str]] = []
    for field, source_text in fields:
        normalized_source = normalize_text(source_text)
        for phrase in exclusions:
            if _contains_phrase(normalized_source, phrase):
                matches.append((field, phrase))
    return tuple(matches)


def _match_category(
    category_id: str,
    terms: tuple[TaxonomyTerm, ...],
    fields: tuple[tuple[str, str], ...],
) -> tuple[MatchEvidence, ...]:
    matches: list[MatchEvidence] = []
    for field, source_text in fields:
        normalized_source = normalize_text(source_text)
        if not normalized_source:
            continue
        for term in terms:
            if _contains_phrase(normalized_source, term.normalized):
                matches.append(
                    MatchEvidence(
                        field=field,
                        matched_phrase=term.value,
                        source_text=source_text,
                        weight=_weight_for(field, term),
                        category_id=category_id,
                    )
                )
    return tuple(matches)


def _weight_for(field: str, term: TaxonomyTerm) -> int:
    if field == "ancestor":
        return WEIGHTS["ancestor_phrase"]
    is_phrase = term.kind.startswith("phrase") or term.kind == "abbreviation"
    if field == "title":
        return WEIGHTS["title_phrase" if is_phrase else "title_synonym"]
    return WEIGHTS["organization_phrase" if is_phrase else "organization_synonym"]


def _contains_phrase(haystack: str, needle: str) -> bool:
    return f" {needle} " in f" {haystack} "


def _required_string(raw: dict[str, Any], key: str, index: int) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"evaluation case {index} field {key!r} must be a non-empty string")
    return value.strip()


def _optional_string(raw: dict[str, Any], key: str) -> str:
    value = raw.get(key, "")
    if not isinstance(value, str):
        raise ValueError(f"entity field {key!r} must be a string")
    return value


def _string_tuple(raw: dict[str, Any], key: str, case_id: str) -> tuple[str, ...]:
    values = raw.get(key)
    if not isinstance(values, list) or any(not isinstance(value, str) for value in values):
        raise ValueError(f"evaluation case {case_id!r} field {key!r} must be a string list")
    return tuple(values)
