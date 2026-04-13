import copy
import hashlib
import json
import secrets
import uuid
from datetime import date
from pathlib import Path
from typing import Literal
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from scenarios import SCENARIOS
from aigc import (
    AIGC, AIGCError, HMACSigner, verify_artifact, verify_chain,
    validate_policy_dates, PolicyTestCase, PolicyTestSuite,
)
from aigc.policy_loader import (
    merge_policies,
    COMPOSITION_INTERSECT,
    COMPOSITION_UNION,
    COMPOSITION_REPLACE,
)
from aigc._internal.errors import PolicyValidationError
from gates import GATES, get_gate_info
from loaders import InMemoryPolicyLoader
import yaml as yaml_lib

app = FastAPI(title="AIGC Demo API", version="0.3.3")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://nealsolves.github.io",
        "http://localhost:5173",
        "http://localhost:3000",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

SAMPLE_POLICIES_DIR = Path(__file__).resolve().parent / "sample_policies"

MEDICAL_FACTORS = [
    {"name": "no_output_schema", "weight": 0.15, "condition": "no_output_schema"},
    {"name": "broad_roles",      "weight": 0.15, "condition": "broad_roles"},
    {"name": "missing_guards",   "weight": 0.20, "condition": "missing_guards"},
    {"name": "external_model",   "weight": 0.30, "condition": "external_model"},
    {"name": "no_preconditions", "weight": 0.20, "condition": "no_preconditions"},
]


def _build_full_invocation(scenario: dict, policy_path: str) -> dict:
    return {
        "policy_file": policy_path,
        "model_provider": scenario["model_provider"],
        "model_identifier": scenario["model_id"],
        "role": scenario["role"],
        "input": {"query": scenario["prompt"]},
        "output": scenario["output"],
        "context": scenario["context"],
    }


def _build_pre_call_invocation(scenario: dict, policy_path: str) -> dict:
    return {
        "policy_file": policy_path,
        "model_provider": scenario["model_provider"],
        "model_identifier": scenario["model_id"],
        "role": scenario["role"],
        "input": {"query": scenario["prompt"]},
        "context": scenario["context"],
    }


@app.get("/api/scenarios/{scenario_key}")
def get_scenario(scenario_key: str):
    if scenario_key not in SCENARIOS:
        raise HTTPException(status_code=422, detail=f"Unknown scenario_key: {scenario_key!r}")
    s = SCENARIOS[scenario_key]
    return {
        "prompt": s["prompt"],
        "context": s["context"],
        "policy": s["policy"],
        "model_provider": s["model_provider"],
        "model_id": s["model_id"],
        "role": s["role"],
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/scenarios")
def list_scenarios():
    return {"scenarios": list(SCENARIOS.keys())}


@app.get("/api/policies")
def list_policies():
    names = sorted(p.name for p in SAMPLE_POLICIES_DIR.glob("*.yaml"))
    return {"policies": names}


class EnforceRequest(BaseModel):
    scenario_key: str
    mode: Literal["strict", "risk_scored", "warn_only"] = "risk_scored"
    flow: Literal["unified", "split"] = "unified"


@app.post("/api/enforce")
def enforce(req: EnforceRequest):
    if req.scenario_key not in SCENARIOS:
        raise HTTPException(status_code=422, detail=f"Unknown scenario_key: {req.scenario_key!r}")
    scenario = SCENARIOS[req.scenario_key]
    policy_path = str(SAMPLE_POLICIES_DIR / scenario["policy"])

    aigc = AIGC(
        risk_config={"mode": req.mode, "threshold": 0.7, "factors": MEDICAL_FACTORS}
    )
    try:
        if req.flow == "split":
            pre_call_result = aigc.enforce_pre_call(_build_pre_call_invocation(scenario, policy_path))
            artifact = aigc.enforce_post_call(pre_call_result, scenario["output"])
        else:
            artifact = aigc.enforce(_build_full_invocation(scenario, policy_path))
        return {"artifact": artifact, "error": None}
    except AIGCError as exc:
        artifact = getattr(exc, "audit_artifact", None)
        return {"artifact": artifact, "error": str(exc)}


@app.post("/api/sign/generate-key")
def generate_key():
    return {"key": secrets.token_hex(32)}


class SignEnforceRequest(BaseModel):
    scenario_key: str = "signing_basic"
    key: str


@app.post("/api/sign/enforce")
def sign_enforce(req: SignEnforceRequest):
    if req.scenario_key not in SCENARIOS:
        raise HTTPException(status_code=422, detail=f"Unknown scenario_key: {req.scenario_key!r}")
    scenario = SCENARIOS[req.scenario_key]
    policy_path = str(SAMPLE_POLICIES_DIR / scenario["policy"])
    try:
        key_bytes = bytes.fromhex(req.key)
    except ValueError:
        raise HTTPException(status_code=422, detail="key must be a valid hex string (64 hex chars)")
    signer = HMACSigner(key=key_bytes)
    aigc = AIGC(signer=signer)

    try:
        artifact = aigc.enforce(_build_full_invocation(scenario, policy_path))
        return {"artifact": artifact, "error": None}
    except AIGCError as exc:
        artifact = getattr(exc, "audit_artifact", None)
        return {"artifact": artifact, "error": str(exc)}


class VerifySignatureRequest(BaseModel):
    artifact: dict
    key: str


@app.post("/api/sign/verify")
def verify_signature(req: VerifySignatureRequest):
    try:
        key_bytes = bytes.fromhex(req.key)
    except ValueError:
        raise HTTPException(status_code=422, detail="key must be a valid hex string (64 hex chars)")
    signer = HMACSigner(key=key_bytes)
    valid = verify_artifact(req.artifact, signer)
    return {"valid": valid}


def _canonical_sha256(obj: dict) -> str:
    """Replicates AuditChain._compute_artifact_checksum for stateless use."""
    from aigc._internal.utils import canonical_json_bytes
    return hashlib.sha256(canonical_json_bytes(obj)).hexdigest()


class ChainAppendRequest(BaseModel):
    scenario_key: str
    chain_id: str | None = None
    previous_checksum: str | None = None
    chain_index: int = 0


@app.post("/api/chain/append")
def chain_append(req: ChainAppendRequest):
    if req.scenario_key not in SCENARIOS:
        raise HTTPException(status_code=422, detail=f"Unknown scenario_key: {req.scenario_key!r}")
    scenario = SCENARIOS[req.scenario_key]
    policy_path = str(SAMPLE_POLICIES_DIR / scenario["policy"])
    chain_id = req.chain_id or str(uuid.uuid4())

    aigc = AIGC()
    try:
        artifact = aigc.enforce(_build_full_invocation(scenario, policy_path))
    except AIGCError as exc:
        artifact = getattr(exc, "audit_artifact", None)
        if not artifact:
            raise HTTPException(status_code=422, detail=str(exc))

    # Inject chain fields — mirrors AuditChain.append()
    artifact["chain_id"] = chain_id
    artifact["chain_index"] = req.chain_index
    artifact["previous_audit_checksum"] = req.previous_checksum
    artifact_copy = {k: v for k, v in artifact.items() if k != "checksum"}
    artifact["checksum"] = _canonical_sha256(artifact_copy)

    return {"artifact": artifact, "chain_id": chain_id}


class ChainVerifyRequest(BaseModel):
    artifacts: list[dict]


@app.post("/api/chain/verify")
def chain_verify(req: ChainVerifyRequest):
    valid, errors = verify_chain(req.artifacts)
    return {"valid": valid, "errors": errors}


class ChainTamperRequest(BaseModel):
    artifacts: list[dict]
    index: int


class ComposeRequest(BaseModel):
    parent_yaml: str
    child_yaml: str
    strategy: str = "intersect"


_STRATEGY_MAP = {
    "intersect": COMPOSITION_INTERSECT,
    "union": COMPOSITION_UNION,
    "replace": COMPOSITION_REPLACE,
}


@app.post("/api/compose")
def compose_policies(req: ComposeRequest):
    try:
        base  = yaml_lib.safe_load(req.parent_yaml)
        child = yaml_lib.safe_load(req.child_yaml)
    except yaml_lib.YAMLError as exc:
        return {"merged_yaml": None, "escalations": [], "diff": {}, "error": str(exc)}

    if not isinstance(base, dict):
        return {"merged_yaml": None, "escalations": [], "diff": {}, "error": "parent_yaml must be a YAML mapping"}
    if not isinstance(child, dict):
        return {"merged_yaml": None, "escalations": [], "diff": {}, "error": "child_yaml must be a YAML mapping"}

    strategy = _STRATEGY_MAP.get(req.strategy, COMPOSITION_INTERSECT)

    try:
        merged = merge_policies(base, child, composition_strategy=strategy)
        merged.pop("extends", None)
        merged.pop("composition_strategy", None)
    except Exception as exc:
        return {"merged_yaml": None, "escalations": [], "diff": {}, "error": str(exc)}

    # Escalation detection
    base_roles = set(base.get("roles", []))
    merged_roles = set(merged.get("roles", []))
    base_tools = {t["name"] for t in base.get("tools", {}).get("allowed_tools", []) if isinstance(t, dict) and "name" in t}
    merged_tools = {t["name"] for t in merged.get("tools", {}).get("allowed_tools", []) if isinstance(t, dict) and "name" in t}
    base_post = set(base.get("post_conditions", {}).get("required", []))
    merged_post = set(merged.get("post_conditions", {}).get("required", []))

    escalations: list[str] = []
    new_roles = merged_roles - base_roles
    if new_roles:
        escalations.append(f"New roles not in base: {sorted(new_roles)}")
    new_tools = merged_tools - base_tools
    if new_tools:
        escalations.append(f"New tools not in base: {sorted(new_tools)}")
    removed_post = base_post - merged_post
    if removed_post:
        escalations.append(f"Postconditions removed: {sorted(removed_post)}")

    diff = {
        "kept_roles": sorted(base_roles & merged_roles),
        "removed_roles": sorted(base_roles - merged_roles),
        "added_roles": sorted(new_roles),
    }

    return {
        "merged_yaml": yaml_lib.dump(merged, default_flow_style=False),
        "escalations": escalations,
        "diff": diff,
        "error": None,
    }


@app.post("/api/chain/tamper")
def chain_tamper(req: ChainTamperRequest):
    artifacts = copy.deepcopy(req.artifacts)
    if not (0 <= req.index < len(artifacts)):
        raise HTTPException(status_code=422, detail=f"Index {req.index} out of range")
    artifact = artifacts[req.index]
    current = artifact.get("enforcement_result", "PASS")
    artifact["enforcement_result"] = "FAIL" if current == "PASS" else "PASS"
    # Intentionally do NOT recompute checksum — that's what makes it tampered
    return {"artifacts": artifacts}


class LoadPolicyRequest(BaseModel):
    policy_name: str


@app.post("/api/policy/load")
def load_policy_endpoint(req: LoadPolicyRequest):
    path = (SAMPLE_POLICIES_DIR / req.policy_name).resolve()
    if not path.is_relative_to(SAMPLE_POLICIES_DIR.resolve()):
        return {"policy": None, "yaml_text": None, "error": "Access denied"}
    if not path.exists():
        return {"policy": None, "yaml_text": None, "error": f"Not found: {req.policy_name}"}
    try:
        text = path.read_text()
        policy = yaml_lib.safe_load(text)
        return {"policy": policy, "yaml_text": text, "error": None}
    except Exception as exc:
        return {"policy": None, "yaml_text": None, "error": str(exc)}


class ValidateDatesRequest(BaseModel):
    effective_date: str | None = None
    expiration_date: str | None = None
    reference_date: str | None = None


class LoadInMemoryRequest(BaseModel):
    yaml_text: str


@app.post("/api/policy/load-inmemory")
def load_policy_inmemory(req: LoadInMemoryRequest):
    try:
        loader = InMemoryPolicyLoader(req.yaml_text)
        policy = loader.load("inline")
        if not isinstance(policy, dict):
            return {"policy": None, "yaml_text": req.yaml_text, "loader_class": "InMemoryPolicyLoader", "error": "YAML must be a mapping"}
        return {"policy": policy, "yaml_text": req.yaml_text, "loader_class": "InMemoryPolicyLoader", "error": None}
    except Exception as exc:
        return {"policy": None, "yaml_text": None, "loader_class": "InMemoryPolicyLoader", "error": str(exc)}


@app.post("/api/policy/validate-dates")
def validate_dates_endpoint(req: ValidateDatesRequest):
    policy: dict = {}
    if req.effective_date:
        policy["effective_date"] = req.effective_date
    if req.expiration_date:
        policy["expiration_date"] = req.expiration_date

    ref = date.fromisoformat(req.reference_date) if req.reference_date else date.today()

    try:
        evidence = validate_policy_dates(policy, clock=lambda: ref)
        return {
            "in_range": evidence.get("active", True),
            "evidence": evidence,
            "error": None,
        }
    except PolicyValidationError as exc:
        return {"in_range": False, "evidence": {}, "error": str(exc)}


class PolicyTestRequest(BaseModel):
    policy_name: str


@app.post("/api/policy/test")
def run_policy_tests(req: PolicyTestRequest):
    path = (SAMPLE_POLICIES_DIR / req.policy_name).resolve()
    if not path.is_relative_to(SAMPLE_POLICIES_DIR.resolve()):
        return {"results": [], "error": "Access denied"}
    if not path.exists():
        return {"results": [], "error": f"Not found: {req.policy_name}"}
    policy_path = str(path)

    cases = [
        (PolicyTestCase(
            name="valid role passes",
            policy_file=policy_path,
            role="doctor",
            model_provider="mock",
            model_identifier="mock-model",
            input_data={"query": "What is the dosage?"},
            output_data={"result": "500mg"},
            context={
                "domain": "medical",
                "role_declared": True,
                "schema_exists": True,
                "human_review_required": True,
            },
        ), "pass"),
        (PolicyTestCase(
            name="unauthorized role fails",
            policy_file=policy_path,
            role="unknown_role",
            model_provider="mock",
            model_identifier="mock-model",
            input_data={"query": "What is the dosage?"},
            output_data={"result": "500mg"},
            context={
                "domain": "medical",
                "role_declared": True,
                "schema_exists": True,
                "human_review_required": True,
            },
        ), "fail"),
        (PolicyTestCase(
            name="missing precondition fails",
            policy_file=policy_path,
            role="doctor",
            model_provider="mock",
            model_identifier="mock-model",
            input_data={"query": "What is the dosage?"},
            output_data={"result": "500mg"},
            context={
                "domain": "medical",
                "schema_exists": True,
                "human_review_required": True,
            },
        ), "fail"),
    ]

    suite = PolicyTestSuite(f"{req.policy_name} test suite")
    for case, expected in cases:
        suite.add(case, expected)

    raw_results = suite.run_all()

    return {
        "results": [
            {
                "name": r.name,
                "enforcement_result": r.enforcement_result,
                "passed": r.passed,
                "failure_reason": r.failure_reason,
            }
            for r in raw_results
        ],
        "all_met_expectations": suite.all_passed(raw_results),
        "error": None,
    }


class Lab8KBRequest(BaseModel):
    scenario_key: str = "kb_sourced_pass"


@app.post("/api/lab8/query-kb")
def lab8_query_kb(req: Lab8KBRequest):
    if req.scenario_key not in SCENARIOS:
        raise HTTPException(status_code=422, detail=f"Unknown scenario_key: {req.scenario_key!r}")
    scenario = SCENARIOS[req.scenario_key]
    policy_path = str(SAMPLE_POLICIES_DIR / scenario["policy"])

    from aigc import ProvenanceGate
    aigc_instance = AIGC(custom_gates=[ProvenanceGate()])
    invocation = _build_full_invocation(scenario, policy_path)
    source_ids = scenario["context"].get("provenance", {}).get("source_ids", [])

    try:
        artifact = aigc_instance.enforce(invocation)
        return {"artifact": artifact, "source_ids": source_ids, "error": None}
    except AIGCError as exc:
        artifact = getattr(exc, "audit_artifact", None)
        return {"artifact": artifact, "source_ids": source_ids, "error": str(exc)}


class Lab9CompareRequest(BaseModel):
    scenario_key: str = "low_risk_faq"


@app.post("/api/lab9/compare")
def lab9_compare(req: Lab9CompareRequest):
    if req.scenario_key not in SCENARIOS:
        raise HTTPException(status_code=422, detail=f"Unknown scenario_key: {req.scenario_key!r}")
    scenario = SCENARIOS[req.scenario_key]
    policy_path = str(SAMPLE_POLICIES_DIR / scenario["policy"])

    # Governed path — strict mode exposes full policy impact (risk threshold enforced)
    aigc_instance = AIGC(
        risk_config={"mode": "strict", "threshold": 0.7, "factors": MEDICAL_FACTORS}
    )
    governed_artifact = None
    governed_error = None
    try:
        governed_artifact = aigc_instance.enforce(_build_full_invocation(scenario, policy_path))
    except AIGCError as exc:
        governed_artifact = getattr(exc, "audit_artifact", None)
        governed_error = str(exc)

    # Ungoverned path — synthetic record representing raw model output with no enforcement
    ungoverned_artifact = {
        "enforcement_result": "PASS",
        "model_provider": scenario["model_provider"],
        "model_identifier": scenario["model_id"],
        "role": scenario["role"],
        "policy_version": "ungoverned",
        "metadata": {
            "gates_evaluated": [],
            "risk_scoring": None,
            "mode": "ungoverned",
        },
        "output": scenario["output"],
    }

    return {
        # Top-level artifact key so useApi auto-ingests the governed result into auditHistory
        "artifact": governed_artifact,
        "governed": {"artifact": governed_artifact, "error": governed_error},
        "ungoverned": {"artifact": ungoverned_artifact, "error": None},
        "scenario_key": req.scenario_key,
    }


class Lab10SplitRequest(BaseModel):
    scenario_key: str = "split_precall_block"
    mode: Literal["strict", "risk_scored", "warn_only"] = "risk_scored"


@app.post("/api/lab10/split-trace")
def lab10_split_trace(req: Lab10SplitRequest):
    if req.scenario_key not in SCENARIOS:
        raise HTTPException(status_code=422, detail=f"Unknown scenario_key: {req.scenario_key!r}")
    scenario = SCENARIOS[req.scenario_key]
    policy_path = str(SAMPLE_POLICIES_DIR / scenario["policy"])

    aigc_instance = AIGC(
        risk_config={"mode": req.mode, "threshold": 0.7, "factors": MEDICAL_FACTORS}
    )
    pre_invocation = _build_pre_call_invocation(scenario, policy_path)

    try:
        pre_result = aigc_instance.enforce_pre_call(pre_invocation)
    except AIGCError as exc:
        # Phase A blocked
        artifact = getattr(exc, "audit_artifact", None)
        meta = (artifact or {}).get("metadata", {})
        return {
            "phase_a": {
                "result": "FAIL",
                "gates_evaluated": meta.get("pre_call_gates_evaluated", []),
                "failures": (artifact or {}).get("failures", []),
                "blocked": True,
            },
            "phase_b": None,
            "artifact": artifact,
            "combined_result": "FAIL",
            "error": str(exc),
        }

    # Phase A passed — record its metadata from the PreCallResult token
    phase_a_meta = pre_result.phase_a_metadata
    phase_a = {
        "result": "PASS",
        "gates_evaluated": phase_a_meta.get("gates_evaluated", []),
        "failures": [],
        "blocked": False,
    }

    # Phase B
    try:
        artifact = aigc_instance.enforce_post_call(pre_result, scenario["output"])
    except AIGCError as exc:
        artifact = getattr(exc, "audit_artifact", None)
        meta = (artifact or {}).get("metadata", {})
        return {
            "phase_a": phase_a,
            "phase_b": {
                "result": "FAIL",
                "gates_evaluated": meta.get("post_call_gates_evaluated", []),
                "failures": (artifact or {}).get("failures", []),
                "blocked": True,
            },
            "artifact": artifact,
            "combined_result": "FAIL",
            "error": str(exc),
        }

    meta = artifact.get("metadata", {})
    phase_b = {
        "result": artifact["enforcement_result"],
        "gates_evaluated": meta.get("post_call_gates_evaluated", []),
        "failures": artifact.get("failures") or [],
        "blocked": artifact["enforcement_result"] == "FAIL",
    }

    return {
        "phase_a": phase_a,
        "phase_b": phase_b,
        "artifact": artifact,
        "combined_result": artifact["enforcement_result"],
        "error": None,
    }


@app.get("/api/gate/{gate_name}")
def get_gate(gate_name: str):
    gate = GATES.get(gate_name)
    if not gate:
        return {"error": f"Unknown gate: {gate_name}"}
    return get_gate_info(gate)


class GateRunRequest(BaseModel):
    gate_name: str
    scenario_key: str


@app.post("/api/gate/run")
def run_gate(req: GateRunRequest):
    gate = GATES.get(req.gate_name)
    if not gate:
        return {"artifact": None, "gate_result": None, "error": f"Unknown gate: {req.gate_name}"}

    if req.scenario_key not in SCENARIOS:
        raise HTTPException(status_code=422, detail=f"Unknown scenario_key: {req.scenario_key!r}")

    scenario = SCENARIOS[req.scenario_key]
    policy_path = str(SAMPLE_POLICIES_DIR / scenario["policy"])
    aigc = AIGC(custom_gates=[gate])

    invocation = _build_full_invocation(scenario, policy_path)

    try:
        artifact = aigc.enforce(invocation)
    except AIGCError as exc:
        artifact = getattr(exc, "audit_artifact", None)

    # Run gate with the same policy and context used during enforcement
    with open(policy_path) as _f:
        policy_dict = yaml_lib.safe_load(_f) or {}
    direct_result = gate.evaluate(invocation, policy_dict, scenario["context"])

    return {
        "artifact": artifact,
        "gate_result": {
            "name": req.gate_name,
            "insertion_point": gate.insertion_point,
            "passed": direct_result.passed,
            "failures": direct_result.failures,
            "metadata": direct_result.metadata,
        },
        "error": None,
    }
