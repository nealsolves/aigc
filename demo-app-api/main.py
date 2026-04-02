import secrets
from pathlib import Path
from typing import Literal
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from scenarios import SCENARIOS
from aigc import AIGC, InvocationBuilder, AIGCError, HMACSigner, verify_artifact

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
