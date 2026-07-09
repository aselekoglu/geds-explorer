from pathlib import Path
from urllib.parse import urlsplit, parse_qsl

from geds_crawler.parser import (
    extract_departments,
    extract_org_children,
    extract_people,
    extract_people_page,
    strip_contact_text,
)
from geds_crawler.urls import geds_url


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


def test_extract_people_page_returns_people_and_canonical_next_url():
    page = extract_people_page(
        load_fixture("org_people_page_1.html"),
        org_dn="OU=TEAM,OU=ISED-ISDE,O=GC,C=CA",
        department_dn="OU=ISED-ISDE,O=GC,C=CA",
        department_name="ISED",
        org_name="Team",
        org_path="ISED / Team",
    )
    assert len(page.people) == 25
    assert page.next_url is not None
    parsed = urlsplit(page.next_url)
    assert (parsed.scheme, parsed.netloc, parsed.path) == (
        "https", "geds-sage.gc.ca", "/en/GEDS"
    )
    assert dict(parse_qsl(parsed.query))["page"] == "2"


def test_exactly_25_people_without_next_link_is_terminal():
    links = "".join(
        f'<a href="{geds_url("015", f"CN=Person {index},OU=TEAM,O=GC,C=CA")}">'
        f"Person {index}</a>"
        for index in range(25)
    )
    page = extract_people_page(
        f"<html><body>{links}</body></html>",
        org_dn="OU=TEAM,OU=ISED-ISDE,O=GC,C=CA",
        department_dn="OU=ISED-ISDE,O=GC,C=CA",
        department_name="ISED",
        org_name="Team",
        org_path="ISED / Team",
    )
    assert len(page.people) == 25
    assert page.next_url is None


def test_live_ajax_pagination_metadata_produces_second_page_request():
    html = """
    <div id="personResults">
      <a href="?pgid=015&dn=Q049SmFuZSBEb2UsT1U9VEVBTSxPPUdDLEM9Q0E=">Doe, Jane</a>
    </div>
    <script>
      showPageController(1,116,"signed-filter-token",1,"");
    </script>
    """

    page = extract_people_page(
        html,
        org_dn="OU=TEAM,O=GC,C=CA",
        department_dn="OU=DEPT,O=GC,C=CA",
        department_name="Department",
        org_name="Team",
        org_path="Department / Team",
        page_url="https://geds-sage.gc.ca/en/GEDS?pgid=014&dn=seed",
    )

    assert page.next_url is not None
    query = dict(parse_qsl(urlsplit(page.next_url).query, keep_blank_values=True))
    assert query == {
        "p1": "2",
        "p2": "signed-filter-token",
        "p3": "1",
        "p4": "",
        "pgid": "153",
        "total": "116",
    }


def test_ajax_result_page_uses_request_metadata_to_continue_until_total():
    html = '<ol start="26"><li><a href="?pgid=015&dn=Q049Sm9obiBEb2UsT1U9VEVBTSxPPUdDLEM9Q0E=">Doe, John</a></li></ol>'
    page_url = (
        "https://geds-sage.gc.ca/en/GEDS?"
        "pgid=153&p1=2&p2=signed-filter-token&p3=1&p4=&total=116"
    )

    page = extract_people_page(
        html,
        org_dn="OU=TEAM,O=GC,C=CA",
        department_dn="OU=DEPT,O=GC,C=CA",
        department_name="Department",
        org_name="Team",
        org_path="Department / Team",
        page_url=page_url,
    )

    assert page.next_url is not None
    query = dict(parse_qsl(urlsplit(page.next_url).query, keep_blank_values=True))
    assert query["p1"] == "3"
    assert query["total"] == "116"
