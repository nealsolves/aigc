"""Tests for policy version dates (M2 feature)."""
import pytest
from datetime import date

from aigc._internal.policy_loader import validate_policy_dates, load_policy
from aigc._internal.errors import PolicyValidationError


# ── Date validation ──────────────────────────────────────────────


def test_no_dates_always_active():
    evidence = validate_policy_dates({"policy_version": "1.0"})
    assert evidence["active"] is True
    assert evidence["policy_dates"] == "none_specified"


def test_inside_active_window():
    policy = {
        "effective_date": "2020-01-01",
        "expiration_date": "2099-12-31",
    }
    evidence = validate_policy_dates(
        policy, clock=lambda: date(2025, 6, 15)
    )
    assert evidence["active"] is True


def test_before_effective_date():
    policy = {"effective_date": "2099-01-01"}
    with pytest.raises(PolicyValidationError, match="not yet active"):
        validate_policy_dates(
            policy, clock=lambda: date(2025, 1, 1)
        )


def test_after_expiration_date():
    policy = {"expiration_date": "2020-12-31"}
    with pytest.raises(PolicyValidationError, match="expired"):
        validate_policy_dates(
            policy, clock=lambda: date(2025, 1, 1)
        )


def test_effective_after_expiration_invalid():
    policy = {
        "effective_date": "2025-12-01",
        "expiration_date": "2025-01-01",
    }
    with pytest.raises(PolicyValidationError, match="after expiration"):
        validate_policy_dates(
            policy, clock=lambda: date(2025, 6, 15)
        )


def test_exact_effective_date_is_active():
    """Policy is active on its effective_date."""
    policy = {"effective_date": "2025-06-15"}
    evidence = validate_policy_dates(
        policy, clock=lambda: date(2025, 6, 15)
    )
    assert evidence["active"] is True


def test_exact_expiration_date_is_active():
    """Policy is active on its expiration_date."""
    policy = {"expiration_date": "2025-06-15"}
    evidence = validate_policy_dates(
        policy, clock=lambda: date(2025, 6, 15)
    )
    assert evidence["active"] is True


def test_malformed_date_raises():
    policy = {"effective_date": "not-a-date"}
    with pytest.raises(PolicyValidationError, match="Invalid date format"):
        validate_policy_dates(policy)


def test_invalid_date_type_raises():
    policy = {"effective_date": 12345}
    with pytest.raises(PolicyValidationError, match="Invalid date type"):
        validate_policy_dates(policy)


# ── Clock injection ──────────────────────────────────────────────


def test_clock_injection_deterministic():
    """Clock injection ensures testability without time dependence."""
    policy = {
        "effective_date": "2025-01-01",
        "expiration_date": "2025-12-31",
    }
    fixed_clock = lambda: date(2025, 6, 15)
    e1 = validate_policy_dates(policy, clock=fixed_clock)
    e2 = validate_policy_dates(policy, clock=fixed_clock)
    assert e1 == e2


# ── Evidence in result ───────────────────────────────────────────


def test_evidence_includes_dates():
    policy = {
        "effective_date": "2020-01-01",
        "expiration_date": "2099-12-31",
    }
    evidence = validate_policy_dates(
        policy, clock=lambda: date(2025, 6, 15)
    )
    assert evidence["effective_date"] == "2020-01-01"
    assert evidence["expiration_date"] == "2099-12-31"
    assert evidence["evaluation_date"] == "2025-06-15"


# ── Integration with load_policy ─────────────────────────────────


def test_load_active_policy(tmp_path):
    p = tmp_path / "active.yaml"
    p.write_text(
        "policy_version: '1.0'\nroles:\n  - planner\n"
        "effective_date: '2020-01-01'\nexpiration_date: '2099-12-31'\n"
    )
    policy = load_policy(str(p))
    assert policy["effective_date"] == "2020-01-01"


def test_load_expired_policy(tmp_path):
    p = tmp_path / "expired.yaml"
    p.write_text(
        "policy_version: '1.0'\nroles:\n  - planner\n"
        "expiration_date: '2020-12-31'\n"
    )
    with pytest.raises(PolicyValidationError, match="expired"):
        load_policy(str(p))
