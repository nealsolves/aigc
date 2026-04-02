from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
