from __future__ import annotations

from pathlib import Path

import pytest

from geds_crawler.canonical_hierarchy import (
    derive_hierarchy,
    dn_suffixes,
    stable_org_id,
    validate_hierarchy,
)
from geds_crawler.canonical_models import CanonicalOrganization
from geds_crawler.canonical_resolver import resolve_completed_run


REAL_RUN_ID = "769b7b73-dc8e-4911-b1d5-80cbe07e34f8"


def _row(
    dn: str,
    name: str,
    *,
    department_dn: str = "OU=Dept,O=GC,C=CA",
    stored_parent: str | None = None,
) -> dict[str, object]:
    return {
        "dn": dn,
        "name": name,
        "parent_dn": stored_parent,
        "department_dn": department_dn,
        "depth": 99,
        "org_path": "wrong / stored / path",
        "source_url": f"https://example.test/org/{stable_org_id(dn)}",
    }


def test_dn_suffixes_preserve_escaped_commas():
    assert dn_suffixes(r"OU=Policy\, Planning,OU=Branch,O=GC,C=CA") == (
        "OU=Branch,O=GC,C=CA",
        "O=GC,C=CA",
        "C=CA",
    )


def test_dn_suffixes_handle_escaped_backslash_before_separator():
    assert dn_suffixes(r"OU=Path\\,OU=Branch,O=GC,C=CA") == (
        "OU=Branch,O=GC,C=CA",
        "O=GC,C=CA",
        "C=CA",
    )


def test_derive_hierarchy_uses_nearest_known_suffix_not_stored_parent():
    department_dn = "OU=Dept,O=GC,C=CA"
    rows = [
        _row(department_dn, "Department", stored_parent="broken"),
        _row(
            f"OU=Branch,{department_dn}",
            "Branch",
            stored_parent="self",
        ),
        _row(
            f"OU=Team,OU=Branch,{department_dn}",
            "Team",
            stored_parent="unrelated",
        ),
    ]

    organizations = derive_hierarchy(rows)
    by_name = {org.name: org for org in organizations}

    assert by_name["Department"].parent_dn is None
    assert by_name["Department"].depth == 0
    assert by_name["Branch"].parent_dn == department_dn
    assert by_name["Branch"].canonical_path == ("Department", "Branch")
    assert by_name["Team"].parent_dn == f"OU=Branch,{department_dn}"
    assert by_name["Team"].canonical_path == (
        "Department",
        "Branch",
        "Team",
    )
    assert by_name["Team"].depth == 2


def test_derive_hierarchy_skips_missing_intermediate_suffix():
    department_dn = "OU=Dept,O=GC,C=CA"
    rows = [
        _row(department_dn, "Department"),
        _row(
            f"OU=Team,OU=Missing,{department_dn}",
            "Team",
        ),
    ]

    organizations = derive_hierarchy(rows)
    team = next(org for org in organizations if org.name == "Team")

    assert team.parent_dn == department_dn
    assert team.canonical_path == ("Department", "Team")


def test_stable_org_id_is_case_insensitive_and_url_safe():
    first = stable_org_id("OU=Team,OU=Dept,O=GC,C=CA")
    second = stable_org_id("ou=team,ou=dept,o=gc,c=ca")

    assert first == second
    assert len(first) == 22
    assert first.replace("-", "").replace("_", "").isalnum()


def test_validate_hierarchy_detects_cycle():
    first = CanonicalOrganization(
        org_id="first",
        dn="OU=First,O=GC,C=CA",
        name="First",
        parent_dn="OU=Second,O=GC,C=CA",
        department_dn="OU=First,O=GC,C=CA",
        depth=1,
        canonical_path=("Second", "First"),
        source_url="https://example.test/first",
    )
    second = CanonicalOrganization(
        org_id="second",
        dn="OU=Second,O=GC,C=CA",
        name="Second",
        parent_dn="OU=First,O=GC,C=CA",
        department_dn="OU=First,O=GC,C=CA",
        depth=1,
        canonical_path=("First", "Second"),
        source_url="https://example.test/second",
    )

    quality = validate_hierarchy((first, second))

    assert quality.root_count == 0
    assert quality.cycle_count == 2


def test_current_lineage_derives_expected_cycle_free_shape():
    project_root = _find_real_project_root()
    if project_root is None:
        pytest.skip("real GEDS outputs are not available")
    resolved = resolve_completed_run(
        project_root / "outputs" / "control" / "control.sqlite",
        REAL_RUN_ID,
    )

    organizations = derive_hierarchy(tuple(resolved.iter_orgs()))
    quality = validate_hierarchy(organizations)

    assert len(organizations) == 26421
    assert quality.root_count == 156
    assert quality.missing_parent_count == 0
    assert quality.cycle_count == 0
    assert quality.max_depth == 12


def _find_real_project_root() -> Path | None:
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "outputs" / "control" / "control.sqlite"
        if candidate.is_file():
            return parent
    return None
