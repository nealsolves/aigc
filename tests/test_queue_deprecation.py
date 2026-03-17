"""Tests for queue sink mode deprecation (M2-RR-05)."""
import warnings
import pytest

from aigc._internal.sinks import (
    set_sink_failure_mode,
    get_sink_failure_mode,
)


@pytest.fixture(autouse=True)
def _reset_sink_state():
    """Reset global sink state before and after each test."""
    original = get_sink_failure_mode()
    yield
    set_sink_failure_mode(original if original != "queue" else "log")


def test_queue_mode_emits_deprecation_warning():
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        set_sink_failure_mode("queue")
        assert len(w) == 1
        assert issubclass(w[0].category, DeprecationWarning)
        assert "deprecated" in str(w[0].message).lower()
        assert "queue" in str(w[0].message)


def test_queue_mode_falls_back_to_log():
    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        set_sink_failure_mode("queue")
    assert get_sink_failure_mode() == "log"


def test_raise_mode_still_works():
    set_sink_failure_mode("raise")
    assert get_sink_failure_mode() == "raise"


def test_log_mode_still_works():
    set_sink_failure_mode("log")
    assert get_sink_failure_mode() == "log"


def test_invalid_mode_rejected():
    with pytest.raises(ValueError, match="Invalid"):
        set_sink_failure_mode("invalid")
