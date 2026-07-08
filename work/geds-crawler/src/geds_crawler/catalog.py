from __future__ import annotations

from .models import Department
from .urls import canonical_dn


def select_departments(catalog: list[Department], allowed_dns: set[str]) -> list[Department]:
    normalized_dns = {canonical_dn(dn).strip().upper() for dn in allowed_dns}
    return [
        dept for dept in catalog
        if canonical_dn(dept.dn).strip().upper() in normalized_dns
    ]
