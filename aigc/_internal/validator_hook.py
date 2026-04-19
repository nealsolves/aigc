"""
ValidatorHook — typed governance hook contract for workflow steps.

Hooks are evaluated at enforce_step_pre_call() time after invocation-level
governance passes. A DENY or TIMEOUT result fails the step closed.
"""
from __future__ import annotations

import abc
import threading
import time
from dataclasses import dataclass
from typing import Any

# ---------------------------------------------------------------------------
# Decision constants
# ---------------------------------------------------------------------------

VALIDATOR_ALLOW = "allow"
VALIDATOR_DENY = "deny"
VALIDATOR_WARN = "warn"
VALIDATOR_REVIEW_REQUIRED = "review_required"
VALIDATOR_EXECUTION_FAILURE = "execution_failure"
VALIDATOR_TIMEOUT = "timeout"

_FAIL_CLOSED_DECISIONS = {VALIDATOR_DENY, VALIDATOR_TIMEOUT, VALIDATOR_REVIEW_REQUIRED}
_RETRY_ELIGIBLE_DECISIONS = {VALIDATOR_EXECUTION_FAILURE}

# ---------------------------------------------------------------------------
# Envelope and Result
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ValidatorHookEnvelope:
    """Versioned, session-bound input to a ValidatorHook.evaluate() call."""

    hook_schema_version: str  # "1.0"
    session_id: str
    step_id: str
    participant_id: str | None
    invocation: dict[str, Any]
    deadline_ms: int
    observed_at: int  # unix milliseconds
    policy_file: str | None = None
    invocation_checksum: str | None = None


@dataclass(frozen=True)
class ValidatorHookResult:
    """Typed, immutable result from a ValidatorHook.evaluate() call."""

    decision: str  # one of VALIDATOR_* constants
    reason_code: str | None
    explanation: str | None
    hook_id: str
    hook_version: str
    attempt: int
    latency_ms: int
    observed_at: int  # unix milliseconds
    stale_result: bool = False
    provenance: str | None = None


# ---------------------------------------------------------------------------
# Abstract base class
# ---------------------------------------------------------------------------


class ValidatorHook(abc.ABC):
    """Abstract base for custom workflow validator hooks.

    Subclass this, set hook_id and hook_version, implement evaluate().

    Timeout semantics: if evaluate() does not return within timeout_ms,
    _invoke_hook() returns a TIMEOUT result (fail-closed).

    Retry semantics: on EXECUTION_FAILURE, _invoke_hook() retries up to
    max_retries times. On DENY or TIMEOUT, no retry occurs.

    Class attributes:
        timeout_ms: Per-invocation timeout in milliseconds (class-level
            attribute, not instance).
        max_retries: Max retries on EXECUTION_FAILURE (class-level
            attribute, not instance).
        DENY and REVIEW_REQUIRED decisions are never retried automatically.

    Hook contract: evaluate() must not raise and must not mutate envelope.invocation.

    Thread lifetime warning: once timeout_ms elapses, _invoke_hook() returns a
    TIMEOUT result (fail-closed) and abandons the evaluate() thread. The thread
    continues running as a daemon until it returns naturally or the process exits.
    Implementations must be written to be safe under that condition — they may
    produce side effects or consume resources past the timeout window the caller
    observes.
    """

    hook_id: str
    hook_version: str
    timeout_ms: int = 5000
    max_retries: int = 0

    @abc.abstractmethod
    def evaluate(self, envelope: ValidatorHookEnvelope) -> ValidatorHookResult:
        """Evaluate the hook for a workflow step.

        Must return a ValidatorHookResult. Must not raise — return
        EXECUTION_FAILURE instead.
        """


# ---------------------------------------------------------------------------
# Hook runner with timeout and retry
# ---------------------------------------------------------------------------


def _call_hook_once(
    hook: ValidatorHook,
    envelope: ValidatorHookEnvelope,
    attempt: int,
) -> ValidatorHookResult:
    """Call hook.evaluate() in a daemon thread with timeout_ms enforcement."""
    result_holder: list[ValidatorHookResult] = []
    exception_holder: list[BaseException] = []

    def _run() -> None:
        try:
            result_holder.append(hook.evaluate(envelope))
        except BaseException as exc:  # noqa: BLE001
            exception_holder.append(exc)

    start_ms = int(time.time() * 1000)
    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    thread.join(timeout=hook.timeout_ms / 1000.0)
    elapsed_ms = int(time.time() * 1000) - start_ms

    if thread.is_alive():
        return ValidatorHookResult(
            decision=VALIDATOR_TIMEOUT,
            reason_code="HOOK_TIMEOUT",
            explanation=f"Hook {hook.hook_id!r} timed out after {hook.timeout_ms}ms",
            hook_id=hook.hook_id,
            hook_version=hook.hook_version,
            attempt=attempt,
            latency_ms=hook.timeout_ms,
            observed_at=int(time.time() * 1000),
        )

    if exception_holder:
        return ValidatorHookResult(
            decision=VALIDATOR_EXECUTION_FAILURE,
            reason_code="HOOK_EXCEPTION",
            explanation=str(exception_holder[0]),
            hook_id=hook.hook_id,
            hook_version=hook.hook_version,
            attempt=attempt,
            latency_ms=elapsed_ms,
            observed_at=int(time.time() * 1000),
        )

    result = result_holder[0]

    # Stale-result check: reject results that arrived after the deadline or
    # whose attempt number doesn't match the active attempt.
    _absolute_deadline = envelope.observed_at + envelope.deadline_ms
    if result.observed_at > _absolute_deadline or result.attempt != attempt:
        return ValidatorHookResult(
            decision=VALIDATOR_EXECUTION_FAILURE,
            reason_code="HOOK_STALE_RESULT",
            explanation=(
                f"Hook {hook.hook_id!r} returned a stale result "
                f"(observed_at={result.observed_at}, "
                f"deadline={_absolute_deadline}, attempt={result.attempt} vs {attempt})"
            ),
            hook_id=result.hook_id,
            hook_version=result.hook_version,
            attempt=attempt,
            latency_ms=elapsed_ms,
            observed_at=int(time.time() * 1000),
            stale_result=True,
        )

    _KNOWN_DECISIONS = {
        VALIDATOR_ALLOW,
        VALIDATOR_DENY,
        VALIDATOR_WARN,
        VALIDATOR_REVIEW_REQUIRED,
        VALIDATOR_EXECUTION_FAILURE,
        VALIDATOR_TIMEOUT,
    }
    if result.decision not in _KNOWN_DECISIONS:
        return ValidatorHookResult(
            decision=VALIDATOR_DENY,
            reason_code="HOOK_INVALID_DECISION",
            explanation=f"Unrecognized decision: {result.decision!r}",
            hook_id=result.hook_id,
            hook_version=result.hook_version,
            attempt=attempt,
            latency_ms=elapsed_ms,
            observed_at=int(time.time() * 1000),
        )

    return result


def _invoke_hook(
    hook: ValidatorHook,
    envelope: ValidatorHookEnvelope,
) -> ValidatorHookResult:
    """Invoke a hook with timeout and retry semantics.

    Retries up to hook.max_retries times on EXECUTION_FAILURE.
    Returns immediately on any other decision (ALLOW, DENY, WARN, TIMEOUT).
    """
    result = _call_hook_once(hook, envelope, attempt=1)
    for attempt in range(2, hook.max_retries + 2):
        if result.decision not in _RETRY_ELIGIBLE_DECISIONS:
            break
        result = _call_hook_once(hook, envelope, attempt=attempt)
    return result
