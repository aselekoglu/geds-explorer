from __future__ import annotations

import base64
import hashlib
from collections.abc import Iterable, Mapping
from typing import Any

from .canonical_models import CanonicalOrganization, HierarchyQuality
from .canonical_resolver import CanonicalValidationError


def dn_suffixes(dn: str) -> tuple[str, ...]:
    """Return DN suffixes following each unescaped comma."""

    suffixes: list[str] = []
    backslashes = 0
    for index, char in enumerate(dn):
        if char == "\\":
            backslashes += 1
            continue
        if char == "," and backslashes % 2 == 0:
            suffixes.append(dn[index + 1 :].strip())
        backslashes = 0
    return tuple(suffixes)


def stable_org_id(dn: str) -> str:
    digest = hashlib.sha256(dn.casefold().encode("utf-8")).digest()[:16]
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def derive_hierarchy(
    rows: Iterable[Mapping[str, Any]],
) -> tuple[CanonicalOrganization, ...]:
    """Derive a deterministic hierarchy from DN suffix relationships."""

    source_by_key: dict[str, dict[str, Any]] = {}
    for source in rows:
        row = dict(source)
        dn = str(row.get("dn") or "").strip()
        if not dn:
            raise CanonicalValidationError("Organization row has no DN")
        key = dn.casefold()
        if key in source_by_key:
            raise CanonicalValidationError(f"Duplicate organization DN: {dn}")
        row["dn"] = dn
        source_by_key[key] = row

    parent_by_key: dict[str, str | None] = {}
    for key, row in source_by_key.items():
        parent_by_key[key] = next(
            (
                suffix.casefold()
                for suffix in dn_suffixes(str(row["dn"]))
                if suffix.casefold() in source_by_key
            ),
            None,
        )

    path_cache: dict[str, tuple[str, ...]] = {}

    def path_for(key: str, visiting: frozenset[str] = frozenset()) -> tuple[str, ...]:
        cached = path_cache.get(key)
        if cached is not None:
            return cached
        if key in visiting:
            raise CanonicalValidationError(
                f"DN-derived organization cycle at {source_by_key[key]['dn']}"
            )
        name = str(source_by_key[key].get("name") or "").strip()
        if not name:
            raise CanonicalValidationError(
                f"Organization has no name: {source_by_key[key]['dn']}"
            )
        parent_key = parent_by_key[key]
        path = (
            (name,)
            if parent_key is None
            else (*path_for(parent_key, visiting | {key}), name)
        )
        path_cache[key] = path
        return path

    organizations: list[CanonicalOrganization] = []
    for key in sorted(source_by_key):
        row = source_by_key[key]
        path = path_for(key)
        parent_key = parent_by_key[key]
        organizations.append(
            CanonicalOrganization(
                org_id=stable_org_id(str(row["dn"])),
                dn=str(row["dn"]),
                name=str(row["name"]).strip(),
                parent_dn=(
                    None
                    if parent_key is None
                    else str(source_by_key[parent_key]["dn"])
                ),
                department_dn=str(row.get("department_dn") or "").strip(),
                depth=len(path) - 1,
                canonical_path=path,
                source_url=str(row.get("source_url") or "").strip(),
            )
        )
    return tuple(organizations)


def validate_hierarchy(
    organizations: Iterable[CanonicalOrganization],
) -> HierarchyQuality:
    orgs = tuple(organizations)
    by_key = {org.dn.casefold(): org for org in orgs}
    missing_parent_count = sum(
        1
        for org in orgs
        if org.parent_dn is not None
        and org.parent_dn.casefold() not in by_key
    )
    cycle_nodes: set[str] = set()
    state: dict[str, int] = {}

    def visit(key: str, stack: list[str]) -> None:
        current_state = state.get(key, 0)
        if current_state == 2:
            return
        if current_state == 1:
            cycle_nodes.update(stack[stack.index(key) :])
            return
        state[key] = 1
        stack.append(key)
        parent_dn = by_key[key].parent_dn
        if parent_dn is not None:
            parent_key = parent_dn.casefold()
            if parent_key in by_key:
                visit(parent_key, stack)
        stack.pop()
        state[key] = 2

    for key in by_key:
        visit(key, [])

    return HierarchyQuality(
        root_count=sum(1 for org in orgs if org.parent_dn is None),
        missing_parent_count=missing_parent_count,
        cycle_count=len(cycle_nodes),
        max_depth=max((org.depth for org in orgs), default=0),
    )
