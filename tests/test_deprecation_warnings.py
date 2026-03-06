"""Tests for internal import deprecation warnings (WS-14)."""

import importlib
import warnings

import pytest


def test_internal_package_import_emits_deprecation():
    """Importing from aigc._internal emits DeprecationWarning."""
    import aigc._internal as mod
    # Force __getattr__ by accessing attribute
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        func = mod.__getattr__("enforce_invocation")
        assert len(w) == 1
        assert issubclass(w[0].category, DeprecationWarning)
        assert "aigc._internal" in str(w[0].message)
        assert "from aigc import" in str(w[0].message)
        assert callable(func)


def test_public_import_no_deprecation():
    """Importing from aigc does NOT emit DeprecationWarning."""
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        from aigc import enforce_invocation  # noqa: F401
        deprecation_warnings = [
            x for x in w
            if issubclass(x.category, DeprecationWarning)
            and "aigc._internal" in str(x.message)
        ]
        assert len(deprecation_warnings) == 0


def test_internal_import_returns_correct_callable():
    """Deprecated import still returns the correct function."""
    import aigc._internal as mod
    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        func = mod.__getattr__("enforce_invocation")
    from aigc._internal.enforcement import enforce_invocation
    assert func is enforce_invocation


def test_internal_nonexistent_attribute_raises():
    """Accessing nonexistent attribute raises AttributeError."""
    import aigc._internal as mod
    with pytest.raises(AttributeError, match="no attribute"):
        mod.__getattr__("nonexistent_function")
