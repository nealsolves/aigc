"""
PR-08 ValidatorHook interface tests: contract shape, decision types, session integration.
"""
from __future__ import annotations
import time
import threading
import uuid
import pytest


# ---------------------------------------------------------------------------
# Import boundary — internal only in PR-08
# ---------------------------------------------------------------------------

def test_validator_hook_not_on_public_surface():
    """PR-08 keeps ValidatorHook internal. Freeze test asserts aigc.ValidatorHook must not exist."""
    import aigc
    assert not hasattr(aigc, "ValidatorHook"), (
        "ValidatorHook must not be exported to the public aigc surface until the "
        "planned-only designation is lifted and the freeze test is updated."
    )


def test_open_session_does_not_accept_validator_hooks():
    """open_session() must not accept validator_hooks — Fix 3: hook injection is not
    a public API surface in PR-08."""
    import inspect
    import aigc
    sig = inspect.signature(aigc.AIGC.open_session)
    assert "validator_hooks" not in sig.parameters, (
        "validator_hooks must not be a public open_session() parameter in PR-08"
    )


def test_validator_hook_importable_from_internal():
    """Internal module must be importable for use by the engine."""
    from aigc._internal.validator_hook import (
        ValidatorHook, ValidatorHookEnvelope, ValidatorHookResult,
        VALIDATOR_ALLOW, VALIDATOR_DENY,
    )
    assert ValidatorHook is not None


# ---------------------------------------------------------------------------
# ValidatorHookEnvelope structure
# ---------------------------------------------------------------------------

def test_envelope_is_immutable():
    from aigc._internal.validator_hook import ValidatorHookEnvelope
    env = ValidatorHookEnvelope(
        hook_schema_version="1.0",
        session_id="s-1",
        step_id="step-1",
        participant_id=None,
        invocation={"role": "planner"},
        deadline_ms=5000,
        observed_at=int(time.time() * 1000),
    )
    with pytest.raises((AttributeError, TypeError)):
        env.session_id = "s-2"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# ValidatorHookResult structure
# ---------------------------------------------------------------------------

def test_result_is_immutable():
    from aigc._internal.validator_hook import ValidatorHookResult, VALIDATOR_ALLOW
    result = ValidatorHookResult(
        decision=VALIDATOR_ALLOW,
        reason_code=None,
        explanation=None,
        hook_id="test-hook",
        hook_version="1.0",
        attempt=1,
        latency_ms=0,
        observed_at=int(time.time() * 1000),
    )
    with pytest.raises((AttributeError, TypeError)):
        result.decision = "deny"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Concrete ValidatorHook subclass
# ---------------------------------------------------------------------------

def test_concrete_hook_must_implement_evaluate():
    from aigc._internal.validator_hook import ValidatorHook
    with pytest.raises(TypeError):
        ValidatorHook()  # type: ignore[abstract]


def _make_allow_hook():
    from aigc._internal.validator_hook import ValidatorHook, ValidatorHookResult, VALIDATOR_ALLOW
    import time as _time

    class AllowHook(ValidatorHook):
        hook_id = "allow-hook"
        hook_version = "1.0"

        def evaluate(self, envelope):
            return ValidatorHookResult(
                decision=VALIDATOR_ALLOW,
                reason_code=None,
                explanation="Always allow",
                hook_id=self.hook_id,
                hook_version=self.hook_version,
                attempt=1,
                latency_ms=1,
                observed_at=int(_time.time() * 1000),
            )

    return AllowHook()


def _make_deny_hook():
    from aigc._internal.validator_hook import ValidatorHook, ValidatorHookResult, VALIDATOR_DENY
    import time as _time

    class DenyHook(ValidatorHook):
        hook_id = "deny-hook"
        hook_version = "1.0"

        def evaluate(self, envelope):
            return ValidatorHookResult(
                decision=VALIDATOR_DENY,
                reason_code="POLICY_VIOLATION",
                explanation="Deny always",
                hook_id=self.hook_id,
                hook_version=self.hook_version,
                attempt=1,
                latency_ms=1,
                observed_at=int(_time.time() * 1000),
            )

    return DenyHook()


def _make_timeout_hook(delay_s: float = 10.0):
    from aigc._internal.validator_hook import ValidatorHook, ValidatorHookResult, VALIDATOR_ALLOW
    import time as _time

    class SlowHook(ValidatorHook):
        hook_id = "slow-hook"
        hook_version = "1.0"
        timeout_ms = 100  # very short timeout

        def evaluate(self, envelope):
            _time.sleep(delay_s)  # exceeds timeout
            return ValidatorHookResult(
                decision=VALIDATOR_ALLOW,
                reason_code=None,
                explanation=None,
                hook_id=self.hook_id,
                hook_version=self.hook_version,
                attempt=1,
                latency_ms=0,
                observed_at=int(_time.time() * 1000),
            )

    return SlowHook()


def _make_flaky_hook(fail_times: int = 1):
    """Hook that returns EXECUTION_FAILURE `fail_times` before returning ALLOW."""
    from aigc._internal.validator_hook import (
        ValidatorHook, ValidatorHookResult, VALIDATOR_ALLOW, VALIDATOR_EXECUTION_FAILURE,
    )
    import time as _time

    class FlakyHook(ValidatorHook):
        hook_id = "flaky-hook"
        hook_version = "1.0"
        max_retries = 2

        def __init__(self):
            self._call_count = 0

        def evaluate(self, envelope):
            self._call_count += 1
            if self._call_count <= fail_times:
                return ValidatorHookResult(
                    decision=VALIDATOR_EXECUTION_FAILURE,
                    reason_code="TRANSIENT_ERROR",
                    explanation="Temporary failure",
                    hook_id=self.hook_id,
                    hook_version=self.hook_version,
                    attempt=self._call_count,
                    latency_ms=1,
                    observed_at=int(_time.time() * 1000),
                )
            return ValidatorHookResult(
                decision=VALIDATOR_ALLOW,
                reason_code=None,
                explanation=None,
                hook_id=self.hook_id,
                hook_version=self.hook_version,
                attempt=self._call_count,
                latency_ms=1,
                observed_at=int(_time.time() * 1000),
            )

    return FlakyHook()


# ---------------------------------------------------------------------------
# Hook runner: timeout and retry
# ---------------------------------------------------------------------------

def test_invoke_hook_allow_passes():
    from aigc._internal.validator_hook import _invoke_hook, VALIDATOR_ALLOW, ValidatorHookEnvelope
    import time as _time
    hook = _make_allow_hook()
    env = ValidatorHookEnvelope(
        hook_schema_version="1.0", session_id="s-1", step_id="step-1",
        participant_id=None, invocation={}, deadline_ms=5000,
        observed_at=int(_time.time() * 1000),
    )
    result = _invoke_hook(hook, env)
    assert result.decision == VALIDATOR_ALLOW


def test_invoke_hook_timeout_returns_timeout_decision():
    from aigc._internal.validator_hook import _invoke_hook, VALIDATOR_TIMEOUT, ValidatorHookEnvelope
    import time as _time
    hook = _make_timeout_hook(delay_s=5.0)  # hook waits 5s, timeout_ms=100
    env = ValidatorHookEnvelope(
        hook_schema_version="1.0", session_id="s-1", step_id="step-1",
        participant_id=None, invocation={}, deadline_ms=100,
        observed_at=int(_time.time() * 1000),
    )
    result = _invoke_hook(hook, env)
    assert result.decision == VALIDATOR_TIMEOUT


def test_invoke_hook_retries_on_execution_failure():
    from aigc._internal.validator_hook import _invoke_hook, VALIDATOR_ALLOW, ValidatorHookEnvelope
    import time as _time
    hook = _make_flaky_hook(fail_times=1)  # fails once, then allows; max_retries=2
    env = ValidatorHookEnvelope(
        hook_schema_version="1.0", session_id="s-1", step_id="step-1",
        participant_id=None, invocation={}, deadline_ms=5000,
        observed_at=int(_time.time() * 1000),
    )
    result = _invoke_hook(hook, env)
    assert result.decision == VALIDATOR_ALLOW
    assert hook._call_count == 2  # 1 failure + 1 success


def test_invoke_hook_exhausted_retries_returns_execution_failure():
    from aigc._internal.validator_hook import (
        _invoke_hook, VALIDATOR_EXECUTION_FAILURE, ValidatorHookEnvelope,
    )
    import time as _time
    hook = _make_flaky_hook(fail_times=10)  # always fails; max_retries=2 → 3 total attempts
    env = ValidatorHookEnvelope(
        hook_schema_version="1.0", session_id="s-1", step_id="step-1",
        participant_id=None, invocation={}, deadline_ms=5000,
        observed_at=int(_time.time() * 1000),
    )
    result = _invoke_hook(hook, env)
    assert result.decision == VALIDATOR_EXECUTION_FAILURE


# ---------------------------------------------------------------------------
# Session integration — hooks called at enforce_step_pre_call
# Fix 3: validator_hooks is NOT on the public open_session() API.
# These tests construct GovernanceSession directly via the internal path.
# ---------------------------------------------------------------------------

POLICY = "tests/golden_replays/golden_policy_v1.yaml"

_BASE_INV = {
    "policy_file": POLICY,
    "model_provider": "openai",
    "model_identifier": "gpt-4",
    "role": "planner",
    "input": {"query": "test"},
    "context": {"role_declared": True, "schema_exists": True},
}

_GOOD_OUTPUT = {"result": "answer", "confidence": 0.95}


def _make_session(aigc_instance, hooks):
    """Construct a GovernanceSession with hooks via the internal path."""
    from aigc._internal.session import GovernanceSession
    return GovernanceSession(
        aigc_instance,
        str(uuid.uuid4()),
        POLICY,
        None,
        hooks,
    )


def test_allow_hook_permits_step():
    """ALLOW hook must not block a step."""
    from aigc._internal.enforcement import AIGC
    a = AIGC()
    hook = _make_allow_hook()
    session = _make_session(a, [hook])
    with session:
        token = session.enforce_step_pre_call(dict(_BASE_INV))
        session.enforce_step_post_call(token, dict(_GOOD_OUTPUT))
        session.complete()
    assert session.workflow_artifact["status"] == "COMPLETED"


def test_deny_hook_raises_workflow_hook_denied():
    """DENY hook must raise WorkflowHookDeniedError (Fix 4: distinct from ApprovalRequired)."""
    from aigc._internal.enforcement import AIGC
    from aigc._internal.errors import WorkflowHookDeniedError
    a = AIGC()
    hook = _make_deny_hook()
    session = _make_session(a, [hook])
    with pytest.raises(WorkflowHookDeniedError) as exc_info:
        with session:
            session.enforce_step_pre_call(dict(_BASE_INV))
    assert exc_info.value.code == "WORKFLOW_HOOK_DENIED"


def test_timeout_hook_fails_closed():
    """TIMEOUT hook must fail closed (raise WorkflowHookDeniedError)."""
    from aigc._internal.enforcement import AIGC
    from aigc._internal.errors import WorkflowHookDeniedError
    a = AIGC()
    hook = _make_timeout_hook(delay_s=5.0)
    session = _make_session(a, [hook])
    with pytest.raises(WorkflowHookDeniedError):
        with session:
            session.enforce_step_pre_call(dict(_BASE_INV))


def test_warn_hook_does_not_block_step():
    """WARN hook must log but allow the step to proceed."""
    from aigc._internal.enforcement import AIGC
    from aigc._internal.validator_hook import (
        ValidatorHook, ValidatorHookResult, VALIDATOR_WARN,
    )
    import time as _time

    class WarnHook(ValidatorHook):
        hook_id = "warn-hook"
        hook_version = "1.0"

        def evaluate(self, envelope):
            return ValidatorHookResult(
                decision=VALIDATOR_WARN,
                reason_code="LOW_CONFIDENCE",
                explanation="Confidence is low",
                hook_id=self.hook_id,
                hook_version=self.hook_version,
                attempt=1,
                latency_ms=1,
                observed_at=int(_time.time() * 1000),
            )

    a = AIGC()
    session = _make_session(a, [WarnHook()])
    with session:
        token = session.enforce_step_pre_call(dict(_BASE_INV))
        session.enforce_step_post_call(token, dict(_GOOD_OUTPUT))
        session.complete()
    assert session.workflow_artifact["status"] == "COMPLETED"


def test_hook_evidence_recorded_in_workflow_artifact():
    """Hook results must appear in workflow artifact validator_hook_evidence."""
    from aigc._internal.enforcement import AIGC
    a = AIGC()
    hook = _make_allow_hook()
    session = _make_session(a, [hook])
    with session:
        token = session.enforce_step_pre_call(dict(_BASE_INV), step_id="step-x")
        session.enforce_step_post_call(token, dict(_GOOD_OUTPUT))
        session.complete()

    artifact = session.workflow_artifact
    evidence = artifact.get("validator_hook_evidence", [])
    assert len(evidence) == 1
    rec = evidence[0]
    assert rec["hook_id"] == "allow-hook"
    assert rec["step_id"] == "step-x"
    assert rec["decision"] == "allow"


def test_flaky_hook_with_sufficient_retries_succeeds():
    """Hook that fails once with max_retries=2 must succeed on retry."""
    from aigc._internal.enforcement import AIGC
    a = AIGC()
    hook = _make_flaky_hook(fail_times=1)  # fails once, then allows; max_retries=2
    session = _make_session(a, [hook])
    with session:
        token = session.enforce_step_pre_call(dict(_BASE_INV))
        session.enforce_step_post_call(token, dict(_GOOD_OUTPUT))
        session.complete()
    assert session.workflow_artifact["status"] == "COMPLETED"


# ---------------------------------------------------------------------------
# Fail-closed: unknown decision normalization (Bug 2 fix)
# ---------------------------------------------------------------------------

def test_unknown_decision_normalized_to_execution_failure():
    """_call_hook_once must normalize an unrecognized decision to EXECUTION_FAILURE."""
    from aigc._internal.validator_hook import (
        ValidatorHook, ValidatorHookResult, ValidatorHookEnvelope,
        _call_hook_once,
        VALIDATOR_EXECUTION_FAILURE,
    )
    import time as _time

    class BananaHook(ValidatorHook):
        hook_id = "banana-hook"
        hook_version = "1.0"

        def evaluate(self, envelope):
            return ValidatorHookResult(
                decision="banana",
                reason_code="UNKNOWN",
                explanation="returning a nonsense decision",
                hook_id=self.hook_id,
                hook_version=self.hook_version,
                attempt=1,
                latency_ms=1,
                observed_at=int(_time.time() * 1000),
            )

    hook = BananaHook()
    env = ValidatorHookEnvelope(
        hook_schema_version="1.0",
        session_id="s-1",
        step_id="step-1",
        participant_id=None,
        invocation={},
        deadline_ms=5000,
        observed_at=int(_time.time() * 1000),
    )
    result = _call_hook_once(hook, env, attempt=1)
    assert result.decision == VALIDATOR_EXECUTION_FAILURE
    assert result.reason_code == "HOOK_INVALID_DECISION"


def test_unknown_decision_in_session_logs_warning_and_allows():
    """Unknown decision (normalized to EXECUTION_FAILURE) must not block step — takes warning path."""
    from aigc._internal.enforcement import AIGC
    from aigc._internal.validator_hook import (
        ValidatorHook, ValidatorHookResult, VALIDATOR_EXECUTION_FAILURE,
    )
    import time as _time

    class BananaHookNoRetry(ValidatorHook):
        hook_id = "banana-no-retry-hook"
        hook_version = "1.0"
        max_retries = 0  # EXECUTION_FAILURE returned immediately, no retry

        def evaluate(self, envelope):
            return ValidatorHookResult(
                decision="banana",
                reason_code="UNKNOWN",
                explanation="returning a nonsense decision",
                hook_id=self.hook_id,
                hook_version=self.hook_version,
                attempt=1,
                latency_ms=1,
                observed_at=int(_time.time() * 1000),
            )

    a = AIGC()
    session = _make_session(a, [BananaHookNoRetry()])
    # Must not raise — EXECUTION_FAILURE takes the warning path, not the deny path
    with session:
        token = session.enforce_step_pre_call(dict(_BASE_INV))
        session.enforce_step_post_call(token, dict(_GOOD_OUTPUT))
        session.complete()
    assert session.workflow_artifact["status"] == "COMPLETED"
