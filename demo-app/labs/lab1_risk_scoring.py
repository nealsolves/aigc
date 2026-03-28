"""Lab 1: Risk Scoring Engine.

Demonstrates AIGC risk scoring with three modes:
  - strict:      threshold breach fails enforcement
  - risk_scored: threshold recorded and enforced
  - warn_only:   warning recorded, never blocks

Each scenario uses a different policy file and model provider so the
risk factor breakdown genuinely varies between Low / Medium / High.
"""

from __future__ import annotations

from pathlib import Path

import yaml
import streamlit as st

from aigc import InvocationBuilder, AIGCError

from shared.state import get_aigc, sample_policy_path
from shared.ai_client import get_scenario
from shared.artifact_display import render_artifact, render_risk_gauge, render_signal_breakdown
from shared.policy_editor import render_policy_editor, load_policy_text
from shared.guide_rail import LabGuide, GuideStep


# ---------------------------------------------------------------------------
# Scenario → policy/model mapping
# ---------------------------------------------------------------------------
# Each scenario uses a different policy to produce meaningfully different
# risk profiles.  The model_provider also varies: "internal" for low risk,
# "mock" (external) for medium and high.
SCENARIO_CONFIG: dict[str, dict] = {
    "low_risk_faq": {
        "policy": "medical_ai_low_risk.yaml",
        "model_provider": "internal",
        "model_id": "internal-med-v1",
        "role": "doctor",
        "description": (
            "Well-configured policy: 2 roles, guards present, output schema "
            "defined, preconditions set, internal model. Expected score ≈ 0.00."
        ),
    },
    "medium_risk_medical": {
        "policy": "medical_ai.yaml",
        "model_provider": "mock",
        "model_id": "mock-model",
        "role": "doctor",
        "description": (
            "Standard policy: 4 roles (triggers broad_roles), no guards "
            "(triggers missing_guards), external model (triggers external_model). "
            "Expected score ≈ 0.65."
        ),
    },
    "high_risk_drug_interaction": {
        "policy": "medical_ai_high_risk.yaml",
        "model_provider": "mock",
        "model_id": "mock-model",
        "role": "doctor",
        "description": (
            "Loose policy: 5 roles, no guards, no output schema, no "
            "preconditions, external model. All factors trigger. "
            "Expected score ≈ 1.00."
        ),
    },
}


# ---------------------------------------------------------------------------
# Guide rail definition
# ---------------------------------------------------------------------------
def get_guide() -> LabGuide:
    return LabGuide(
        lab_id="lab1",
        title="Risk Scoring Engine",
        overview="See how risk factors combine into a score that gates enforcement.",
        mode="linear",
        steps=[
            GuideStep(
                title="Choose a scenario",
                instruction=(
                    "Pick a preset (Low / Medium / High risk). Each uses a "
                    "different policy with different safeguards enabled."
                ),
                what_to_expect="The prompt, context, and policy all update to match the scenario.",
                completion_key="lab1_scenario_chosen",
            ),
            GuideStep(
                title="Select risk mode",
                instruction="Choose strict, risk_scored, or warn_only to change how the threshold is applied.",
                what_to_expect="The policy YAML updates with the selected mode.",
                completion_key="lab1_mode_set",
            ),
            GuideStep(
                title="Run enforcement",
                instruction='Click "Run Enforcement" to execute the governance pipeline.',
                what_to_expect="A risk gauge, signal breakdown, and audit artifact appear.",
                completion_key="lab1_last_artifact",
            ),
            GuideStep(
                title="Inspect the result",
                instruction="Examine the risk gauge, factor table, and full audit artifact.",
                what_to_expect=(
                    '- **"Policy check passed"** means the governance pipeline ran all its '
                    "checks (role validation, preconditions, schema, risk scoring) and the "
                    "invocation met all policy requirements. It is a compliance verdict.\n"
                    '- **"Policy check failed"** means a governance violation was detected '
                    "and the invocation was blocked. "
                    "Low risk: score ≈ 0.00 (no factors trigger). "
                    "Medium: score ≈ 0.65 (3 factors). "
                    "High: score ≈ 1.00 (all 5 factors)."
                ),
                completion_key="lab1_last_artifact",
            ),
        ],
        glossary={
            "Risk Factor": "A named condition (e.g. no_output_schema) with a weight. Triggered = contributes its weight to the total score.",
            "Threshold": "Score above this value triggers the mode's enforcement action.",
            "strict": "Score > threshold = FAIL. No tolerance.",
            "risk_scored": "Score > threshold = FAIL with risk evidence. Scores at/below pass.",
            "warn_only": "Score is recorded but never blocks enforcement.",
            "Policy check passed": "The governance pipeline ran all checks and the invocation met all policy requirements.",
            "Policy check failed": "A governance violation was detected and the invocation was blocked.",
        },
    )


# ---------------------------------------------------------------------------
# Main render
# ---------------------------------------------------------------------------
def render() -> None:
    st.header("Lab 1: Risk Scoring Engine")
    st.caption(
        "Each scenario uses a different policy with different safeguards. "
        "Switch between them to see how risk factors and scores change."
    )

    # -- Scenario selector -------------------------------------------------
    scenario_col, mode_col = st.columns(2)

    with scenario_col:
        scenario_name = st.radio(
            "Preset Scenario",
            ["low_risk_faq", "medium_risk_medical", "high_risk_drug_interaction"],
            format_func=lambda s: {
                "low_risk_faq": "Low Risk: Simple FAQ",
                "medium_risk_medical": "Medium Risk: Medical Advice",
                "high_risk_drug_interaction": "High Risk: Drug Interaction",
            }.get(s, s),
            key="lab1_scenario",
            horizontal=True,
        )
        st.session_state["lab1_scenario_chosen"] = True

    with mode_col:
        mode = st.radio(
            "Risk Mode",
            ["strict", "risk_scored", "warn_only"],
            index=1,
            key="lab1_mode_selector",
            horizontal=True,
        )
        st.session_state["lab1_mode"] = mode
        st.session_state["lab1_mode_set"] = True

    # -- Clear stale results when scenario or mode changes -----------------
    _current_config = f"{scenario_name}:{mode}"
    if st.session_state.get("_lab1_last_config") != _current_config:
        st.session_state["lab1_last_artifact"] = None
        st.session_state["_lab1_last_config"] = _current_config

    # -- Load scenario + policy -------------------------------------------
    scenario = get_scenario(scenario_name)
    config = SCENARIO_CONFIG[scenario_name]
    policy_path = sample_policy_path(config["policy"])
    raw_policy, parsed_policy = load_policy_text(policy_path)

    # Override risk mode in the policy text for display
    if parsed_policy:
        parsed_policy.setdefault("risk", {})["mode"] = mode

    # -- Scenario description ----------------------------------------------
    st.info(f"**{scenario_name.replace('_', ' ').title()}:** {config['description']}")

    # -- Two columns: config | results ------------------------------------
    config_col, result_col = st.columns(2)

    with config_col:
        st.subheader("Configuration")

        # Show the active policy
        with st.expander(f"Policy: {config['policy']}", expanded=False):
            if parsed_policy:
                st.code(yaml.dump(parsed_policy, default_flow_style=False), language="yaml")

        st.caption(f"Model: `{config['model_provider']}` / `{config['model_id']}`")

        st.text_area(
            "Prompt",
            value=scenario["prompt"],
            key="lab1_prompt",
            height=80,
            disabled=True,
        )

        st.json(scenario["context"], expanded=False)

        # -- Run button ----------------------------------------------------
        run = st.button("Run Enforcement", type="primary", use_container_width=True)

    with result_col:
        st.subheader("Results")

        if run:
            _run_enforcement(policy_path, scenario, mode, config)

        # Show last result if available
        artifact = st.session_state.get("lab1_last_artifact")
        if artifact:
            # Risk gauge
            risk_meta = artifact.get("metadata", {}).get("risk_scoring")
            if isinstance(risk_meta, dict):
                render_risk_gauge(
                    risk_meta.get("score", 0),
                    risk_meta.get("threshold", 0.7),
                    risk_meta.get("mode", ""),
                )
                render_signal_breakdown(risk_meta.get("basis", []))
            elif isinstance(risk_meta, (int, float)):
                render_risk_gauge(float(risk_meta), 0.7)
        else:
            st.info("Run enforcement to see results here.")

    # Render artifact outside columns to avoid nested-column violation
    artifact = st.session_state.get("lab1_last_artifact")
    if artifact:
        st.divider()
        render_artifact(artifact, expanded=True)


# ---------------------------------------------------------------------------
# Enforcement execution
# ---------------------------------------------------------------------------
def _run_enforcement(
    policy_path: str,
    scenario: dict,
    mode: str,
    config: dict,
) -> None:
    """Execute enforcement with the given scenario and risk mode."""
    try:
        aigc = get_aigc(
            risk_config={"mode": mode, "threshold": 0.7, "factors": _medical_factors()},
        )

        invocation = (
            InvocationBuilder()
            .policy(policy_path)
            .model(config["model_provider"], config["model_id"])
            .role(config["role"])
            .input({"query": scenario["prompt"]})
            .output(scenario["output"])
            .context(scenario["context"])
            .build()
        )

        artifact = aigc.enforce(invocation)
        st.session_state["lab1_last_artifact"] = artifact
        st.success("Policy check passed — all governance rules satisfied")

    except AIGCError as exc:
        artifact = getattr(exc, "audit_artifact", None)
        if artifact:
            st.session_state["lab1_last_artifact"] = artifact
        st.error(f"Policy check failed — governance violation detected: {exc}")


def _medical_factors() -> list[dict]:
    """Return the risk factors used across all medical scenarios."""
    return [
        {"name": "no_output_schema", "weight": 0.15, "condition": "no_output_schema"},
        {"name": "broad_roles", "weight": 0.15, "condition": "broad_roles"},
        {"name": "missing_guards", "weight": 0.2, "condition": "missing_guards"},
        {"name": "external_model", "weight": 0.3, "condition": "external_model"},
        {"name": "no_preconditions", "weight": 0.2, "condition": "no_preconditions"},
    ]
