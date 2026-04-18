"""
PR-08 engine hardening tests: schema, state-machine, composition.
"""
from __future__ import annotations
import json
import yaml
import jsonschema
import pytest
from pathlib import Path

SCHEMA_PATH = Path("aigc/schemas/policy_dsl.schema.json")


def _load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text())


# ---------------------------------------------------------------------------
# Schema tests: workflow block
# ---------------------------------------------------------------------------

def test_workflow_max_steps_accepted_by_schema():
    schema = _load_schema()
    policy = {
        "policy_version": "1.0",
        "roles": ["planner"],
        "workflow": {"max_steps": 3},
    }
    jsonschema.validate(policy, schema)  # must not raise


def test_workflow_max_total_tool_calls_accepted_by_schema():
    schema = _load_schema()
    policy = {
        "policy_version": "1.0",
        "roles": ["planner"],
        "workflow": {"max_total_tool_calls": 10},
    }
    jsonschema.validate(policy, schema)


def test_workflow_max_steps_must_be_positive_integer():
    schema = _load_schema()
    policy = {
        "policy_version": "1.0",
        "roles": ["planner"],
        "workflow": {"max_steps": 0},
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(policy, schema)


def test_workflow_unknown_field_rejected():
    schema = _load_schema()
    policy = {
        "policy_version": "1.0",
        "roles": ["planner"],
        "workflow": {"unknown_field": True},
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(policy, schema)


# ---------------------------------------------------------------------------
# Composition hardening: workflow-bearing fields must only narrow
# ---------------------------------------------------------------------------

from aigc._internal.policy_loader import load_policy
from aigc._internal.errors import PolicyValidationError


def test_valid_composition_child_narrows_and_loads():
    """Child policy that narrows roles and tightens budgets must load cleanly."""
    policy = load_policy("tests/test_policies/workflow_composition_child_valid.yaml")
    assert "planner" in policy["roles"]
    assert "reviewer" not in policy["roles"]
    assert policy["workflow"]["max_steps"] == 3


def test_widening_roles_raises_policy_validation_error():
    """Child policy that adds a role not in base must raise PolicyValidationError."""
    with pytest.raises(PolicyValidationError, match="escalation"):
        load_policy("tests/test_policies/workflow_composition_child_widening.yaml")


def test_child_cannot_widen_max_steps():
    """Child policy that increases max_steps beyond base must raise PolicyValidationError."""
    import tempfile
    import textwrap

    with tempfile.TemporaryDirectory() as tmpdir:
        base_path = Path(tmpdir) / "base.yaml"
        child_path = Path(tmpdir) / "child.yaml"

        base_path.write_text(textwrap.dedent("""
            policy_version: "1.0"
            roles: [planner]
            pre_conditions:
              required:
                role_declared:
                  type: boolean
                schema_exists:
                  type: boolean
            post_conditions:
              required: [result]
            workflow:
              max_steps: 3
        """))

        child_path.write_text(textwrap.dedent("""
            extends: base.yaml
            policy_version: "1.0"
            roles: [planner]
            workflow:
              max_steps: 10
        """))

        with pytest.raises(PolicyValidationError, match="max_steps"):
            load_policy(str(child_path))


def test_child_cannot_widen_max_total_tool_calls():
    """Child policy that increases max_total_tool_calls beyond base must raise."""
    import tempfile
    import textwrap

    with tempfile.TemporaryDirectory() as tmpdir:
        base_path = Path(tmpdir) / "base.yaml"
        child_path = Path(tmpdir) / "child.yaml"

        base_path.write_text(textwrap.dedent("""
            policy_version: "1.0"
            roles: [planner]
            pre_conditions:
              required:
                role_declared:
                  type: boolean
                schema_exists:
                  type: boolean
            post_conditions:
              required: [result]
            workflow:
              max_total_tool_calls: 10
        """))

        child_path.write_text(textwrap.dedent("""
            extends: base.yaml
            policy_version: "1.0"
            roles: [planner]
            workflow:
              max_total_tool_calls: 99
        """))

        with pytest.raises(PolicyValidationError, match="max_total_tool_calls"):
            load_policy(str(child_path))


def test_child_can_tighten_max_steps():
    """Child policy that decreases max_steps below base must succeed."""
    import tempfile
    import textwrap

    with tempfile.TemporaryDirectory() as tmpdir:
        base_path = Path(tmpdir) / "base.yaml"
        child_path = Path(tmpdir) / "child.yaml"

        base_path.write_text(textwrap.dedent("""
            policy_version: "1.0"
            roles: [planner]
            pre_conditions:
              required:
                role_declared:
                  type: boolean
                schema_exists:
                  type: boolean
            post_conditions:
              required: [result]
            workflow:
              max_steps: 10
        """))

        child_path.write_text(textwrap.dedent("""
            extends: base.yaml
            policy_version: "1.0"
            roles: [planner]
            workflow:
              max_steps: 3
        """))

        policy = load_policy(str(child_path))
        assert policy["workflow"]["max_steps"] == 3


# ---------------------------------------------------------------------------
# State-machine tests
# ---------------------------------------------------------------------------

from aigc._internal.enforcement import AIGC
from aigc._internal.session import STATE_FAILED, STATE_FINALIZED
from aigc._internal.errors import (
    SessionStateError,
    WorkflowStepBudgetExceededError,
)

BUDGET_POLICY = "tests/test_policies/workflow_budget_policy.yaml"

_BASE_INV = {
    "policy_file": BUDGET_POLICY,
    "model_provider": "openai",
    "model_identifier": "gpt-4",
    "role": "planner",
    "input": {"query": "test"},
    "context": {"role_declared": True, "schema_exists": True},
}

_GOOD_OUTPUT = {"result": "answer"}


def test_invalid_transition_raises_session_state_error():
    """Invalid transition (COMPLETED → PAUSED) raises SessionStateError."""
    a = AIGC()
    session = a.open_session()
    session.complete()
    with pytest.raises(SessionStateError) as exc_info:
        session.pause()
    assert exc_info.value.code == "WORKFLOW_INVALID_TRANSITION"


def test_budget_exceeded_during_context_manager_produces_failed_artifact():
    """Exceeding max_steps inside a with block must emit a FAILED artifact."""
    a = AIGC()
    with pytest.raises(WorkflowStepBudgetExceededError):
        with a.open_session(policy_file=BUDGET_POLICY) as session:
            for _ in range(2):
                token = session.enforce_step_pre_call(dict(_BASE_INV))
                session.enforce_step_post_call(token, dict(_GOOD_OUTPUT))
            session.enforce_step_pre_call(dict(_BASE_INV))  # raises

    assert session.state == STATE_FINALIZED
    artifact = session.workflow_artifact
    assert artifact["status"] == "FAILED"
    assert artifact["failure_summary"] is not None
    assert "WorkflowStepBudgetExceededError" in artifact["failure_summary"]["exception_type"]


def test_finalized_session_rejects_new_steps():
    """Finalized session must reject enforce_step_pre_call."""
    a = AIGC()
    session = a.open_session()
    session.complete()
    session.finalize()
    assert session.state == STATE_FINALIZED
    with pytest.raises(SessionStateError):
        session.enforce_step_pre_call(dict(_BASE_INV))


def test_approval_checkpoint_cycle_reaches_completed():
    """Full pause → resume → complete cycle must produce COMPLETED artifact."""
    a = AIGC()
    POLICY = "tests/golden_replays/golden_policy_v1.yaml"
    inv = {
        "policy_file": POLICY,
        "model_provider": "openai",
        "model_identifier": "gpt-4",
        "role": "planner",
        "input": {"query": "test"},
        "context": {"role_declared": True, "schema_exists": True},
    }
    good_out = {"result": "answer", "confidence": 0.95}

    with a.open_session() as session:
        token = session.enforce_step_pre_call(dict(inv), step_id="step-1")
        session.pause(approval_id="chk-1", reason="Review required")
        session.enforce_step_post_call(token, dict(good_out))
        session.resume(approval_id="chk-1", approval_note="Approved")
        session.complete()

    artifact = session.workflow_artifact
    assert artifact["status"] == "COMPLETED"
    assert len(artifact["approval_checkpoints"]) == 1
    assert artifact["approval_checkpoints"][0]["status"] == "approved"


def test_terminal_state_rejects_finalize():
    """Already-FINALIZED session must raise on second finalize()."""
    a = AIGC()
    session = a.open_session()
    session.finalize()
    with pytest.raises(SessionStateError):
        session.finalize()


# ---------------------------------------------------------------------------
# Schema tests: Phase 3 — extended workflow DSL fields
# ---------------------------------------------------------------------------

def test_workflow_participants_extended_shape_accepted_by_schema():
    schema = _load_schema()
    policy = yaml.safe_load(Path("tests/test_policies/workflow_participant_policy.yaml").read_text())
    jsonschema.validate(policy, schema)


def test_required_sequence_accepted_by_schema():
    schema = _load_schema()
    policy = yaml.safe_load(Path("tests/test_policies/workflow_sequence_policy.yaml").read_text())
    jsonschema.validate(policy, schema)


def test_allowed_transitions_accepted_by_schema():
    schema = _load_schema()
    policy = yaml.safe_load(Path("tests/test_policies/workflow_transition_policy.yaml").read_text())
    jsonschema.validate(policy, schema)


def test_allowed_agent_roles_accepted_by_schema():
    schema = _load_schema()
    policy = yaml.safe_load(Path("tests/test_policies/workflow_role_policy.yaml").read_text())
    jsonschema.validate(policy, schema)


def test_handoffs_accepted_by_schema():
    schema = _load_schema()
    policy = yaml.safe_load(Path("tests/test_policies/workflow_handoff_policy.yaml").read_text())
    jsonschema.validate(policy, schema)


def test_escalation_accepted_by_schema():
    schema = _load_schema()
    policy = yaml.safe_load(Path("tests/test_policies/workflow_escalation_policy.yaml").read_text())
    jsonschema.validate(policy, schema)


def test_protocol_constraints_accepted_by_schema():
    schema = _load_schema()
    policy = yaml.safe_load(Path("tests/test_policies/workflow_protocol_policy.yaml").read_text())
    jsonschema.validate(policy, schema)


def test_protocol_constraints_accept_local_bedrock_a2a_sections():
    schema = _load_schema()
    policy = {
        "policy_version": "1.0",
        "roles": ["planner"],
        "workflow": {
            "protocol_constraints": {
                "local": {"min_version": "1.0"},
                "bedrock": {"require_alias": True},
                "a2a": {"protocol_version": "1.0"},
            }
        }
    }
    jsonschema.validate(policy, schema)


def test_unknown_workflow_field_still_rejected():
    schema = _load_schema()
    policy = {
        "policy_version": "1.0",
        "roles": ["planner"],
        "workflow": {"unknown_field": True},
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(policy, schema)


# ---------------------------------------------------------------------------
# Composition hardening: Phase 4 — new DSL fields must only narrow
# ---------------------------------------------------------------------------

def test_child_cannot_widen_participants():
    """Child cannot add participant IDs not in base."""
    with pytest.raises(PolicyValidationError, match="escalation"):
        load_policy("tests/test_policies/composition_p4_widen_participants.yaml")


def test_child_cannot_widen_participant_protocols():
    """Child cannot widen protocols for a participant."""
    with pytest.raises(PolicyValidationError, match="escalation"):
        load_policy("tests/test_policies/composition_p4_widen_participant_protocols.yaml")


def test_child_cannot_widen_required_sequence():
    """Child cannot add steps to required_sequence."""
    with pytest.raises(PolicyValidationError, match="escalation"):
        load_policy("tests/test_policies/composition_p4_widen_required_sequence.yaml")


def test_child_cannot_widen_allowed_transitions():
    """Child cannot add transitions not in base."""
    with pytest.raises(PolicyValidationError, match="escalation"):
        load_policy("tests/test_policies/composition_p4_widen_allowed_transitions.yaml")


def test_child_cannot_widen_allowed_agent_roles():
    """Child cannot add roles not in base allowed_agent_roles."""
    with pytest.raises(PolicyValidationError, match="escalation"):
        load_policy("tests/test_policies/composition_p4_widen_allowed_agent_roles.yaml")


def test_child_cannot_widen_handoffs():
    """Child cannot add handoff pairs not in base."""
    with pytest.raises(PolicyValidationError, match="escalation"):
        load_policy("tests/test_policies/composition_p4_widen_handoffs.yaml")


def test_child_can_narrow_escalation_threshold():
    """Child can lower require_approval_after_steps (tightening)."""
    policy = load_policy("tests/test_policies/composition_p4_narrow_escalation.yaml")
    assert policy["workflow"]["escalation"]["require_approval_after_steps"] == 2


def test_child_cannot_raise_escalation_threshold():
    """Child cannot raise require_approval_after_steps (widening)."""
    with pytest.raises(PolicyValidationError, match="escalation"):
        load_policy("tests/test_policies/composition_p4_raise_escalation.yaml")


def test_child_cannot_remove_protocol_constraint_section():
    """Child cannot remove a base protocol family."""
    with pytest.raises(PolicyValidationError, match="weakening"):
        load_policy("tests/test_policies/composition_p4_remove_protocol_section.yaml")


def test_child_cannot_weaken_protocol_constraints():
    """Child cannot change a scalar value in a shared protocol family."""
    with pytest.raises(PolicyValidationError, match="escalation"):
        load_policy("tests/test_policies/composition_p4_weaken_protocol_constraints.yaml")
