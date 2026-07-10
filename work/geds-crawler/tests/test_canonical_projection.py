from __future__ import annotations

from pathlib import Path

from geds_crawler.canonical_resolver import OverlayQuality, ResolvedSnapshot
from geds_crawler.models import Department, OrgUnit, PersonIndex
from geds_crawler.store import SnapshotStore


DEPARTMENT = Department(
    "Department",
    "dc=department",
    "https://example.test/departments/department",
)
TARGET_DN = "ou=target,dc=department"
OTHER_DN = "ou=other,dc=department"


def _org(dn: str, name: str) -> OrgUnit:
    return OrgUnit(
        name=name,
        dn=dn,
        parent_dn=None,
        department_dn=DEPARTMENT.dn,
        depth=1,
        org_path=f"{DEPARTMENT.name} / {name}",
        source_url=f"https://example.test/orgs/{name.casefold().replace(' ', '-')}",
    )


def _person(source_url: str, org: OrgUnit, display_name: str) -> PersonIndex:
    return PersonIndex(
        display_name=display_name,
        title="Analyst",
        org_dn=org.dn,
        department_dn=DEPARTMENT.dn,
        department_name=DEPARTMENT.name,
        org_unit=org.name,
        org_path=org.org_path,
        source_url=source_url,
    )


def _create_snapshot(
    path: Path,
    *,
    target_name: str,
    target_person_url: str,
    include_other: bool,
) -> None:
    target = _org(TARGET_DN, target_name)
    other = _org(OTHER_DN, "Other")
    with SnapshotStore(path) as store:
        store.init_schema()
        store.upsert_department(DEPARTMENT, "run", "2026-07-10T00:00:00+00:00")
        store.upsert_org_unit(target, "run", "2026-07-10T00:00:00+00:00")
        store.upsert_person(
            _person(target_person_url, target, target_name),
            "run",
            "2026-07-10T00:00:00+00:00",
        )
        if include_other:
            store.upsert_org_unit(other, "run", "2026-07-10T00:00:00+00:00")
            store.upsert_person(
                _person("untargeted-base-person", other, "Untargeted"),
                "run",
                "2026-07-10T00:00:00+00:00",
            )
        store.commit()


def _resolved(tmp_path: Path, quality: OverlayQuality) -> ResolvedSnapshot:
    base = tmp_path / "base.sqlite"
    overlay = tmp_path / "overlay.sqlite"
    _create_snapshot(
        base,
        target_name="Target base",
        target_person_url="base-person",
        include_other=True,
    )
    _create_snapshot(
        overlay,
        target_name="Target refreshed",
        target_person_url="overlay-person",
        include_other=False,
    )
    return ResolvedSnapshot((base,), (overlay,), (base, overlay), quality)


def test_successful_overlay_replaces_base_people_for_target_org(tmp_path):
    resolved = _resolved(
        tmp_path,
        OverlayQuality(frozenset({TARGET_DN}), frozenset(), ()),
    )

    people = {row["source_url"] for row in resolved.iter_people()}

    assert people == {"overlay-person", "untargeted-base-person"}


def test_failed_overlay_discards_partial_rows_and_keeps_base(tmp_path):
    resolved = _resolved(
        tmp_path,
        OverlayQuality(
            frozenset(),
            frozenset({TARGET_DN}),
            (f"partial_overlay_base_fallback:{TARGET_DN}",),
        ),
    )

    people = {row["source_url"] for row in resolved.iter_people()}

    assert people == {"base-person", "untargeted-base-person"}


def test_successful_overlay_replaces_target_org_metadata(tmp_path):
    resolved = _resolved(
        tmp_path,
        OverlayQuality(frozenset({TARGET_DN}), frozenset(), ()),
    )

    orgs = {row["dn"]: row for row in resolved.iter_orgs()}

    assert orgs[TARGET_DN]["name"] == "Target refreshed"
    assert orgs[OTHER_DN]["name"] == "Other"
    assert [row["dn"] for row in resolved.iter_departments()] == [DEPARTMENT.dn]


def test_failed_overlay_keeps_base_org_metadata(tmp_path):
    resolved = _resolved(
        tmp_path,
        OverlayQuality(
            frozenset(),
            frozenset({TARGET_DN}),
            (f"partial_overlay_base_fallback:{TARGET_DN}",),
        ),
    )

    orgs = {row["dn"]: row for row in resolved.iter_orgs()}

    assert orgs[TARGET_DN]["name"] == "Target base"
