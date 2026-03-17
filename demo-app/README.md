# AIGC Governance Lab — Demo App

Interactive Streamlit application for exploring the AIGC SDK's governance pipeline. Seven hands-on labs walk you through risk scoring, artifact signing, audit chains, policy composition, pluggable loaders, custom gates, and compliance reporting — all without spending API tokens.

## Quick Start

```bash
# From the project root, install the SDK in dev mode
pip install -e .

# Install demo-app dependencies
pip install -r demo-app/requirements.txt

# Launch the app
cd demo-app
streamlit run app.py
```

The app opens at `http://localhost:8501`. No API keys are required — every lab uses deterministic mock responses.

## Prerequisites

- Python 3.10+
- The `aigc` SDK installed from the parent directory (`pip install -e ../`)
- Dependencies listed in `requirements.txt`: Streamlit ≥ 1.30, PyYAML ≥ 6.0, jsonschema ≥ 4.0

## Labs

| Lab | Name | What It Demonstrates |
|-----|------|----------------------|
| 1 | **Risk Scoring Engine** | Factor-based risk scoring with strict, risk_scored, and warn_only modes. Visual risk gauge, signal breakdown table. |
| 2 | **Signing & Verification** | HMAC-SHA256 artifact signing, tamper detection (flip a field and watch verification fail), key rotation. |
| 3 | **Tamper-Evident Audit Chain** | Hash-linked chain of artifacts. Build a chain, verify integrity, tamper with a link, export as JSON. |
| 4 | **Policy Composition** | Merge base + child policies with intersect / union / replace strategies. Privilege escalation detection. |
| 5 | **Loaders, Versioning & Testing** | FileSystem vs InMemory loaders, effective/expiration date validation with timeline visualization, PolicyTestSuite runner. |
| 6 | **Custom Enforcement Gates** | Pre-built gate plugins (Confidence, PII Detection, Response Length, Audit Metadata). Pipeline visualization shows gate insertion point. |
| 7 | **Compliance Dashboard** | Aggregate audit trail across all labs. Filter by status/policy, export JSON or CSV, CLI equivalent commands. |

## Directory Structure

```
demo-app/
├── app.py                  # Entry point and sidebar navigation
├── requirements.txt        # Python dependencies
├── labs/
│   ├── lab1_risk_scoring.py
│   ├── lab2_signing.py
│   ├── lab3_chain.py
│   ├── lab4_composition.py
│   ├── lab5_loaders.py
│   ├── lab6_custom_gates.py
│   └── lab7_compliance.py
├── shared/
│   ├── state.py            # Session state management and AIGC factory
│   ├── ai_client.py        # Mock AI scenarios (no real API calls)
│   ├── guide_rail.py       # Contextual help system (4 display modes)
│   ├── artifact_display.py # Reusable audit artifact viewer components
│   └── policy_editor.py    # YAML editor with live validation
├── sample_policies/
│   ├── medical_ai.yaml           # Primary demo policy (v2.0)
│   ├── medical_ai_child.yaml     # Child policy for composition lab
│   ├── finance_ai.yaml           # Finance-sector strict policy
│   ├── content_moderation.yaml   # Content moderation policy
│   └── high_risk.yaml            # Aggressive blocking at low threshold
└── tests/
    └── __init__.py
```

## How It Works

Every lab follows the same pattern:

1. A **mock scenario** provides a deterministic prompt, output, and context (see `shared/ai_client.py`).
2. An `InvocationBuilder` assembles the invocation dict.
3. `AIGC.enforce()` runs the full governance pipeline.
4. The resulting **audit artifact** is displayed with PASS/FAIL badge, risk gauge, and raw JSON.
5. A **guide rail** panel (right column) provides step-by-step instructions for each lab.

Session state is managed centrally in `shared/state.py`. Each lab gets a fresh `AIGC` instance so configuration changes in one lab don't pollute another.

## Sample Policies

Five YAML policy files in `sample_policies/` cover different governance postures:

- **medical_ai.yaml** — The primary policy used by most labs. Four roles (doctor, nurse, admin, researcher), risk_scored mode with 0.7 threshold, five risk factors.
- **medical_ai_child.yaml** — Extends `medical_ai.yaml` with intersect composition. Restricts to nurse role only with reduced tool access.
- **finance_ai.yaml** — Finance-sector policy with strict mode, 0.5 threshold, and date bounds (2026).
- **content_moderation.yaml** — Strict mode with a very low 0.3 threshold.
- **high_risk.yaml** — Five roles, aggressive 0.3 threshold, strict blocking.

## Guide Rail System

Labs 1–6 include a contextual guide panel rendered in the right 25% of the screen. Four display modes adapt to each lab's workflow:

- **linear** — Numbered steps with completion tracking (Labs 1, 4)
- **workflows** — Selectable workflow cards with sub-steps (Labs 2, 5)
- **iterative** — Repeating cycle with milestone progress bar (Lab 3)
- **cookbook** — Named recipes with "Load" buttons (Lab 6)

Lab 7 (Compliance Dashboard) uses full-width layout with no guide rail.

## Version

v0.3.0 — Milestone 2 Demo
