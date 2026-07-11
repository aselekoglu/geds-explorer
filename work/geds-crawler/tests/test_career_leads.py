from __future__ import annotations

from pathlib import Path

import pytest

from geds_crawler.career_leads import infer_lead, infer_leads, load_lead_rules


RULES_PATH = Path(__file__).parents[1] / "src" / "geds_crawler" / "data" / "lead_titles.v1.json"


@pytest.fixture
def rules():
    return load_lead_rules(RULES_PATH)


@pytest.mark.parametrize(
    ("title", "expected_kind"),
    [
        ("Manager, Data Platforms", "possible_team_lead"),
        ("Gestionnaire, plateformes de donnees", "possible_team_lead"),
        ("Director, Digital Strategy", "career_conversation_lead"),
        ("Directrice, Strategie numerique", "career_conversation_lead"),
        ("Chief Data Officer", "career_conversation_lead"),
        ("Commissaire adjoint", "career_conversation_lead"),
    ],
)
def test_bilingual_leadership_titles_are_inferred_without_personal_data(title, expected_kind, rules):
    lead = infer_lead(
        title=title,
        person_org_id="team",
        target_org_id="team",
        source_url="https://geds.example/person",
        rules=rules,
    )

    assert lead is not None
    assert lead.kind == expected_kind
    assert lead.confidence == "high"
    assert lead.title == title
    assert lead.source_url == "https://geds.example/person"
    assert set(lead.__dataclass_fields__) == {
        "kind",
        "confidence",
        "title",
        "org_id",
        "source_url",
        "reasons",
    }


@pytest.mark.parametrize(
    "title",
    [
        "Executive Assistant",
        "Advisor to the Director",
        "Acting Assistant",
        "Conseiller aupres de la directrice",
        "Administrative Support Officer",
        "Office of the Director",
    ],
)
def test_assistants_advisors_support_and_office_titles_are_excluded(title, rules):
    assert infer_lead(title, "team", "team", "https://geds.example/person", rules) is None


def test_direct_org_leads_outrank_parent_org_leads_and_results_are_capped(rules):
    people = [
        {"title": "Director General", "org_id": "parent", "source_url": "https://geds.example/dg"},
        {"title": "Manager, Platform A", "org_id": "team", "source_url": "https://geds.example/a"},
        {"title": "Manager, Platform B", "org_id": "team", "source_url": "https://geds.example/b"},
        {"title": "Chief Architect", "org_id": "parent", "source_url": "https://geds.example/chief"},
        {"title": "Head of Delivery", "org_id": "team", "source_url": "https://geds.example/head"},
    ]

    leads = infer_leads("team", people, rules, parent_org_ids=("parent",))

    assert len(leads) == 3
    assert all(lead.org_id == "team" for lead in leads)
    assert all(lead.confidence == "high" for lead in leads)
    assert all(lead.reasons for lead in leads)


def test_parent_org_lead_is_lower_confidence_and_explains_scope(rules):
    leads = infer_leads(
        "team",
        [{"title": "Director General", "org_id": "parent", "source_url": "https://geds.example/dg"}],
        rules,
        parent_org_ids=("parent",),
    )

    assert leads[0].confidence == "medium"
    assert "parent organization" in " ".join(leads[0].reasons).lower()

