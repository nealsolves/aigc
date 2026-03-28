"""Lab 6: Custom Enforcement Gates.

Demonstrates the custom gate plugin system with predefined gate recipes.
No code editor — users pick from pre-built gates, register them, run
enforcement, and see the gate appear in gates_evaluated.

Recipes:
  1. Confidence Gate (pre_output)  — fails if output.confidence < 0.5
  2. PII Detection Gate (post_output) — fails if output contains email/phone
  3. Response Length Gate (pre_output) — fails if output > 500 chars
  4. Audit Metadata Gate (post_output) — always passes, injects metadata
"""

from __future__ import annotations

import re
from typing import Any, Mapping

import streamlit as st

from aigc import (
    EnforcementGate,
    GateResult,
    InvocationBuilder,
    AIGCError,
)

from shared.state import get_aigc, sample_policy_path
from shared.ai_client import get_scenario, list_scenarios
from shared.artifact_display import render_artifact
from shared.guide_rail import LabGuide, GuideRecipe


# ---------------------------------------------------------------------------
# Gate recipes — real EnforcementGate subclasses
# ---------------------------------------------------------------------------

class ConfidenceGate(EnforcementGate):
    """Fails if output.confidence < 0.5."""

    @property
    def name(self) -> str:
        return "confidence_gate"

    @property
    def insertion_point(self) -> str:
        return "pre_output"

    def evaluate(
        self,
        invocation: Mapping[str, Any],
        policy: Mapping[str, Any],
        context: dict[str, Any],
    ) -> GateResult:
        output = invocation.get("output", {})
        confidence = output.get("confidence", 1.0)
        if confidence < 0.5:
            return GateResult(
                passed=False,
                failures=[{
                    "gate": self.name,
                    "message": f"Output confidence {confidence:.2f} is below 0.5 threshold",
                }],
            )
        return GateResult(passed=True, metadata={"confidence": confidence})


class PIIDetectionGate(EnforcementGate):
    """Fails if output contains email or phone patterns."""

    _EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
    _PHONE_RE = re.compile(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b")
    _SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")

    @property
    def name(self) -> str:
        return "pii_detection_gate"

    @property
    def insertion_point(self) -> str:
        return "post_output"

    def evaluate(
        self,
        invocation: Mapping[str, Any],
        policy: Mapping[str, Any],
        context: dict[str, Any],
    ) -> GateResult:
        output = invocation.get("output", {})
        text = str(output.get("result", ""))

        found: list[str] = []
        if self._EMAIL_RE.search(text):
            found.append("email address")
        if self._PHONE_RE.search(text):
            found.append("phone number")
        if self._SSN_RE.search(text):
            found.append("SSN")

        if found:
            return GateResult(
                passed=False,
                failures=[{
                    "gate": self.name,
                    "message": f"PII detected in output: {', '.join(found)}",
                }],
                metadata={"pii_types": found},
            )
        return GateResult(passed=True, metadata={"pii_scan": "clean"})


class ResponseLengthGate(EnforcementGate):
    """Fails if output result exceeds 500 characters."""

    @property
    def name(self) -> str:
        return "response_length_gate"

    @property
    def insertion_point(self) -> str:
        return "pre_output"

    def evaluate(
        self,
        invocation: Mapping[str, Any],
        policy: Mapping[str, Any],
        context: dict[str, Any],
    ) -> GateResult:
        output = invocation.get("output", {})
        text = str(output.get("result", ""))
        if len(text) > 500:
            return GateResult(
                passed=False,
                failures=[{
                    "gate": self.name,
                    "message": f"Response length {len(text)} exceeds 500 char limit",
                }],
            )
        return GateResult(passed=True, metadata={"response_length": len(text)})


class AuditMetadataGate(EnforcementGate):
    """Always passes — injects custom metadata into the pipeline context."""

    @property
    def name(self) -> str:
        return "audit_metadata_gate"

    @property
    def insertion_point(self) -> str:
        return "post_output"

    def evaluate(
        self,
        invocation: Mapping[str, Any],
        policy: Mapping[str, Any],
        context: dict[str, Any],
    ) -> GateResult:
        return GateResult(
            passed=True,
            metadata={
                "custom_tag": "demo_audit",
                "reviewed_by": "aigc_lab6",
            },
        )


# Registry of available gate instances
GATE_RECIPES: dict[str, tuple[EnforcementGate, str, str]] = {
    "Confidence Gate": (
        ConfidenceGate(),
        "Fails if output.confidence < 0.5. Insertion: pre_output.",
        "GateResult with pass/fail, EnforcementGate.evaluate(), short-circuit on failure",
    ),
    "PII Detection Gate": (
        PIIDetectionGate(),
        "Scans output for emails, phones, SSNs. Insertion: post_output.",
        "Regex-based content inspection, GateResult.failures with evidence",
    ),
    "Response Length Gate": (
        ResponseLengthGate(),
        "Fails if output result > 500 characters. Insertion: pre_output.",
        "Simple threshold check, metadata injection for passing results",
    ),
    "Audit Metadata Gate": (
        AuditMetadataGate(),
        "Always passes — injects custom metadata. Insertion: post_output.",
        "Non-blocking gates, metadata propagation through pipeline",
    ),
}


# ---------------------------------------------------------------------------
# Guide rail
# ---------------------------------------------------------------------------
def get_guide() -> LabGuide:
    return LabGuide(
        lab_id="lab6",
        title="Custom Enforcement Gates",
        overview="Register pre-built gate plugins and see them execute in the pipeline.",
        mode="cookbook",
        recipes=[
            GuideRecipe(
                name=name,
                description=desc,
                code=_get_source(gate),
                what_it_demonstrates=demonstrates,
            )
            for name, (gate, desc, demonstrates) in GATE_RECIPES.items()
        ],
        glossary={
            "EnforcementGate": "Abstract base class for custom pipeline gates.",
            "GateResult": "Return value from evaluate(). Has passed, failures, metadata.",
            "insertion_point": "Where the gate runs: pre_authorization, post_authorization, pre_output, post_output.",
            "Short-circuit": "A failing gate stops the pipeline immediately (same as core gates).",
        },
    )


def _get_source(gate: EnforcementGate) -> str:
    """Return a readable source representation of a gate class."""
    import inspect
    try:
        return inspect.getsource(type(gate))
    except (TypeError, OSError):
        return f"# Source unavailable for {type(gate).__name__}"


# ---------------------------------------------------------------------------
# Main render
# ---------------------------------------------------------------------------
def render() -> None:
    st.header("Lab 6: Custom Enforcement Gates")
    st.caption(
        "Select a pre-built gate, register it in the pipeline, and run enforcement "
        "to see it appear in gates_evaluated."
    )

    # -- Gate selector -----------------------------------------------------
    selected_name = st.selectbox(
        "Select a Gate Recipe",
        list(GATE_RECIPES.keys()),
        key="lab6_gate_select",
    )

    gate_instance, description, demonstrates = GATE_RECIPES[selected_name]

    st.info(f"**{selected_name}** — {description}")
    st.caption(f"Demonstrates: {demonstrates}")

    # Show source code
    with st.expander("Gate Source Code"):
        st.code(_get_source(gate_instance), language="python")

    # -- Pipeline visualization --------------------------------------------
    st.divider()
    st.subheader("Pipeline with Custom Gate")
    _render_pipeline(gate_instance)

    # -- Scenario selector -------------------------------------------------
    st.divider()
    st.subheader("Test Run")

    # Pick a scenario that exercises this gate
    if selected_name == "Confidence Gate":
        scenarios = ["gate_high_confidence", "gate_low_confidence"]
    elif selected_name == "PII Detection Gate":
        scenarios = ["gate_pii_present", "gate_clean_output"]
    else:
        scenarios = ["gate_high_confidence", "gate_clean_output"]

    scenario_name = st.radio(
        "Scenario",
        scenarios,
        format_func=lambda s: s.replace("gate_", "").replace("_", " ").title(),
        horizontal=True,
        key="lab6_scenario",
        on_change=lambda: st.session_state.pop("lab6_last_artifact", None),
    )

    if st.button("Run with Custom Gate", type="primary", use_container_width=True):
        _run_with_gate(gate_instance, scenario_name)

    # -- Results -----------------------------------------------------------
    artifact = st.session_state.get("lab6_last_artifact")
    if artifact:
        st.divider()
        render_artifact(artifact, expanded=True)

        # Highlight custom gate in gates_evaluated
        # Custom gates appear as "custom:<gate_name>" in the pipeline
        gates = artifact.get("metadata", {}).get("gates_evaluated", [])
        custom_gate_id = f"custom:{gate_instance.name}"
        matching = [g for g in gates if gate_instance.name in g]
        if matching:
            gate_label = matching[0]
            pos = gates.index(gate_label) + 1
            st.success(f"Custom gate '{gate_label}' executed at position {pos} of {len(gates)}.")
        else:
            st.caption("Custom gate not found in gates_evaluated (may have been short-circuited by an earlier gate).")


# ---------------------------------------------------------------------------
# Pipeline visualization
# ---------------------------------------------------------------------------
def _render_pipeline(custom_gate: EnforcementGate) -> None:
    """Show the pipeline stages with the custom gate inserted at its actual position."""
    stages = [
        ("guard_evaluation", "core"),
        ("role_validation", "core"),
        ("precondition_validation", "core"),
        ("tool_constraint_validation", "core"),
        ("schema_validation", "core"),
        ("postcondition_validation", "core"),
        ("risk_scoring", "core"),
    ]

    # Build full pipeline with custom gate inserted at correct position
    insertion = custom_gate.insertion_point
    if insertion == "pre_authorization":
        # pre_auth runs before all core gates
        full_pipeline = [(custom_gate.name, "custom")] + stages
    else:
        if insertion == "post_authorization":
            insert_after = "tool_constraint_validation"
        elif insertion == "pre_output":
            insert_after = "tool_constraint_validation"
        else:  # post_output
            insert_after = "postcondition_validation"

        full_pipeline = []
        for stage_name, stage_type in stages:
            full_pipeline.append((stage_name, stage_type))
            if stage_name == insert_after:
                full_pipeline.append((custom_gate.name, "custom"))

    # Render
    for stage_name, stage_type in full_pipeline:
        color = "#7c3aed" if stage_type == "custom" else "#3b82f6"
        label = f"**{stage_name}**" if stage_type == "custom" else stage_name
        st.markdown(
            f'<div style="padding:6px 12px; margin:2px 0; background:{color}20; '
            f'border-left:4px solid {color}; border-radius:4px; font-size:14px;">'
            f'{"[CUSTOM] " if stage_type == "custom" else ""}{stage_name}</div>',
            unsafe_allow_html=True,
        )


# ---------------------------------------------------------------------------
# Enforcement
# ---------------------------------------------------------------------------
def _run_with_gate(gate: EnforcementGate, scenario_name: str) -> None:
    """Run enforcement with the custom gate registered."""
    scenario = get_scenario(scenario_name)
    policy_path = sample_policy_path("medical_ai.yaml")

    try:
        aigc = get_aigc(custom_gates=[gate])
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
        st.session_state["lab6_last_artifact"] = artifact
        st.success("Enforcement PASSED (with custom gate)")
    except AIGCError as exc:
        artifact = getattr(exc, "audit_artifact", None)
        if artifact:
            st.session_state["lab6_last_artifact"] = artifact
        st.error(f"Enforcement FAILED: {exc}")
