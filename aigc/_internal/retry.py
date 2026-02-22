"""
Retry policy enforcement wrapper.

Provides bounded, auditable retry behavior for transient failures.
Opt-in wrapper around enforce_invocation().
"""

from __future__ import annotations

import time
from typing import Any, Mapping, Callable

from aigc._internal.enforcement import enforce_invocation
from aigc._internal.errors import SchemaValidationError, AIGCError


class RetryExhaustedError(AIGCError):
    """Raised when all retry attempts fail."""

    def __init__(self, message: str, *, attempts: int, last_error: Exception):
        super().__init__(
            message,
            code="RETRY_EXHAUSTED",
            details={
                "attempts": attempts,
                "last_error": str(last_error),
                "last_error_type": type(last_error).__name__,
            },
        )
        self.last_error = last_error


def with_retry(
    invocation: Mapping[str, Any],
    *,
    enforcement_fn: Callable = enforce_invocation,
) -> dict[str, Any]:
    """
    Execute enforcement with retry policy from invocation's policy.

    :param invocation: Standard invocation dict
    :param enforcement_fn: Function to call (default: enforce_invocation)
    :return: Audit artifact from successful attempt
    :raises: RetryExhaustedError if all attempts fail

    Retry semantics:
    - Only retry on SchemaValidationError (transient output failures)
    - Do NOT retry PreconditionError, GovernanceViolationError (policy failures)
    - Each attempt generates separate audit artifact
    - Backoff: backoff_ms * attempt_number
    - max_retries=0 means single attempt (no retries)
    - max_retries=2 means up to 3 total attempts (1 initial + 2 retries)

    Usage:
        from aigc.retry import with_retry

        audit = with_retry(invocation)
    """
    # Load policy to check retry_policy
    from aigc._internal.policy_loader import load_policy

    policy = load_policy(invocation["policy_file"])

    retry_policy = policy.get("retry_policy")
    if not retry_policy:
        # No retry policy - single attempt
        return enforcement_fn(invocation)

    max_retries = retry_policy.get("max_retries", 0)
    backoff_ms = retry_policy.get("backoff_ms", 0)

    last_error: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            audit = enforcement_fn(invocation)
            # Success - return audit
            return audit

        except SchemaValidationError as exc:
            # Retryable error
            last_error = exc

            # Check if more retries available
            if attempt < max_retries:
                # Calculate backoff
                sleep_ms = backoff_ms * (attempt + 1)
                time.sleep(sleep_ms / 1000.0)
                # Retry loop continues
            else:
                # Out of retries
                raise RetryExhaustedError(
                    f"Retry exhausted after {attempt + 1} attempts",
                    attempts=attempt + 1,
                    last_error=exc,
                ) from exc

        except AIGCError:
            # Non-retryable governance error - fail immediately
            raise

    # Should never reach here, but satisfy type checker
    if last_error:  # pragma: no cover
        raise RetryExhaustedError(  # pragma: no cover
            f"Retry exhausted after {max_retries + 1} attempts",
            attempts=max_retries + 1,
            last_error=last_error,
        ) from last_error

    return enforcement_fn(invocation)  # pragma: no cover
