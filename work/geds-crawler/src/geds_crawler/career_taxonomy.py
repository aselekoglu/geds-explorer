from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any


TOKEN_RE = re.compile(r"[a-z0-9]+")


def normalize_text(value: str) -> str:
    """Return a comparison-only form without changing the source value."""

    decomposed = unicodedata.normalize("NFKD", value.casefold())
    plain = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return " ".join(TOKEN_RE.findall(plain))


def tokenize(value: str) -> tuple[str, ...]:
    normalized = normalize_text(value)
    return tuple(normalized.split()) if normalized else ()


@dataclass(frozen=True)
class TaxonomyTerm:
    value: str
    normalized: str
    kind: str


@dataclass(frozen=True)
class CareerCategory:
    id: str
    label_en: str
    label_fr: str
    phrases_en: tuple[str, ...]
    phrases_fr: tuple[str, ...]
    abbreviations: tuple[str, ...]
    synonyms_en: tuple[str, ...]
    synonyms_fr: tuple[str, ...]
    exclusions: tuple[str, ...]
    positive_examples: tuple[str, ...]
    negative_examples: tuple[str, ...]
    terms: tuple[TaxonomyTerm, ...]
    normalized_exclusions: tuple[str, ...]

    @property
    def positive_terms(self) -> tuple[str, ...]:
        return tuple(term.value for term in self.terms)


@dataclass(frozen=True)
class QueryInterpretation:
    original_query: str
    normalized_query: str
    category_ids: tuple[str, ...]
    expanded_terms: tuple[str, ...]
    evidence: tuple[str, ...]
    taxonomy_version: str


@dataclass(frozen=True)
class CareerTaxonomy:
    version: str
    categories: tuple[CareerCategory, ...]

    def interpret(self, query: str) -> QueryInterpretation:
        normalized_query = normalize_text(query)
        matched_categories: set[str] = set()
        expanded_terms: set[str] = set()
        evidence: set[str] = set()

        if normalized_query:
            for category in self.categories:
                matched_terms = tuple(
                    term
                    for term in category.terms
                    if _contains_phrase(normalized_query, term.normalized)
                )
                if not matched_terms:
                    continue

                matched_categories.add(category.id)
                expanded_terms.update(term.normalized for term in category.terms)
                evidence.update(
                    f'{category.id}: {term.kind} "{term.value}"'
                    for term in matched_terms
                )

        return QueryInterpretation(
            original_query=query,
            normalized_query=normalized_query,
            category_ids=tuple(sorted(matched_categories)),
            expanded_terms=tuple(sorted(expanded_terms)),
            evidence=tuple(sorted(evidence)),
            taxonomy_version=self.version,
        )


def load_taxonomy(path: Path | str) -> CareerTaxonomy:
    source_path = Path(path)
    try:
        payload = json.loads(source_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid taxonomy file {source_path}: {exc}") from exc

    if not isinstance(payload, dict):
        raise ValueError("taxonomy root must be an object")
    version = payload.get("version")
    raw_categories = payload.get("categories")
    if not isinstance(version, str) or not version.strip():
        raise ValueError("taxonomy version must be a non-empty string")
    if not isinstance(raw_categories, list) or not raw_categories:
        raise ValueError("taxonomy categories must be a non-empty list")

    categories: list[CareerCategory] = []
    seen_ids: set[str] = set()
    positive_owners: dict[str, str] = {}
    exclusions: list[tuple[str, str]] = []

    for index, raw_category in enumerate(raw_categories):
        category = _load_category(raw_category, index)
        if category.id in seen_ids:
            raise ValueError(f"duplicate category id: {category.id}")
        seen_ids.add(category.id)

        for term in category.terms:
            owner = positive_owners.get(term.normalized)
            if owner is not None:
                raise ValueError(
                    "positive phrase collision: "
                    f'{term.normalized!r} belongs to both {owner!r} and {category.id!r}'
                )
            positive_owners[term.normalized] = category.id
        exclusions.extend((value, category.id) for value in category.normalized_exclusions)
        categories.append(category)

    for exclusion, category_id in exclusions:
        if exclusion in positive_owners:
            raise ValueError(
                "positive/exclusion collision: "
                f'{exclusion!r} is positive for {positive_owners[exclusion]!r} '
                f"and excluded by {category_id!r}"
            )

    return CareerTaxonomy(version=version.strip(), categories=tuple(categories))


def _load_category(raw: Any, index: int) -> CareerCategory:
    if not isinstance(raw, dict):
        raise ValueError(f"category {index} must be an object")

    category_id = _required_string(raw, "id", index)
    label_en = _required_string(raw, "label_en", index)
    label_fr = _required_string(raw, "label_fr", index)
    if not label_en or not label_fr:
        raise ValueError(f"category {category_id!r} requires bilingual labels")

    phrases_en = _string_tuple(raw, "phrases_en", category_id)
    phrases_fr = _string_tuple(raw, "phrases_fr", category_id)
    abbreviations = _string_tuple(raw, "abbreviations", category_id)
    synonyms_en = _string_tuple(raw, "synonyms_en", category_id)
    synonyms_fr = _string_tuple(raw, "synonyms_fr", category_id)
    exclusions = _string_tuple(raw, "exclusions", category_id)
    positive_examples = _string_tuple(raw, "positive_examples", category_id)
    negative_examples = _string_tuple(raw, "negative_examples", category_id)

    if not phrases_en or not phrases_fr:
        raise ValueError(f"category {category_id!r} requires bilingual phrase sets")
    if not synonyms_en or not synonyms_fr:
        raise ValueError(f"category {category_id!r} requires bilingual synonym sets")
    if not positive_examples or not negative_examples:
        raise ValueError(f"category {category_id!r} requires positive and negative examples")

    fields = (
        ("phrase_en", phrases_en),
        ("phrase_fr", phrases_fr),
        ("abbreviation", abbreviations),
        ("synonym_en", synonyms_en),
        ("synonym_fr", synonyms_fr),
    )
    terms: list[TaxonomyTerm] = []
    normalized_terms: set[str] = set()
    for kind, values in fields:
        for value in values:
            normalized = normalize_text(value)
            if not normalized:
                raise ValueError(f"category {category_id!r} has an empty normalized phrase")
            if normalized in normalized_terms:
                raise ValueError(
                    f"positive phrase collision: duplicate {normalized!r} in {category_id!r}"
                )
            normalized_terms.add(normalized)
            terms.append(TaxonomyTerm(value=value, normalized=normalized, kind=kind))

    normalized_exclusions = tuple(normalize_text(value) for value in exclusions)
    if any(not value for value in normalized_exclusions):
        raise ValueError(f"category {category_id!r} has an empty normalized exclusion")

    return CareerCategory(
        id=category_id,
        label_en=label_en,
        label_fr=label_fr,
        phrases_en=phrases_en,
        phrases_fr=phrases_fr,
        abbreviations=abbreviations,
        synonyms_en=synonyms_en,
        synonyms_fr=synonyms_fr,
        exclusions=exclusions,
        positive_examples=positive_examples,
        negative_examples=negative_examples,
        terms=tuple(terms),
        normalized_exclusions=normalized_exclusions,
    )


def _required_string(raw: dict[str, Any], key: str, index: int) -> str:
    value = raw.get(key)
    if not isinstance(value, str):
        raise ValueError(f"category {index} field {key!r} must be a string")
    return value.strip()


def _string_tuple(raw: dict[str, Any], key: str, category_id: str) -> tuple[str, ...]:
    values = raw.get(key)
    if not isinstance(values, list) or any(not isinstance(value, str) for value in values):
        raise ValueError(f"category {category_id!r} field {key!r} must be a string list")
    return tuple(value.strip() for value in values if value.strip())


def _contains_phrase(haystack: str, needle: str) -> bool:
    return f" {needle} " in f" {haystack} "
