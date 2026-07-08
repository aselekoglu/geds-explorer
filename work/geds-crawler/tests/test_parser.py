from pathlib import Path

from geds_crawler.parser import (
    extract_departments,
    extract_org_children,
    extract_people,
    strip_contact_text,
)


FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_department_list_extracts_allowlisted_department_links():
    departments = extract_departments(
        load_fixture("department_list.html"),
        allowed_names={
            "Shared Services Canada",
            "Treasury Board of Canada Secretariat",
        },
    )

    assert [department.name for department in departments] == [
        "Shared Services Canada",
        "Treasury Board of Canada Secretariat",
    ]
    assert all(department.dn for department in departments)
    assert all(department.source_url.startswith("https://geds-sage.gc.ca/en/GEDS") for department in departments)


def test_org_page_extracts_child_org_links_only():
    children = extract_org_children(
        load_fixture("org_page.html"),
        parent_dn="OU=SSC-SPC,O=GC,C=CA",
        department_dn="OU=SSC-SPC,O=GC,C=CA",
        parent_path="Shared Services Canada",
        depth=0,
    )

    assert [child.name for child in children] == [
        "Digital Communications and Collaboration",
        "Cloud Services",
    ]
    assert [child.depth for child in children] == [1, 1]
    assert children[0].org_path == "Shared Services Canada / Digital Communications and Collaboration"


def test_people_extraction_strips_contact_values_and_keeps_source_url():
    people = extract_people(
        load_fixture("org_page.html"),
        org_dn="OU=SSC-SPC,O=GC,C=CA",
        department_dn="OU=SSC-SPC,O=GC,C=CA",
        department_name="Shared Services Canada",
        org_name="Shared Services Canada",
        org_path="Shared Services Canada",
    )

    assert [person.display_name for person in people] == [
        "Doe, Jane",
        "Smith, John",
        "Bruneau, Eve-Marie",
        "Notitle, Person",
    ]
    assert people[0].title == "Director, Enterprise Platforms"
    assert people[1].title == "Senior IT Security Analyst"
    assert people[2].title == "Senior Financial Analyst"
    assert people[3].title is None
    assert all(person.source_url.startswith("https://geds-sage.gc.ca/en/GEDS") for person in people)

    serialized = "\n".join(str(person.__dict__) for person in people)
    assert "613-555-0100" not in serialized
    assert "jane.doe@example.gc.ca" not in serialized
    assert "Telephone" not in serialized
    assert "Email" not in serialized


def test_strip_contact_text_removes_phone_email_and_contact_labels():
    value = strip_contact_text("Director Telephone: 613-555-0100 Email: jane.doe@example.gc.ca")

    assert value == "Director"
