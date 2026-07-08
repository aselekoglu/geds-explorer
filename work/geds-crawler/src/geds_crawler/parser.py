from __future__ import annotations

import re

from bs4 import BeautifulSoup, Tag

from .models import Department, OrgUnit, PersonIndex
from .urls import geds_url, parse_geds_link


CONTACT_LINE_RE = re.compile(
    r"\b(?:telephone|tel|phone|facsimile|fax|email|e-mail|courriel|address|adresse)\b\s*:?.*$",
    re.IGNORECASE,
)
EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PHONE_RE = re.compile(r"(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}(?:\s*(?:x|ext\.?)\s*\d+)?", re.IGNORECASE)
SPACE_RE = re.compile(r"\s+")


def clean_text(value: str) -> str:
    return SPACE_RE.sub(" ", value).strip()


def strip_contact_text(value: str) -> str:
    without_labels = CONTACT_LINE_RE.sub("", value)
    without_email = EMAIL_RE.sub("", without_labels)
    without_phone = PHONE_RE.sub("", without_email)
    return clean_text(without_phone.strip(" -|,;:"))


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def _link_text(link: Tag) -> str:
    return clean_text(link.get_text(" ", strip=True))


def extract_departments(html: str, allowed_names: set[str] | None = None) -> list[Department]:
    allowed = {name.casefold() for name in allowed_names} if allowed_names else None
    departments: list[Department] = []
    seen: set[str] = set()

    for link in _soup(html).find_all("a", href=True):
        parsed = parse_geds_link(link.get("href"))
        name = _link_text(link)
        if not parsed or parsed.pgid != "014" or not name:
            continue
        if allowed is not None and name.casefold() not in allowed:
            continue
        if parsed.dn in seen:
            continue
        seen.add(parsed.dn)
        departments.append(Department(name=name, dn=parsed.dn, source_url=parsed.url))

    return departments


def extract_org_children(
    html: str,
    parent_dn: str,
    department_dn: str,
    parent_path: str,
    depth: int,
) -> list[OrgUnit]:
    children: list[OrgUnit] = []
    seen: set[str] = set()

    for link in _soup(html).find_all("a", href=True):
        parsed = parse_geds_link(link.get("href"))
        name = _link_text(link)
        if not parsed or parsed.pgid != "014" or not name:
            continue
        if parsed.dn == parent_dn or parsed.dn in seen:
            continue
        seen.add(parsed.dn)
        children.append(
            OrgUnit(
                name=name,
                dn=parsed.dn,
                parent_dn=parent_dn,
                department_dn=department_dn,
                depth=depth + 1,
                org_path=f"{parent_path} / {name}",
                source_url=parsed.url,
            )
        )

    return children


def _candidate_title(link: Tag, display_name: str) -> str | None:
    inline = _parse_person_link_text(_link_text(link))[1]
    if inline:
        return inline

    parent = link.find_parent(["li", "tr", "p", "div"])
    if parent is None:
        return None

    chunks: list[str] = []
    for text in parent.stripped_strings:
        cleaned = strip_contact_text(text)
        normalized = cleaned.strip(" ;")
        if normalized and normalized != _link_text(link).strip(" ;") and normalized != display_name:
            chunks.append(cleaned)

    title = clean_text(" ".join(chunks)).strip(" ;")
    if title == display_name:
        return None
    return title or None


def _parse_person_link_text(value: str) -> tuple[str, str | None]:
    parts = [strip_contact_text(part) for part in value.replace("\xa0", " ").split(";")]
    parts = [part for part in parts if part]
    if not parts:
        return "", None
    return parts[0], clean_text(" ".join(parts[1:])) or None


def extract_people(
    html: str,
    org_dn: str,
    department_dn: str,
    department_name: str,
    org_name: str,
    org_path: str,
) -> list[PersonIndex]:
    people: list[PersonIndex] = []
    seen: set[str] = set()

    for link in _soup(html).find_all("a", href=True):
        parsed = parse_geds_link(link.get("href"))
        display_name, inline_title = _parse_person_link_text(_link_text(link))
        if not parsed or parsed.pgid != "015" or not display_name:
            continue
        if parsed.dn in seen:
            continue
        seen.add(parsed.dn)
        people.append(
            PersonIndex(
                display_name=display_name,
                title=inline_title or _candidate_title(link, display_name),
                org_dn=org_dn,
                department_dn=department_dn,
                department_name=department_name,
                org_unit=org_name,
                org_path=org_path,
                source_url=geds_url("015", parsed.dn),
            )
        )

    return people
