import copy
import hashlib
import json
import secrets
import uuid
from pathlib import Path
from typing import Literal
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from scenarios import SCENARIOS
from aigc import AIGC, InvocationBuilder, AIGCError, HMACSigner, verify_artifact, verify_chain

app = FastAPI(title="AIGC Demo API", version="0.3.0")

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

SAMPLE_POLICIES_DIR = (
    Path(__file__).resolve().parent.parent / "demo-app-streamlit" / "sample_policies"
)

MEDICAL_FACTORS = [
    {"name": "no_output_schema", "weight": 0.15, "condition": "no_output_schema"},
    {"name": "broad_roles",      "weight": 0.15, "condition": "broad_roles"},
    {"name": "missing_guards",   "weight": 0.20, "condition": "missing_guards"},
    {"name": "external_model",   "weight": 0.30, "condition": "external_model"},
    {"name": "no_preconditions", "weight": 0.20, "condition": "no_preconditions"},
]


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


@app.post("/api/enforce")
def enforce(req: EnforceRequest):
    if req.scenario_key not in SCENARIOS:
        raise HTTPException(status_code=422, detail=f"Unknown scenario_key: {req.scenario_key!r}")
    scenario = SCENARIOS[req.scenario_key]
    policy_path = str(SAMPLE_POLICIES_DIR / scenario["policy"])

    aigc = AIGC(
        risk_config={"mode": req.mode, "threshold": 0.7, "factors": MEDICAL_FACTORS}
    )
    invocation = (
        InvocationBuilder()
        .policy(policy_path)
        .model(scenario["model_provider"], scenario["model_id"])
        .role(scenario["role"])
        .input({"query": scenario["prompt"]})
        .output(scenario["output"])
        .context(scenario["context"])
        .build()
    )

    try:
        artifact = aigc.enforce(invocation)
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

    invocation = (
        InvocationBuilder()
        .policy(policy_path)
        .model(scenario["model_provider"], scenario["model_id"])
        .role(scenario["role"])
        .input({"query": scenario["prompt"]})
        .output(scenario["output"])
        .context(scenario["context"])
        .build()
    )

    try:
        artifact = aigc.enforce(invocation)
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
    data = json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


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
    invocation = (
        InvocationBuilder()
        .policy(policy_path)
        .model(scenario["model_provider"], scenario["model_id"])
        .role(scenario["role"])
        .input({"query": scenario["prompt"]})
        .output(scenario["output"])
        .context(scenario["context"])
        .build()
    )

    try:
        artifact = aigc.enforce(invocation)
    except AIGCError as exc:
        artifact = getattr(exc, "audit_artifact", None) or {}

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


@app.post("/api/chain/tamper")
def chain_tamper(req: ChainTamperRequest):
    artifacts = copy.deepcopy(req.artifacts)
    if req.index >= len(artifacts):
        return {"error": f"Index {req.index} out of range", "artifacts": artifacts}
    artifact = artifacts[req.index]
    current = artifact.get("enforcement_result", "PASS")
    artifact["enforcement_result"] = "FAIL" if current == "PASS" else "PASS"
    # Intentionally do NOT recompute checksum — that's what makes it tampered
    return {"artifacts": artifacts}
