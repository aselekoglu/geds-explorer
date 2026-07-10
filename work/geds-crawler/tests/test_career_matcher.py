from __future__ import annotations

from pathlib import Path

import pytest

from geds_crawler.career_matcher import (
    CareerMatcher,
    MatchEntity,
    evaluate_matcher,
    load_evaluation_cases,
)
from geds_crawler.career_taxonomy import load_taxonomy


ROOT = Path(__file__).parents[1]
TAXONOMY_PATH = ROOT / "src" / "geds_crawler" / "data" / "career_taxonomy.v1.json"
EVALUATION_PATH = ROOT / "tests" / "fixtures" / "career_match_evaluation.v1.json"


@pytest.fixture
def taxonomy():
    return load_taxonomy(TAXONOMY_PATH)


@pytest.fixture
def matcher(taxonomy):
    return CareerMatcher(taxonomy)


def test_direct_title_outranks_ancestor_only(matcher, taxonomy):
    ai_query = taxonomy.interpret("AI")
    title = matcher.match_entity(
        MatchEntity("p1", "person", "Machine Learning Engineer", "Platform", ()),
        ai_query,
    )
    ancestor = matcher.match_entity(
        MatchEntity("o1", "organization", "", "Administration", ("AI Centre",)),
        ai_query,
    )

    assert title.score > ancestor.score
    assert title.confidence == "high"
    assert title.evidence[0].field == "title"
    assert ancestor.confidence == "exploratory"


def test_exclusion_suppresses_ambiguous_policy_term(matcher, taxonomy):
    policy_query = taxonomy.interpret("policy")
    result = matcher.match_entity(
        MatchEntity("o1", "organization", "", "Insurance Policy Processing", ()),
        policy_query,
    )

    assert result.score == 0
    assert result.category_ids == ()
    assert result.exclusions


def test_synonym_and_abbreviation_have_explicit_explainable_weights(matcher, taxonomy):
    query = taxonomy.interpret("AI and software")
    result = matcher.match_entity(
        MatchEntity("p1", "person", "AI Software Developer", "Digital Delivery", ()),
        query,
    )

    assert result.score == 325
    assert [(item.matched_phrase, item.weight) for item in result.evidence] == [
        ("AI", 100),
        ("digital delivery", 85),
        ("software", 70),
        ("developer", 70),
    ]
    assert result.category_ids == (
        "data-ai-research",
        "software-digital-delivery",
    )


def test_duplicate_evidence_is_only_counted_once(matcher, taxonomy):
    result = matcher.match_entity(
        MatchEntity("p1", "person", "Cybersecurity Cybersecurity Analyst", "", ()),
        taxonomy.interpret("cybersecurity"),
    )

    assert result.score == 100
    assert len(result.evidence) == 1


def test_ancestor_only_evidence_is_capped_at_medium_confidence(matcher, taxonomy):
    result = matcher.match_entity(
        MatchEntity(
            "o1",
            "organization",
            "",
            "Administrative Services",
            ("AI Centre", "Machine Learning Office", "Data Science Directorate"),
        ),
        taxonomy.interpret("AI"),
    )

    assert result.score == 60
    assert result.confidence == "medium"
    assert {item.field for item in result.evidence} == {"ancestor"}


def test_reviewed_evaluation_fixture_passes_and_has_required_coverage(taxonomy):
    cases = load_evaluation_cases(EVALUATION_PATH)
    report = evaluate_matcher(cases, taxonomy)

    assert len(cases) == 40
    assert report.total_cases == 40
    assert report.passed_cases == 40
    assert report.failed_case_ids == ()
    assert report.forbidden_match_case_ids == ()
    assert report.taxonomy_version == "1.0.0"
    assert {case.expected_categories[0] for case in cases if case.expected_categories} == {
        category.id for category in taxonomy.categories
    }
