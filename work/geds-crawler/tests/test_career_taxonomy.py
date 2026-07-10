from __future__ import annotations

import json
from pathlib import Path

import pytest

from geds_crawler.career_taxonomy import load_taxonomy, normalize_text, tokenize


TAXONOMY_PATH = (
    Path(__file__).parents[1]
    / "src"
    / "geds_crawler"
    / "data"
    / "career_taxonomy.v1.json"
)

REQUIRED_CATEGORY_IDS = {
    "software-digital-delivery",
    "data-ai-research",
    "cyber-it-infrastructure",
    "policy-programs-regulation",
    "communications-public-affairs",
    "finance-audit-procurement",
    "legal-enforcement-investigations",
    "science-engineering-environment-health",
    "hr-organizational-services",
    "executive-management-coordination",
}


@pytest.fixture
def taxonomy():
    return load_taxonomy(TAXONOMY_PATH)


@pytest.mark.parametrize(
    ("query", "category"),
    [
        ("AI", "data-ai-research"),
        ("intelligence artificielle", "data-ai-research"),
        ("cybersécurité", "cyber-it-infrastructure"),
        ("approvisionnement", "finance-audit-procurement"),
        ("relations publiques", "communications-public-affairs"),
        ("développement de logiciels", "software-digital-delivery"),
        ("politiques publiques", "policy-programs-regulation"),
        ("ressources humaines", "hr-organizational-services"),
    ],
)
def test_interpret_maps_bilingual_terms(query, category, taxonomy):
    result = taxonomy.interpret(query)

    assert category in result.category_ids
    assert result.evidence
    assert result.taxonomy_version == taxonomy.version


def test_interpret_is_deterministic_and_explains_expansion(taxonomy):
    first = taxonomy.interpret("AI and software / IA et logiciels")
    second = taxonomy.interpret("AI and software / IA et logiciels")

    assert first == second
    assert first.category_ids == (
        "data-ai-research",
        "software-digital-delivery",
    )
    assert "artificial intelligence" in first.expanded_terms
    assert any("AI" in item or "ai" in item for item in first.evidence)


def test_taxonomy_contains_the_versioned_initial_categories(taxonomy):
    assert taxonomy.version == "1.0.0"
    assert {category.id for category in taxonomy.categories} == REQUIRED_CATEGORY_IDS
    assert all(category.label_en and category.label_fr for category in taxonomy.categories)
    assert all(category.positive_terms for category in taxonomy.categories)


def test_normalization_is_diacritic_and_punctuation_aware():
    assert normalize_text("  Cybersécurité—R&D  ") == "cybersecurite r d"
    assert tokenize("Intelligence artificielle / AI") == (
        "intelligence",
        "artificielle",
        "ai",
    )


def test_loader_rejects_duplicate_category_ids(tmp_path):
    payload = json.loads(TAXONOMY_PATH.read_text(encoding="utf-8"))
    payload["categories"].append(payload["categories"][0])
    path = tmp_path / "duplicate.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="duplicate category id"):
        load_taxonomy(path)


def test_loader_rejects_normalized_phrase_collision(tmp_path):
    payload = json.loads(TAXONOMY_PATH.read_text(encoding="utf-8"))
    payload["categories"][1]["phrases_en"].append("software development")
    path = tmp_path / "collision.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="positive phrase collision"):
        load_taxonomy(path)


def test_loader_rejects_positive_exclusion_collision(tmp_path):
    payload = json.loads(TAXONOMY_PATH.read_text(encoding="utf-8"))
    payload["categories"][0]["exclusions"].append("software development")
    path = tmp_path / "exclusion-collision.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="positive/exclusion collision"):
        load_taxonomy(path)


def test_loader_requires_bilingual_labels(tmp_path):
    payload = json.loads(TAXONOMY_PATH.read_text(encoding="utf-8"))
    payload["categories"][0]["label_fr"] = ""
    path = tmp_path / "missing-label.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="bilingual labels"):
        load_taxonomy(path)
