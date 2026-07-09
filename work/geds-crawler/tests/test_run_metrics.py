from __future__ import annotations

from datetime import datetime, timezone, timedelta
import pytest

from geds_crawler.run_metrics import (
    calculate_progress,
    ewma,
    estimate_remaining_requests,
    estimate_eta,
    EtaEstimate,
)


def test_calculate_progress():
    res = calculate_progress(total=100, succeeded=20, failed=5)
    assert res == {
        "total_orgs": 100,
        "completed_orgs": 20,
        "failed_orgs": 5,
        "terminal_orgs": 25,
        "percent": 25.0,
    }

    res_empty = calculate_progress(total=0, succeeded=0, failed=0)
    assert res_empty["percent"] == 0.0


def test_ewma():
    # Empty sequence
    assert ewma([]) is None

    # Single value
    assert ewma([10.0]) == 10.0

    # Multi-value:
    # y0 = 10.0
    # y1 = 0.25 * 20.0 + 0.75 * 10.0 = 5.0 + 7.5 = 12.5
    # y2 = 0.25 * 30.0 + 0.75 * 12.5 = 7.5 + 9.375 = 16.875
    assert ewma([10.0, 20.0, 30.0], alpha=0.25) == 16.875


def test_estimate_remaining_requests():
    # No completed samples (defaults to 1.0 request multiplier per remaining org)
    assert estimate_remaining_requests(
        known_pending_pages=5,
        incomplete_orgs_without_known_next=3,
        completed_org_request_samples=[],
    ) == 8.0

    # Completed samples exist: EWMA of [10.0, 20.0] with alpha=0.25 is 12.5.
    # remaining = 5 + 3 * max(1.0, 12.5) = 5 + 37.5 = 42.5
    assert estimate_remaining_requests(
        known_pending_pages=5,
        incomplete_orgs_without_known_next=3,
        completed_org_request_samples=[10.0, 20.0],
    ) == 42.5

    # EWMA under 1.0 is capped at 1.0 multiplier
    # EWMA of [0.5] is 0.5. Cap at 1.0.
    # remaining = 5 + 3 * 1.0 = 8.0
    assert estimate_remaining_requests(
        known_pending_pages=5,
        incomplete_orgs_without_known_next=3,
        completed_org_request_samples=[0.5],
    ) == 8.0


def test_estimate_eta_basis_and_confidence():
    now = datetime(2026, 7, 9, 12, 0, 0, tzinfo=timezone.utc)

    # 1. Configured rate fallback (measured_at is None)
    est = estimate_eta(
        remaining_requests=100.0,
        configured_rps=2.0,
        measured_rps=5.0,
        measured_at=None,
        completed_orgs=10,
        now=now,
    )
    assert est.basis == "configured_rate"
    assert est.confidence == "low"
    assert est.expected_seconds == 50
    # Low confidence uncertainty multipliers: 0.65 - 1.55
    assert est.low_seconds == 32  # round(50 * 0.65) = 32.5 -> rounds to 32 (round to even)
    assert est.high_seconds == 78  # round(50 * 1.55) = 77.5 -> rounds to 78 (round to even)
    assert est.estimated_finish_at == "2026-07-09T12:00:50+00:00"

    # 2. Measured rate usage (measured_at is within 30 seconds)
    measured_at = now - timedelta(seconds=15)
    est2 = estimate_eta(
        remaining_requests=100.0,
        configured_rps=2.0,
        measured_rps=5.0,
        measured_at=measured_at,
        completed_orgs=100,  # medium confidence
        now=now,
    )
    assert est2.basis == "measured_rate"
    assert est2.confidence == "medium"
    assert est2.expected_seconds == 20  # 100 / 5.0
    # Medium confidence uncertainty multipliers: 0.80 - 1.30
    assert est2.low_seconds == 16
    assert est2.high_seconds == 26
    assert est2.estimated_finish_at == "2026-07-09T12:00:20+00:00"

    # 3. Measured rate stale fallback (> 30 seconds)
    stale_measured_at = now - timedelta(seconds=31)
    est3 = estimate_eta(
        remaining_requests=100.0,
        configured_rps=2.0,
        measured_rps=5.0,
        measured_at=stale_measured_at,
        completed_orgs=250,  # high confidence
        now=now,
    )
    assert est3.basis == "configured_rate"
    assert est3.confidence == "high"
    assert est3.expected_seconds == 50  # 100 / 2.0
    # High confidence uncertainty multipliers: 0.90 - 1.15
    assert est3.low_seconds == 45
    assert est3.high_seconds == 57  # round(50 * 1.15) = 57.49999999999999 -> rounds to 57
    assert est3.estimated_finish_at == "2026-07-09T12:00:50+00:00"
