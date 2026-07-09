from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal, Sequence


@dataclass(frozen=True)
class EtaEstimate:
    expected_seconds: int | None
    low_seconds: int | None
    high_seconds: int | None
    confidence: Literal["low", "medium", "high"]
    basis: Literal["configured_rate", "measured_rate"]
    estimated_finish_at: str | None


def calculate_progress(total: int, succeeded: int, failed: int) -> dict:
    terminal = succeeded + failed
    percent = (terminal / total * 100.0) if total > 0 else 0.0
    return {
        "total_orgs": total,
        "completed_orgs": succeeded,
        "failed_orgs": failed,
        "terminal_orgs": terminal,
        "percent": percent,
    }


def ewma(values: Sequence[float], alpha: float = 0.25) -> float | None:
    if not values:
        return None
    current = values[0]
    for v in values[1:]:
        current = alpha * v + (1 - alpha) * current
    return current


def estimate_remaining_requests(
    known_pending_pages: int,
    incomplete_orgs_without_known_next: int,
    completed_org_request_samples: Sequence[float],
) -> float:
    ewma_val = ewma(completed_org_request_samples)
    mult = max(1.0, ewma_val) if ewma_val is not None else 1.0
    return known_pending_pages + incomplete_orgs_without_known_next * mult


def estimate_eta(
    remaining_requests: float,
    configured_rps: float,
    measured_rps: float | None,
    measured_at: datetime | None,
    completed_orgs: int,
    now: datetime,
) -> EtaEstimate:
    if completed_orgs < 50:
        confidence = "low"
    elif completed_orgs < 200:
        confidence = "medium"
    else:
        confidence = "high"

    # Determine rate and basis
    is_measured_valid = (
        measured_rps is not None
        and measured_rps > 0
        and measured_at is not None
        and (now - measured_at).total_seconds() <= 30
    )

    if is_measured_valid:
        rate = measured_rps
        basis = "measured_rate"
    else:
        rate = configured_rps
        basis = "configured_rate"

    if rate <= 0 or remaining_requests <= 0:
        return EtaEstimate(
            expected_seconds=0,
            low_seconds=0,
            high_seconds=0,
            confidence=confidence,
            basis=basis,
            estimated_finish_at=now.isoformat(),
        )

    expected = remaining_requests / rate
    expected_seconds = int(round(expected))

    # Apply uncertainty multipliers
    if confidence == "low":
        low_mult, high_mult = 0.65, 1.55
    elif confidence == "medium":
        low_mult, high_mult = 0.80, 1.30
    else:
        low_mult, high_mult = 0.90, 1.15

    low_seconds = int(round(expected_seconds * low_mult))
    high_seconds = int(round(expected_seconds * high_mult))

    estimated_finish = now + timedelta(seconds=expected_seconds)
    
    return EtaEstimate(
        expected_seconds=expected_seconds,
        low_seconds=low_seconds,
        high_seconds=high_seconds,
        confidence=confidence,
        basis=basis,
        estimated_finish_at=estimated_finish.isoformat(),
    )
