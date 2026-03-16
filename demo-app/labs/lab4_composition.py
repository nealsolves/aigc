"""Lab 4: Policy Composition with Restriction Semantics.

Demonstrates:
  - Loading a base policy and a child policy
  - Composing them with intersect / union / replace strategies
  - Visualising what changed (roles gained/lost, tools restricted)
  - Detecting privilege escalation
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
import streamlit as st

from aigc import PolicyValidationError
from aigc.policy_loader import (
    load_policy,
    merge_policies,
    COMPOSITION_INTERSECT,
    COMPOSITION_UNION,
    COMPOSITION_REPLACE,
)

from shared.state import sample_policy_path
from shared.policy_editor import render_policy_editor, load_policy_text
from shared.guide_rail import LabGuide, GuideStep


# ---------------------------------------------------------------------------
# Guide rail
# ---------------------------------------------------------------------------
def get_guide() -> LabGuide:
    return LabGuide(
        lab_id="lab4",
        title="Policy Composition",
        overview="Compose parent and child policies and see how merge strategies control privilege.",
        mode="linear",
        steps=[
            GuideStep(
                title="Load base policy",
                instruction="The base policy (medical_ai.yaml) is pre-loaded on the left.",
                what_to_expect="Roles: doctor, nurse, admin, researcher. Tools: search_medical_db, lookup_drug_interaction.",
                completion_key="lab4_base_loaded",
            ),
            GuideStep(
                title="Load child policy",
                instruction="The child policy (medical_ai_child.yaml) is pre-loaded on the right.",
                what_to_expect='Child requests only "nurse" role and fewer tools.',
                completion_key="lab4_child_loaded",
            ),
            GuideStep(
                title="Choose a strategy",
                instruction="Select intersect, union, or replace to see how composition behaves.",
                what_to_expect="Intersect restricts. Union extends. Replace overwrites.",
                completion_key="lab4_strategy_set",
            ),
            GuideStep(
                title="Compose",
                instruction='Click "Compose Policies" to merge base + child.',
                what_to_expect="The effective policy appears below with a diff summary.",
                completion_key="lab4_composed_policy",
            ),
        ],
        glossary={
            "intersect": "Result is the overlap of base and child. Can only restrict.",
            "union": "Result is the combination of base and child. Can extend privileges.",
            "replace": "Child completely overwrites the base value.",
            "Escalation": "A child policy gaining privileges not present in the parent.",
        },
    )


# ---------------------------------------------------------------------------
# Main render
# ---------------------------------------------------------------------------
def render() -> None:
    st.header("Lab 4: Policy Composition")
    st.caption(
        "See how merge strategies (intersect / union / replace) control what "
        "a child policy can and cannot do."
    )

    # -- Load policies -----------------------------------------------------
    base_path = sample_policy_path("medical_ai.yaml")
    child_path = sample_policy_path("medical_ai_child.yaml")

    base_raw, base_parsed = load_policy_text(base_path)
    child_raw, child_parsed = load_policy_text(child_path)

    st.session_state["lab4_base_loaded"] = True
    st.session_state["lab4_child_loaded"] = True

    # -- Side-by-side editors ---------------------------------------------
    base_col, child_col = st.columns(2)

    with base_col:
        st.subheader("Base Policy")
        edited_base = render_policy_editor(
            default_policy=base_raw,
            key="lab4_base_editor",
            label="Base Policy (medical_ai.yaml)",
            height=250,
        )

    with child_col:
        st.subheader("Child Policy")
        edited_child = render_policy_editor(
            default_policy=child_raw,
            key="lab4_child_editor",
            label="Child Policy (medical_ai_child.yaml)",
            height=250,
        )

    # -- Strategy selector -------------------------------------------------
    st.divider()
    strategy = st.radio(
        "Composition Strategy",
        ["intersect", "union", "replace"],
        horizontal=True,
        key="lab4_strategy",
    )
    st.session_state["lab4_strategy_set"] = True

    # -- Compose button ----------------------------------------------------
    if st.button("Compose Policies", type="primary", use_container_width=True):
        _compose(edited_base or base_parsed, edited_child or child_parsed, strategy)

    # -- Results -----------------------------------------------------------
    composed = st.session_state.get("lab4_composed_policy")
    if composed:
        st.divider()
        st.subheader("Effective Policy (after composition)")
        st.code(yaml.dump(composed, default_flow_style=False), language="yaml")

        # Diff summary
        _render_diff(
            edited_base or base_parsed,
            composed,
        )

    # -- Escalation check --------------------------------------------------
    violations = st.session_state.get("lab4_escalation_violations")
    if violations is not None:
        st.divider()
        if violations:
            st.error(f"Privilege escalation detected ({len(violations)} violation(s)):")
            for v in violations:
                st.markdown(f"- {v}")
        else:
            st.success("No privilege escalation — child is a restriction of the base.")


# ---------------------------------------------------------------------------
# Composition logic
# ---------------------------------------------------------------------------
def _compose(
    base: dict[str, Any] | None,
    child: dict[str, Any] | None,
    strategy: str,
) -> None:
    """Compose base + child and store results."""
    if not base or not child:
        st.error("Both base and child policies must be valid YAML.")
        return

    try:
        # Use internal merge with the chosen strategy
        composed = merge_policies(base, child, composition_strategy=strategy)

        # Remove internal keys
        composed.pop("extends", None)
        composed.pop("composition_strategy", None)

        st.session_state["lab4_composed_policy"] = composed

        # Escalation check: composed roles/tools should be subset of base
        violations = _check_escalation(base, composed)
        st.session_state["lab4_escalation_violations"] = violations

    except PolicyValidationError as exc:
        st.error(f"Composition failed: {exc}")
    except Exception as exc:
        st.error(f"Error: {exc}")


def _check_escalation(
    base: dict[str, Any],
    composed: dict[str, Any],
) -> list[str]:
    """Check if composed policy escalates privileges beyond base."""
    violations: list[str] = []

    base_roles = set(base.get("roles", []))
    composed_roles = set(composed.get("roles", []))
    new_roles = composed_roles - base_roles
    if new_roles:
        violations.append(f"New roles not in base: {sorted(new_roles)}")

    base_tools = {t["name"] for t in base.get("tools", {}).get("allowed_tools", [])}
    composed_tools = {t["name"] for t in composed.get("tools", {}).get("allowed_tools", [])}
    new_tools = composed_tools - base_tools
    if new_tools:
        violations.append(f"New tools not in base: {sorted(new_tools)}")

    # Check postconditions not removed
    base_post = set(base.get("post_conditions", {}).get("required", []))
    composed_post = set(composed.get("post_conditions", {}).get("required", []))
    removed_post = base_post - composed_post
    if removed_post:
        violations.append(f"Postconditions removed: {sorted(removed_post)}")

    return violations


# ---------------------------------------------------------------------------
# Diff rendering
# ---------------------------------------------------------------------------
def _render_diff(base: dict[str, Any] | None, composed: dict[str, Any] | None) -> None:
    """Show a summary of what changed between base and composed."""
    if not base or not composed:
        return

    st.subheader("Composition Diff")

    # Roles
    base_roles = set(base.get("roles", []))
    comp_roles = set(composed.get("roles", []))
    kept = base_roles & comp_roles
    removed = base_roles - comp_roles
    added = comp_roles - base_roles

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("**Kept (shared)**")
        for r in sorted(kept):
            st.markdown(f"- :green[{r}]")
    with col2:
        st.markdown("**Removed from base**")
        for r in sorted(removed):
            st.markdown(f"- :blue[{r}]")
    with col3:
        st.markdown("**Added by child**")
        for r in sorted(added):
            st.markdown(f"- :red[{r}]")

    # Tools
    base_tools = {t["name"] for t in base.get("tools", {}).get("allowed_tools", [])}
    comp_tools = {t["name"] for t in composed.get("tools", {}).get("allowed_tools", [])}
    st.caption(f"Tools: base={sorted(base_tools)} -> composed={sorted(comp_tools)}")
