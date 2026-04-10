"""Tests for RiskHistory advisory utility."""
import pytest
from aigc._internal.risk_history import (
    RiskHistory,
    TRAJECTORY_IMPROVING,
    TRAJECTORY_STABLE,
    TRAJECTORY_DEGRADING,
)
from aigc._internal.risk_scoring import RiskScore


# ── Construction ──────────────────────────────────────────────────────────────

def test_entity_id_stored():
    h = RiskHistory("my-workflow")
    assert h.entity_id == "my-workflow"


def test_entity_id_non_string_rejected():
    with pytest.raises(TypeError, match="entity_id"):
        RiskHistory(123)


def test_empty_entity_id_raises():
    with pytest.raises(ValueError, match="entity_id"):
        RiskHistory("")


def test_stability_band_bool_rejected():
    """bool is a subclass of int/float; must be rejected explicitly."""
    with pytest.raises(TypeError, match="stability_band"):
        RiskHistory("x", stability_band=True)


def test_stability_band_out_of_range_raises():
    with pytest.raises(ValueError, match="stability_band"):
        RiskHistory("x", stability_band=1.5)


def test_scores_empty_on_init():
    h = RiskHistory("x")
    assert h.scores == ()


def test_latest_none_when_empty():
    assert RiskHistory("x").latest is None


# ── record() ──────────────────────────────────────────────────────────────────

def test_record_float():
    h = RiskHistory("x")
    h.record(0.5)
    assert h.scores == (0.5,)


def test_record_risk_score_object():
    h = RiskHistory("x")
    rs = RiskScore(score=0.6, threshold=0.7, mode="strict", basis=[])
    h.record(rs)
    assert h.scores == (0.6,)


def test_record_multiple_preserves_order():
    h = RiskHistory("x")
    h.record(0.8)
    h.record(0.5)
    h.record(0.2)
    assert h.scores == (0.8, 0.5, 0.2)


def test_latest_returns_most_recent():
    h = RiskHistory("x")
    h.record(0.4)
    h.record(0.7)
    assert h.latest == 0.7


def test_record_bool_rejected():
    """bool is a subclass of int; must be rejected explicitly to preserve contract."""
    h = RiskHistory("x")
    with pytest.raises(TypeError, match="bool"):
        h.record(True)


def test_record_out_of_range_raises():
    h = RiskHistory("x")
    with pytest.raises(ValueError, match="score"):
        h.record(1.5)


# ── trajectory() ──────────────────────────────────────────────────────────────

def test_trajectory_raises_when_empty():
    with pytest.raises(ValueError, match="need >= 2"):
        RiskHistory("x").trajectory()


def test_trajectory_raises_with_single_entry():
    h = RiskHistory("x")
    h.record(0.5)
    with pytest.raises(ValueError, match="need >= 2"):
        h.trajectory()


def test_trajectory_improving():
    h = RiskHistory("x")
    h.record(0.8)
    h.record(0.3)
    assert h.trajectory() == TRAJECTORY_IMPROVING


def test_trajectory_degrading():
    h = RiskHistory("x")
    h.record(0.3)
    h.record(0.8)
    assert h.trajectory() == TRAJECTORY_DEGRADING


def test_trajectory_stable():
    h = RiskHistory("x")
    h.record(0.50)
    h.record(0.52)  # delta = 0.02, below default stability_band of 0.05
    assert h.trajectory() == TRAJECTORY_STABLE


def test_trajectory_stable_at_boundary():
    """delta == stability_band is classified as stable (condition is >, not >=)."""
    h = RiskHistory("x", stability_band=0.05)
    h.record(0.50)
    h.record(0.55)  # delta = 0.05 == stability_band → not > band → stable
    assert h.trajectory() == TRAJECTORY_STABLE


def test_trajectory_custom_stability_band():
    """A wider band makes a delta that would otherwise degrade classify as stable."""
    h = RiskHistory("x", stability_band=0.10)
    h.record(0.50)
    h.record(0.57)  # delta = 0.07 < 0.10 → stable
    assert h.trajectory() == TRAJECTORY_STABLE
