"""PR-08 protocol_constraints enforcement tests."""
from __future__ import annotations
import pytest
from aigc._internal.enforcement import AIGC
from aigc._internal.errors import WorkflowProtocolViolationError
from aigc._internal.session import GovernanceSession
import uuid

POLICY = "tests/golden_replays/golden_policy_v1.yaml"
_BASE_INV = {
    "policy_file": POLICY, "model_provider": "openai",
    "model_identifier": "gpt-4", "role": "planner",
    "input": {"query": "test"},
    "context": {"role_declared": True, "schema_exists": True},
}
_GOOD_OUTPUT = {"result": "answer", "confidence": 0.95}


def _session(protocol_constraints, participants=None):
    a = AIGC()
    s = GovernanceSession(a, str(uuid.uuid4()), POLICY, None)
    s._protocol_constraints = protocol_constraints
    if participants:
        s._participants = participants
        s._participants_by_id = {p["id"]: p for p in participants}
    return s


def test_declared_protocol_required_when_protocol_constraints_present():
    """Missing protocol in invocation when constraints declared raises."""
    s = _session({"local": {}})
    with pytest.raises(WorkflowProtocolViolationError) as exc_info:
        with s:
            s.enforce_step_pre_call(dict(_BASE_INV))  # no protocol key
    assert exc_info.value.details.get("reason_code") == "WORKFLOW_PROTOCOL_REQUIRED"


def test_unknown_protocol_section_rejected():
    """Protocol not in declared constraint sections raises."""
    inv = dict(_BASE_INV)
    inv["protocol"] = "grpc"
    s = _session({"local": {}})
    with pytest.raises(WorkflowProtocolViolationError):
        with s:
            s.enforce_step_pre_call(inv)


def test_participant_protocol_mismatch_rejected():
    """Protocol not in participant's protocols list raises."""
    inv = dict(_BASE_INV)
    inv["protocol"] = "local"
    inv["context"] = {**inv["context"], "protocol_evidence": {"local": {}}}
    s = _session(
        {"local": {}, "bedrock": {}},
        participants=[{"id": "agent-1", "protocols": ["bedrock"]}],
    )
    with pytest.raises(WorkflowProtocolViolationError):
        with s:
            s.enforce_step_pre_call(inv, participant_id="agent-1")
            # agent-1 only allows bedrock, not local


def test_bedrock_alias_backed_identity_required_for_governed_binding():
    """Bedrock participant requires alias_backed=True in evidence."""
    inv = dict(_BASE_INV)
    inv["protocol"] = "bedrock"
    inv["context"] = {
        **inv["context"],
        "protocol_evidence": {"bedrock": {"alias_backed": False}},  # not alias-backed
    }
    s = _session(
        {"bedrock": {}},
        participants=[{"id": "agent-1", "protocols": ["bedrock"]}],
    )
    with pytest.raises(WorkflowProtocolViolationError):
        with s:
            s.enforce_step_pre_call(inv, participant_id="agent-1")


def test_a2a_requires_supported_interfaces_protocol_version_1_0():
    """A2A evidence without supportedInterfaces protocolVersion 1.0 raises."""
    inv = dict(_BASE_INV)
    inv["protocol"] = "a2a"
    inv["context"] = {
        **inv["context"],
        "protocol_evidence": {"a2a": {"supportedInterfaces": [{"protocolVersion": "2.0"}]}},
    }
    s = _session({"a2a": {}})
    with pytest.raises(WorkflowProtocolViolationError):
        with s:
            s.enforce_step_pre_call(inv)


def test_a2a_grpc_transport_rejected_with_protocol_violation():
    """A2A with gRPC transport raises WorkflowProtocolViolationError."""
    inv = dict(_BASE_INV)
    inv["protocol"] = "a2a"
    inv["context"] = {
        **inv["context"],
        "protocol_evidence": {
            "a2a": {
                "transport": "grpc",
                "supportedInterfaces": [{"protocolVersion": "1.0"}],
            }
        },
    }
    s = _session({"a2a": {}})
    with pytest.raises(WorkflowProtocolViolationError):
        with s:
            s.enforce_step_pre_call(inv)
