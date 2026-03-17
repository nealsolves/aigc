"""Tests for tamper-evident audit chain (M2 feature)."""
import copy
import pytest
from aigc._internal.audit_chain import AuditChain, verify_chain
from aigc._internal.audit import generate_audit_artifact


def _sample_invocation():
    return {
        "policy_file": "test.yaml",
        "model_provider": "openai",
        "model_identifier": "gpt-4",
        "role": "planner",
        "input": {"prompt": "test"},
        "output": {"result": "ok"},
        "context": {},
    }


def _make_artifact(i=0):
    return generate_audit_artifact(
        _sample_invocation(),
        {"policy_version": "1.0"},
        enforcement_result="PASS",
        metadata={"gates_evaluated": [], "seq": i},
        timestamp=1000 + i,
    )


# ── Basic chain construction ────────────────────────────────────


def test_chain_empty():
    chain = AuditChain()
    assert chain.length == 0
    valid, errors = chain.verify()
    assert valid
    assert errors == []


def test_chain_single_artifact():
    chain = AuditChain()
    artifact = _make_artifact(0)
    chain.append(artifact)
    assert chain.length == 1
    assert artifact["chain_index"] == 0
    assert artifact["previous_audit_checksum"] is None
    assert artifact["chain_id"] == chain.chain_id


def test_chain_multiple_artifacts():
    chain = AuditChain()
    a1 = _make_artifact(0)
    a2 = _make_artifact(1)
    a3 = _make_artifact(2)
    chain.append(a1)
    chain.append(a2)
    chain.append(a3)

    assert a1["chain_index"] == 0
    assert a2["chain_index"] == 1
    assert a3["chain_index"] == 2
    assert a1["previous_audit_checksum"] is None
    assert a2["previous_audit_checksum"] is not None
    assert a3["previous_audit_checksum"] is not None
    assert a2["previous_audit_checksum"] != a3["previous_audit_checksum"]


def test_chain_custom_id():
    chain = AuditChain(chain_id="my-chain-001")
    assert chain.chain_id == "my-chain-001"
    artifact = _make_artifact()
    chain.append(artifact)
    assert artifact["chain_id"] == "my-chain-001"


# ── Chain verification ───────────────────────────────────────────


def test_valid_chain_verifies():
    chain = AuditChain()
    for i in range(5):
        chain.append(_make_artifact(i))
    valid, errors = chain.verify()
    assert valid
    assert errors == []


def test_broken_link_detected():
    chain = AuditChain()
    a1 = _make_artifact(0)
    a2 = _make_artifact(1)
    chain.append(a1)
    chain.append(a2)

    # Tamper with the link
    a2["previous_audit_checksum"] = "tampered" + "0" * 55
    valid, errors = chain.verify()
    assert not valid
    assert any("broken link" in e for e in errors)


def test_modified_artifact_detected():
    """Modifying an artifact breaks the chain for subsequent links."""
    chain = AuditChain()
    a1 = _make_artifact(0)
    a2 = _make_artifact(1)
    a3 = _make_artifact(2)
    chain.append(a1)
    chain.append(a2)
    chain.append(a3)

    # Store the original chain for standalone verification
    artifacts = [a1, a2, a3]

    # Tamper with a1 — this should break the link from a2
    a1["enforcement_result"] = "FAIL"
    valid, errors = verify_chain(artifacts)
    assert not valid


def test_chain_index_mismatch_detected():
    chain = AuditChain()
    a1 = _make_artifact(0)
    chain.append(a1)
    a1["chain_index"] = 99
    valid, errors = chain.verify()
    assert not valid
    assert any("chain_index" in e for e in errors)


def test_chain_id_mismatch_detected():
    chain = AuditChain()
    a1 = _make_artifact(0)
    chain.append(a1)
    a1["chain_id"] = "wrong-chain"
    valid, errors = chain.verify()
    assert not valid
    assert any("chain_id" in e for e in errors)


# ── Standalone verify_chain ──────────────────────────────────────


def test_verify_chain_standalone_valid():
    chain = AuditChain(chain_id="test")
    artifacts = []
    for i in range(3):
        a = _make_artifact(i)
        chain.append(a)
        artifacts.append(a)
    valid, errors = verify_chain(artifacts)
    assert valid


def test_verify_chain_empty():
    valid, errors = verify_chain([])
    assert valid


def test_verify_chain_standalone_broken():
    chain = AuditChain()
    a1 = _make_artifact(0)
    a2 = _make_artifact(1)
    chain.append(a1)
    chain.append(a2)
    a2["previous_audit_checksum"] = "wrong"
    valid, errors = verify_chain([a1, a2])
    assert not valid


# ── Determinism ──────────────────────────────────────────────────


def test_chain_deterministic():
    """Same artifacts produce same chain checksums."""
    chain1 = AuditChain(chain_id="c1")
    chain2 = AuditChain(chain_id="c1")
    a1 = _make_artifact(0)
    a2 = copy.deepcopy(a1)
    chain1.append(a1)
    chain2.append(a2)
    assert a1["previous_audit_checksum"] == a2["previous_audit_checksum"]
