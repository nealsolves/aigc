"""
Internal implementation details. No compatibility guarantees.

All public symbols should be imported from the top-level ``aigc`` package.
Importing from ``aigc._internal`` is deprecated and will emit a
DeprecationWarning.
"""

import warnings as _warnings

_EXPORTS = {
    "enforce_invocation": "aigc._internal.enforcement",
    "with_retry": "aigc._internal.retry",
    "RetryExhaustedError": "aigc._internal.retry",
    "AIGCError": "aigc._internal.errors",
    "FeatureNotImplementedError": "aigc._internal.errors",
    "GovernanceViolationError": "aigc._internal.errors",
    "InvocationValidationError": "aigc._internal.errors",
    "PolicyLoadError": "aigc._internal.errors",
    "PolicyValidationError": "aigc._internal.errors",
    "PreconditionError": "aigc._internal.errors",
    "SchemaValidationError": "aigc._internal.errors",
}


def __getattr__(name: str):
    if name in _EXPORTS:
        _warnings.warn(
            f"Importing '{name}' from 'aigc._internal' is deprecated. "
            f"Use 'from aigc import {name}' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        import importlib
        mod = importlib.import_module(_EXPORTS[name])
        return getattr(mod, name)
    raise AttributeError(f"module 'aigc._internal' has no attribute {name}")
