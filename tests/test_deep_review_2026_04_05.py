"""Regression tests for AIGC deep review findings (2026-04-05).

Each finding maps to one test class.

F-01 — Split pre-call crashes on YAML-native non-JSON policy values
F-02 — Validation/canonicalization mismatch: NaN and mixed key types
F-03 — Split decorator emits no artifact when wrapped function raises
        after Phase A PASS
"""
from __future__ import annotations

import pytest

from aigc._internal.enforcement import (
    AIGC,
    enforce_invocation,
    enforce_post_call,
    enforce_pre_call,
    enforce_pre_call_async,
)
from aigc._internal.errors import InvocationValidationError
from aigc._internal.sinks import (
    CallbackAuditSink,
    get_audit_sink,
    set_audit_sink,
)
from aigc._internal.decorators import governed


# ── Helpers ────────────────────────────────────────────────────────────────────

GOLDEN_POLICY = "tests/golden_replays/golden_policy_v1.yaml"


def _pre_call_inv(**overrides):
    inv = {
        "policy_file": GOLDEN_POLICY,
        "model_provider": "anthropic",
        "model_identifier": "claude-sonnet-4-5-20250929",
        "role": "planner",
        "input": {"query": "test"},
        "context": {"role_declared": True, "schema_exists": True},
    }
    inv.update(overrides)
    return inv


def _full_inv(output, **overrides):
    inv = _pre_call_inv(**overrides)
    inv["output"] = output
    return inv


# ── F-01: Split pre-call crashes on non-JSON policy values ────────────────────


class TestF01PolicyFreezeCrash:
    """F-01: YAML-native date in output_schema must not produce a raw
    TypeError.  All four split pre-call entry points must produce a
    typed InvocationValidationError with an attached FAIL artifact.
    """

    @pytest.fixture()
    def date_policy_file(self, tmp_path):
        """Policy whose output_schema carries a YAML-native date value."""
        p = tmp_path / "date_policy.yaml"
        p.write_text(
            "policy_version: '1.0'\n"
            "roles:\n"
            "  - planner\n"
            "pre_conditions:\n"
            "  required:\n"
            "    role_declared:\n"
            "      type: boolean\n"
            "output_schema:\n"
            "  type: object\n"
            "  properties:\n"
            "    release_date:\n"
            "      const: 2026-01-01\n"  # parsed by yaml.safe_load as date
        )
        return str(p)

    def test_module_sync_raises_typed_error(self, date_policy_file):
        """enforce_pre_call raises InvocationValidationError, not TypeError."""
        inv = _pre_call_inv(policy_file=date_policy_file)
        with pytest.raises(InvocationValidationError) as exc_info:
            enforce_pre_call(inv)

        assert "non-json-serializable" in str(exc_info.value).lower()

    def test_module_sync_attaches_artifact(self, date_policy_file):
        """enforce_pre_call attaches a FAIL artifact to the exception."""
        inv = _pre_call_inv(policy_file=date_policy_file)
        with pytest.raises(InvocationValidationError) as exc_info:
            enforce_pre_call(inv)

        artifact = exc_info.value.audit_artifact
        assert artifact is not None
        assert artifact["enforcement_result"] == "FAIL"
        assert artifact["metadata"]["enforcement_mode"] == "split_pre_call_only"

    @pytest.mark.asyncio
    async def test_module_async_raises_typed_error(self, date_policy_file):
        """enforce_pre_call_async raises InvocationValidationError."""
        inv = _pre_call_inv(policy_file=date_policy_file)
        with pytest.raises(InvocationValidationError) as exc_info:
            await enforce_pre_call_async(inv)

        assert "non-json-serializable" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_module_async_attaches_artifact(self, date_policy_file):
        """enforce_pre_call_async attaches a FAIL artifact."""
        inv = _pre_call_inv(policy_file=date_policy_file)
        with pytest.raises(InvocationValidationError) as exc_info:
            await enforce_pre_call_async(inv)

        artifact = exc_info.value.audit_artifact
        assert artifact is not None
        assert artifact["enforcement_result"] == "FAIL"

    def test_aigc_sync_raises_typed_error(self, date_policy_file):
        """AIGC.enforce_pre_call raises InvocationValidationError."""
        engine = AIGC()
        inv = _pre_call_inv(policy_file=date_policy_file)
        with pytest.raises(InvocationValidationError) as exc_info:
            engine.enforce_pre_call(inv)

        assert "non-json-serializable" in str(exc_info.value).lower()

    def test_aigc_sync_attaches_artifact(self, date_policy_file):
        """AIGC.enforce_pre_call attaches a FAIL artifact."""
        engine = AIGC()
        inv = _pre_call_inv(policy_file=date_policy_file)
        with pytest.raises(InvocationValidationError) as exc_info:
            engine.enforce_pre_call(inv)

        artifact = exc_info.value.audit_artifact
        assert artifact is not None
        assert artifact["enforcement_result"] == "FAIL"
        assert artifact["metadata"]["enforcement_mode"] == "split_pre_call_only"

    @pytest.mark.asyncio
    async def test_aigc_async_raises_typed_error(self, date_policy_file):
        """AIGC.enforce_pre_call_async raises InvocationValidationError."""
        engine = AIGC()
        inv = _pre_call_inv(policy_file=date_policy_file)
        with pytest.raises(InvocationValidationError) as exc_info:
            await engine.enforce_pre_call_async(inv)

        assert "non-json-serializable" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_aigc_async_attaches_artifact(self, date_policy_file):
        """AIGC.enforce_pre_call_async attaches a FAIL artifact."""
        engine = AIGC()
        inv = _pre_call_inv(policy_file=date_policy_file)
        with pytest.raises(InvocationValidationError) as exc_info:
            await engine.enforce_pre_call_async(inv)

        artifact = exc_info.value.audit_artifact
        assert artifact is not None
        assert artifact["enforcement_result"] == "FAIL"


# ── F-02: Validation/canonicalization mismatch ────────────────────────────────


class TestF02ValidationCanonicalizationMismatch:
    """F-02: NaN, Infinity, and mixed-key-type dicts must be rejected by
    invocation validation with a typed InvocationValidationError + artifact,
    not crash later in checksum canonicalization with a raw ValueError/TypeError.

    Tests cover: unified path (enforce_invocation), split post-call path
    (enforce_post_call), and input/context validation.
    """

    # ── output path — NaN ──────────────────────────────────────────────────────

    def test_unified_nan_output_raises_typed_error(self):
        """enforce_invocation rejects NaN in output as InvocationValidationError."""
        inv = _full_inv({"x": float("nan")})
        with pytest.raises(InvocationValidationError) as exc_info:
            enforce_invocation(inv)
        assert exc_info.value.audit_artifact is not None

    def test_split_post_call_nan_output_raises_typed_error(self):
        """enforce_post_call rejects NaN in output."""
        pre = enforce_pre_call(_pre_call_inv())
        with pytest.raises(InvocationValidationError) as exc_info:
            enforce_post_call(pre, {"x": float("nan")})
        assert exc_info.value.audit_artifact is not None

    # ── output path — Infinity ─────────────────────────────────────────────────

    def test_unified_infinity_output_raises_typed_error(self):
        """enforce_invocation rejects Infinity in output."""
        inv = _full_inv({"x": float("inf")})
        with pytest.raises(InvocationValidationError) as exc_info:
            enforce_invocation(inv)
        assert exc_info.value.audit_artifact is not None

    def test_split_post_call_infinity_output_raises_typed_error(self):
        """enforce_post_call rejects Infinity in output."""
        pre = enforce_pre_call(_pre_call_inv())
        with pytest.raises(InvocationValidationError) as exc_info:
            enforce_post_call(pre, {"x": float("inf")})
        assert exc_info.value.audit_artifact is not None

    # ── output path — mixed key types ─────────────────────────────────────────

    def test_unified_mixed_key_types_raises_typed_error(self):
        """enforce_invocation rejects mixed int/str key types in output."""
        inv = _full_inv({1: "one", "2": "two"})
        with pytest.raises(InvocationValidationError) as exc_info:
            enforce_invocation(inv)
        assert exc_info.value.audit_artifact is not None

    def test_split_post_call_mixed_key_types_raises_typed_error(self):
        """enforce_post_call rejects mixed int/str key types in output."""
        pre = enforce_pre_call(_pre_call_inv())
        with pytest.raises(InvocationValidationError) as exc_info:
            enforce_post_call(pre, {1: "one", "2": "two"})
        assert exc_info.value.audit_artifact is not None

    # ── input/context paths — NaN ──────────────────────────────────────────────

    def test_unified_nan_in_input_raises_typed_error(self):
        """enforce_invocation rejects NaN in input field."""
        inv = _full_inv(
            {"result": "ok", "confidence": 0.9},
            input={"query": float("nan")},
        )
        with pytest.raises(InvocationValidationError):
            enforce_invocation(inv)

    def test_unified_nan_in_context_raises_typed_error(self):
        """enforce_invocation rejects NaN in context field."""
        inv = _full_inv(
            {"result": "ok", "confidence": 0.9},
            context={"role_declared": True, "schema_exists": True,
                     "score": float("nan")},
        )
        with pytest.raises(InvocationValidationError):
            enforce_invocation(inv)

    # ── AIGC instance paths ────────────────────────────────────────────────────

    def test_aigc_nan_output_raises_typed_error(self):
        """AIGC.enforce raises InvocationValidationError for NaN in output."""
        engine = AIGC()
        inv = _full_inv({"x": float("nan")})
        with pytest.raises(InvocationValidationError) as exc_info:
            engine.enforce(inv)
        assert exc_info.value.audit_artifact is not None

    def test_aigc_split_post_call_nan_output_raises_typed_error(self):
        """AIGC split post-call rejects NaN in output."""
        engine = AIGC()
        pre = engine.enforce_pre_call(_pre_call_inv())
        with pytest.raises(InvocationValidationError) as exc_info:
            engine.enforce_post_call(pre, {"x": float("nan")})
        assert exc_info.value.audit_artifact is not None


# ── F-03: Decorator emits no artifact when wrapped function raises ─────────────


class TestF03DecoratorFunctionFailureArtifact:
    """F-03: @governed(pre_call_enforcement=True) must emit a FAIL artifact
    to the configured sink when the wrapped function raises after Phase A PASS,
    before re-propagating the original exception unchanged.
    """

    POLICY = GOLDEN_POLICY
    VALID_INPUT = {"task": "analyse system"}
    VALID_CONTEXT = {"role_declared": True, "schema_exists": True}

    def test_sync_decorator_emits_artifact_on_fn_raise(self):
        """Sync wrapped function raise → FAIL artifact emitted, original exception propagated."""
        collected: list[dict] = []
        sink = CallbackAuditSink(lambda a: collected.append(a))

        @governed(
            policy_file=self.POLICY,
            role="planner",
            model_provider="anthropic",
            model_identifier="claude-sonnet-4-5-20250929",
            pre_call_enforcement=True,
        )
        def raising_fn(input_data, context):
            raise RuntimeError("simulated LLM failure")

        old_sink = get_audit_sink()
        set_audit_sink(sink)
        try:
            with pytest.raises(RuntimeError, match="simulated LLM failure"):
                raising_fn(self.VALID_INPUT, self.VALID_CONTEXT)
        finally:
            set_audit_sink(old_sink)

        assert len(collected) == 1, (
            f"Expected 1 artifact from wrapped function failure, got {len(collected)}"
        )
        artifact = collected[0]
        assert artifact["enforcement_result"] == "FAIL"
        assert artifact["failure_gate"] == "wrapped_function_error"
        assert artifact["metadata"]["enforcement_mode"] == "split"

    def test_sync_decorator_original_exception_propagates_unchanged(self):
        """Original exception type and message are preserved after artifact emission."""
        old_sink = get_audit_sink()
        set_audit_sink(CallbackAuditSink(lambda _: None))
        try:
            @governed(
                policy_file=self.POLICY,
                role="planner",
                model_provider="anthropic",
                model_identifier="claude-sonnet-4-5-20250929",
                pre_call_enforcement=True,
            )
            def raising_fn(input_data, context):
                raise ValueError("specific error value")

            with pytest.raises(ValueError, match="specific error value"):
                raising_fn(self.VALID_INPUT, self.VALID_CONTEXT)
        finally:
            set_audit_sink(old_sink)

    @pytest.mark.asyncio
    async def test_async_decorator_emits_artifact_on_fn_raise(self):
        """Async wrapped function raise → FAIL artifact emitted."""
        collected: list[dict] = []
        old_sink = get_audit_sink()
        set_audit_sink(CallbackAuditSink(lambda a: collected.append(a)))
        try:
            @governed(
                policy_file=self.POLICY,
                role="planner",
                model_provider="anthropic",
                model_identifier="claude-sonnet-4-5-20250929",
                pre_call_enforcement=True,
            )
            async def raising_async_fn(input_data, context):
                raise RuntimeError("async LLM failure")

            with pytest.raises(RuntimeError, match="async LLM failure"):
                await raising_async_fn(self.VALID_INPUT, self.VALID_CONTEXT)
        finally:
            set_audit_sink(old_sink)

        assert len(collected) == 1
        artifact = collected[0]
        assert artifact["enforcement_result"] == "FAIL"
        assert artifact["failure_gate"] == "wrapped_function_error"

    @pytest.mark.asyncio
    async def test_async_decorator_original_exception_propagates(self):
        """Async: original exception type preserved after artifact emission."""
        old_sink = get_audit_sink()
        set_audit_sink(CallbackAuditSink(lambda _: None))
        try:
            @governed(
                policy_file=self.POLICY,
                role="planner",
                model_provider="anthropic",
                model_identifier="claude-sonnet-4-5-20250929",
                pre_call_enforcement=True,
            )
            async def raising_async_fn(input_data, context):
                raise KeyError("missing key")

            with pytest.raises(KeyError, match="missing key"):
                await raising_async_fn(self.VALID_INPUT, self.VALID_CONTEXT)
        finally:
            set_audit_sink(old_sink)

    def test_phase_a_fail_still_raises_no_fn_call(self):
        """Phase A fail is unaffected: function not called, original Phase A error raised."""
        call_count = [0]

        @governed(
            policy_file=self.POLICY,
            role="unauthorized_role",
            model_provider="anthropic",
            model_identifier="claude-sonnet-4-5-20250929",
            pre_call_enforcement=True,
        )
        def fn(input_data, context):
            call_count[0] += 1
            raise RuntimeError("should never reach here")

        from aigc._internal.errors import GovernanceViolationError
        with pytest.raises(GovernanceViolationError):
            fn(self.VALID_INPUT, self.VALID_CONTEXT)

        assert call_count[0] == 0
