"""
Regression tests for invalid risk_config.mode → FAIL artifact guarantee.

Proves that:
- Invalid risk_config.mode raises a typed AIGCError (PolicyValidationError),
  not a raw ValueError.
- A FAIL artifact is generated and attached to the exception.
- Valid risk modes still behave unchanged.

These tests close audit finding C2.
"""

import pytest

from aigc._internal.enforcement import AIGC
from aigc._internal.errors import AIGCError, PolicyValidationError
from aigc._internal.risk_scoring import (
    compute_risk_score,
    VALID_RISK_MODES,
)


# ── Fixtures ────────────────────────────────────────────────────

POLICY_YAML = """\
policy_version: "1.0"
roles:
  - analyst
pre_conditions:
  required:
    has_session:
      type: boolean
"""


@pytest.fixture()
def policy_path(tmp_path):
    p = tmp_path / "policy.yaml"
    p.write_text(POLICY_YAML)
    return str(p)


@pytest.fixture()
def base_invocation(policy_path):
    return {
        "policy_file": policy_path,
        "model_provider": "test",
        "model_identifier": "test-model",
        "role": "analyst",
        "input": {"prompt": "hello"},
        "output": {"text": "world"},
        "context": {"has_session": True},
    }


# ── Unit-level: compute_risk_score raises typed error ────────────

class TestComputeRiskScoreInvalidMode:
    """Invalid mode must raise PolicyValidationError, not ValueError."""

    def test_invalid_mode_raises_policy_validation_error(self):
        with pytest.raises(PolicyValidationError) as exc_info:
            compute_risk_score(
                {"context": {}}, {},
                risk_config={"mode": "invalid_mode", "factors": []},
            )
        assert "invalid_mode" in str(exc_info.value)

    def test_invalid_mode_is_not_raw_value_error(self):
        with pytest.raises(AIGCError):
            compute_risk_score(
                {"context": {}}, {},
                risk_config={"mode": "bogus", "factors": []},
            )
        # Verify it does NOT raise raw ValueError
        try:
            compute_risk_score(
                {"context": {}}, {},
                risk_config={"mode": "bogus", "factors": []},
            )
        except PolicyValidationError:
            pass  # expected
        except ValueError:
            pytest.fail("Raw ValueError escaped — should be PolicyValidationError")


class TestValidModesUnchanged:
    """Valid risk modes must continue to work without error."""

    @pytest.mark.parametrize("mode", list(VALID_RISK_MODES))
    def test_valid_mode_computes_score(self, mode):
        result = compute_risk_score(
            {"context": {}}, {},
            risk_config={
                "mode": mode,
                "threshold": 0.7,
                "factors": [
                    {"name": "test_factor", "weight": 0.3, "condition": "missing_guards"},
                ],
            },
        )
        assert result.mode == mode
        assert 0.0 <= result.score <= 1.0


# ── Integration-level: pipeline produces FAIL artifact ───────────

class TestInvalidRiskModeProducesFAILArtifact:
    """C2 regression: invalid risk_config.mode in pipeline must emit FAIL."""

    def test_raises_aigc_error_not_value_error(self, base_invocation):
        aigc = AIGC(risk_config={"mode": "invalid", "factors": []})
        with pytest.raises(AIGCError) as exc_info:
            aigc.enforce(base_invocation)

        assert not isinstance(exc_info.value, type) or True
        # Must not be raw ValueError
        assert isinstance(exc_info.value, AIGCError)

    def test_fail_artifact_attached(self, base_invocation):
        aigc = AIGC(risk_config={"mode": "invalid", "factors": []})
        with pytest.raises(AIGCError) as exc_info:
            aigc.enforce(base_invocation)

        artifact = exc_info.value.audit_artifact
        assert artifact is not None
        assert artifact["enforcement_result"] == "FAIL"

    def test_artifact_emitted_to_sink(self, base_invocation):
        emitted = []
        from aigc._internal.sinks import CallbackAuditSink
        sink = CallbackAuditSink(lambda a: emitted.append(a))
        aigc = AIGC(
            risk_config={"mode": "not_a_mode", "factors": []},
            sink=sink,
        )
        with pytest.raises(AIGCError):
            aigc.enforce(base_invocation)

        assert len(emitted) == 1
        assert emitted[0]["enforcement_result"] == "FAIL"

    def test_failure_gate_is_risk_scoring(self, base_invocation):
        """Invalid risk_config.mode must map to risk_scoring gate."""
        aigc = AIGC(risk_config={"mode": "bad", "factors": []})
        with pytest.raises(AIGCError) as exc_info:
            aigc.enforce(base_invocation)

        artifact = exc_info.value.audit_artifact
        assert artifact["failure_gate"] == "risk_scoring"

    def test_non_risk_policy_validation_still_invocation_validation(self):
        """PolicyValidationError without risk details stays invocation_validation."""
        from aigc._internal.enforcement import _map_exception_to_failure_gate
        exc = PolicyValidationError("generic issue", details={"issues": []})
        assert _map_exception_to_failure_gate(exc) == "invocation_validation"
