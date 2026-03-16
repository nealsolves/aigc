"""Lab 1: Risk Scoring Engine.

Demonstrates AIGC risk scoring with three modes:
  - strict:      threshold breach fails enforcement
  - risk_scored: threshold recorded and enforced
  - warn_only:   warning recorded, never blocks

The user picks a scenario, adjusts the risk mode, and sees how the
same invocation produces different outcomes.
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
                instruction="Pick a preset (Low / Medium / High risk) to load a mock prompt and context.",
                what_to_expect="The prompt and context fields populate automatically.",
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
                what_to_expect="Notice how different modes affect the enforcement outcome (PASS vs FAIL vs WARN).",
                completion_key="lab1_last_artifact",
            ),
        ],
        glossary={
            "Risk Factor": "A named condition (e.g. no_output_schema) with a weight. Triggered = contributes its weight to the total score.",
            "Threshold": "Score above this value triggers the mode's enforcement action.",
            "strict": "Score > threshold = FAIL. No tolerance.",
            "risk_scored": "Score > threshold = FAIL with risk evidence. Scores at/below pass.",
            "warn_only": "Score is recorded but never blocks enforcement.",
        },
    )


# ---------------------------------------------------------------------------
# Main render
# ---------------------------------------------------------------------------
def render() -> None:
    st.header("Lab 1: Risk Scoring Engine")
    st.caption(
        "Adjust risk mode and scenarios to see how the same invocation produces "
        "different enforcement outcomes."
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

    # -- Load scenario + policy -------------------------------------------
    scenario = get_scenario(scenario_name)
    policy_path = sample_policy_path("medical_ai.yaml")
    raw_policy, parsed_policy = load_policy_text(policy_path)

    # Override risk mode in the policy text for display
    if parsed_policy:
        parsed_policy.setdefault("risk", {})["mode"] = mode

    # -- Two columns: config | results ------------------------------------
    config_col, result_col = st.columns(2)

    with config_col:
        st.subheader("Configuration")

        # Show the active policy
        with st.expander("Policy YAML", expanded=False):
            if parsed_policy:
                st.code(yaml.dump(parsed_policy, default_flow_style=False), language="yaml")

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
            _run_enforcement(policy_path, scenario, mode)

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

            render_artifact(artifact, expanded=True)
        else:
            st.info("Run enforcement to see results here.")


# ---------------------------------------------------------------------------
# Enforcement execution
# ---------------------------------------------------------------------------
def _run_enforcement(policy_path: str, scenario: dict, mode: str) -> None:
    """Execute enforcement with the given scenario and risk mode."""
    try:
        aigc = get_aigc(
            risk_config={"mode": mode, "threshold": 0.7, "factors": _medical_factors()},
        )

        invocation = (
            InvocationBuilder()
            .policy(policy_path)
            .model("mock", "mock-model")
            .role("doctor")
            .input({"query": scenario["prompt"]})
            .output(scenario["output"])
            .context(scenario["context"])
            .build()
        )

        artifact = aigc.enforce(invocation)
        st.session_state["lab1_last_artifact"] = artifact
        st.success("Enforcement PASSED")

    except AIGCError as exc:
        artifact = getattr(exc, "audit_artifact", None)
        if artifact:
            st.session_state["lab1_last_artifact"] = artifact
        st.error(f"Enforcement FAILED: {exc}")


def _medical_factors() -> list[dict]:
    """Return the risk factors matching medical_ai.yaml."""
    return [
        {"name": "no_output_schema", "weight": 0.15, "condition": "no_output_schema"},
        {"name": "broad_roles", "weight": 0.15, "condition": "broad_roles"},
        {"name": "missing_guards", "weight": 0.2, "condition": "missing_guards"},
        {"name": "external_model", "weight": 0.3, "condition": "external_model"},
        {"name": "no_preconditions", "weight": 0.2, "condition": "no_preconditions"},
    ]
