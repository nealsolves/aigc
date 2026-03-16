"""Lab 5: Pluggable Loaders, Versioning & Policy Testing.

Three tabs:
  1. Loaders    — FileSystem vs InMemory policy loading
  2. Versioning — effective_date / expiration_date validation with date picker
  3. Testing    — PolicyTestCase runner with pass/fail results
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Any

import yaml
import streamlit as st

from aigc import (
    InvocationBuilder,
    AIGCError,
    PolicyValidationError,
    FilePolicyLoader,
)
from aigc._internal.policy_loader import load_policy, validate_policy_dates
from aigc._internal.policy_testing import PolicyTestCase, PolicyTestSuite, expect_pass, expect_fail

from shared.state import get_aigc, sample_policy_path, SAMPLE_POLICIES_DIR
from shared.policy_editor import render_policy_editor, render_policy_selector, load_policy_text
from shared.guide_rail import LabGuide, GuideWorkflow, GuideStep


# ---------------------------------------------------------------------------
# Guide rail
# ---------------------------------------------------------------------------
def get_guide() -> LabGuide:
    return LabGuide(
        lab_id="lab5",
        title="Loaders, Versioning & Testing",
        overview="Load policies from different sources, validate date ranges, and run policy tests.",
        mode="workflows",
        workflows=[
            GuideWorkflow(
                name="Policy Loaders",
                description="Load policies from filesystem or define them in-memory.",
                steps=[
                    GuideStep(
                        title="Select a loader",
                        instruction="Pick FileSystem or InMemory from the dropdown.",
                        what_to_expect="FileSystem loads from disk. InMemory lets you define policies inline.",
                    ),
                    GuideStep(
                        title="Load a policy",
                        instruction='Click "Load Policy" to parse and display it.',
                        what_to_expect="The parsed policy appears below.",
                    ),
                ],
            ),
            GuideWorkflow(
                name="Policy Versioning",
                description="Set effective/expiration dates and validate against a reference date.",
                steps=[
                    GuideStep(
                        title="Set dates on a policy",
                        instruction="Edit the effective_date and expiration_date fields.",
                        what_to_expect="The policy becomes time-bounded.",
                    ),
                    GuideStep(
                        title="Pick a reference date",
                        instruction="Use the date picker to simulate checking on a different day.",
                        what_to_expect="See if the policy is valid, expired, or not yet effective.",
                    ),
                ],
            ),
            GuideWorkflow(
                name="Policy Testing",
                description="Run pre-built test cases against a policy.",
                steps=[
                    GuideStep(
                        title="Select a policy",
                        instruction="Choose a sample policy to test.",
                        what_to_expect="Test cases are pre-configured for the selected policy.",
                    ),
                    GuideStep(
                        title="Run tests",
                        instruction='Click "Run Tests" to execute the suite.',
                        what_to_expect="Green dots for passes, red Fs for failures.",
                    ),
                ],
            ),
        ],
        glossary={
            "PolicyLoaderBase": "Abstract interface for loading policies from any source.",
            "FilePolicyLoader": "Default loader — reads YAML files from disk.",
            "InMemoryLoader": "Loads policies from a Python dict. Useful for testing.",
            "effective_date": "Policy is not valid before this date.",
            "expiration_date": "Policy is not valid after this date.",
        },
    )


# ---------------------------------------------------------------------------
# Main render
# ---------------------------------------------------------------------------
def render() -> None:
    st.header("Lab 5: Loaders, Versioning & Testing")

    tab_loader, tab_version, tab_testing = st.tabs([
        "Policy Loaders",
        "Versioning",
        "Policy Testing",
    ])

    with tab_loader:
        _render_loader_tab()

    with tab_version:
        _render_versioning_tab()

    with tab_testing:
        _render_testing_tab()


# ---------------------------------------------------------------------------
# Tab 1: Loaders
# ---------------------------------------------------------------------------
def _render_loader_tab() -> None:
    st.subheader("Policy Loaders")
    loader_type = st.selectbox(
        "Loader Type",
        ["FileSystem", "InMemory"],
        key="lab5_loader_type",
    )

    if loader_type == "FileSystem":
        path = render_policy_selector(key="lab5_fs_selector")
        if path and st.button("Load Policy", key="lab5_fs_load"):
            try:
                parsed = load_policy(path)
                st.session_state["lab5_loaded_policy"] = parsed
                st.success(f"Loaded: {Path(path).name}")
            except Exception as exc:
                st.error(f"Load failed: {exc}")

    else:  # InMemory
        default_yaml = (
            'policy_version: "1.0"\n'
            "roles:\n"
            "  - analyst\n"
            "  - reviewer\n"
            "pre_conditions:\n"
            "  required:\n"
            "    role_declared:\n"
            '      type: "boolean"\n'
            "    schema_exists:\n"
            '      type: "boolean"\n'
            "output_schema:\n"
            "  type: object\n"
            "  properties:\n"
            "    result:\n"
            "      type: string\n"
            "  required:\n"
            "    - result\n"
        )
        parsed = render_policy_editor(
            default_policy=default_yaml,
            key="lab5_inmemory_editor",
            label="Define policy inline",
        )
        if parsed:
            st.session_state["lab5_loaded_policy"] = parsed
            st.success("In-memory policy loaded.")

    # Display loaded policy
    loaded = st.session_state.get("lab5_loaded_policy")
    if loaded:
        with st.expander("Parsed Policy", expanded=True):
            st.json(loaded)


# ---------------------------------------------------------------------------
# Tab 2: Versioning
# ---------------------------------------------------------------------------
def _render_versioning_tab() -> None:
    st.subheader("Policy Versioning")
    st.caption(
        "Policies can have effective_date and expiration_date. "
        "Enforcement rejects expired or not-yet-effective policies."
    )

    col1, col2 = st.columns(2)
    with col1:
        eff_date = st.date_input(
            "effective_date",
            value=date(2026, 1, 1),
            key="lab5_eff_date",
        )
    with col2:
        exp_date = st.date_input(
            "expiration_date",
            value=date(2026, 12, 31),
            key="lab5_exp_date",
        )

    ref_date = st.date_input(
        "Reference date (simulate 'today')",
        value=date.today(),
        key="lab5_ref_date",
    )

    # Build a minimal policy with dates
    test_policy: dict[str, Any] = {
        "policy_version": "1.0",
        "roles": ["analyst"],
        "effective_date": str(eff_date),
        "expiration_date": str(exp_date),
    }

    if st.button("Validate Version", type="primary", key="lab5_validate_version"):
        try:
            result = validate_policy_dates(
                test_policy,
                clock=lambda: ref_date,
            )
            st.session_state["lab5_version_result"] = ("valid", None)
            st.success(
                f"Policy is VALID on {ref_date} "
                f"(effective {eff_date} — {exp_date})."
            )
        except PolicyValidationError as exc:
            st.session_state["lab5_version_result"] = ("invalid", str(exc))
            st.error(f"Policy is NOT VALID on {ref_date}: {exc}")

    # Visual timeline
    _render_timeline(eff_date, exp_date, ref_date)


def _render_timeline(eff: date, exp: date, ref: date) -> None:
    """Render a simple visual timeline bar."""
    total_days = (exp - eff).days or 1
    ref_days = (ref - eff).days
    pct = max(0, min(100, int(ref_days / total_days * 100)))

    in_range = eff <= ref <= exp
    color = "#22c55e" if in_range else "#ef4444"

    html = f"""
    <div style="margin:16px 0;">
      <div style="display:flex; justify-content:space-between; font-size:11px; color:#888;">
        <span>{eff}</span>
        <span>ref: {ref}</span>
        <span>{exp}</span>
      </div>
      <div style="position:relative; height:16px; background:#e5e7eb; border-radius:4px;">
        <div style="position:absolute; left:{pct}%; top:-2px; height:20px;
             width:3px; background:{color}; border-radius:2px;"></div>
      </div>
    </div>
    """
    st.html(html)


# ---------------------------------------------------------------------------
# Tab 3: Policy Testing
# ---------------------------------------------------------------------------
def _render_testing_tab() -> None:
    st.subheader("Policy Testing Framework")
    st.caption(
        "Define test cases for your policies and run them as a suite."
    )

    policy_path = render_policy_selector(key="lab5_test_policy_selector")

    if not policy_path:
        return

    st.divider()
    st.markdown("**Pre-built test cases:**")

    # Build test suite based on the selected policy
    raw, parsed = load_policy_text(policy_path)
    if not parsed:
        st.error("Could not parse selected policy.")
        return

    roles = parsed.get("roles", ["planner"])
    first_role = roles[0] if roles else "planner"

    suite = PolicyTestSuite(name=f"Tests for {Path(policy_path).name}")

    # Test 1: valid role should pass
    case_pass = PolicyTestCase(
        name=f"Valid role ({first_role}) passes",
        policy_file=policy_path,
        role=first_role,
        input_data={"query": "test query"},
        output_data={"result": "test result"},
        context={"role_declared": True, "schema_exists": True},
    )
    suite.add(case_pass, expected="pass")

    # Test 2: unauthorized role should fail
    case_fail_role = PolicyTestCase(
        name="Unauthorized role (intruder) fails",
        policy_file=policy_path,
        role="intruder",
        input_data={"query": "test"},
        output_data={"result": "test"},
        context={"role_declared": True, "schema_exists": True},
    )
    suite.add(case_fail_role, expected="fail")

    # Test 3: missing precondition
    case_fail_pre = PolicyTestCase(
        name="Missing precondition (schema_exists=False) fails",
        policy_file=policy_path,
        role=first_role,
        input_data={"query": "test"},
        output_data={"result": "test"},
        context={"role_declared": True, "schema_exists": False},
    )
    suite.add(case_fail_pre, expected="fail")

    # Display test cases
    for i, (case, expected) in enumerate(zip(
        [case_pass, case_fail_role, case_fail_pre],
        ["PASS", "FAIL", "FAIL"],
    )):
        st.markdown(f"{i+1}. **{case.name}** — expected: {expected}")

    st.divider()

    if st.button("Run Tests", type="primary", key="lab5_run_tests"):
        results = suite.run_all()
        st.session_state["lab5_test_results"] = (results, suite)

    # Display results
    stored = st.session_state.get("lab5_test_results")
    if stored:
        test_results, test_suite = stored
        st.divider()

        # Map expected outcomes for display
        expected_map = {case_pass.name: "PASS", case_fail_role.name: "FAIL", case_fail_pre.name: "FAIL"}

        for r in test_results:
            expected = expected_map.get(r.name, "?")
            actual = r.enforcement_result
            met = (expected == actual)
            icon = "\u2705" if met else "\u274c"
            st.markdown(f"{icon} **{r.name}** — expected: {expected}, got: {actual}")
            if r.error:
                st.caption(f"Gate: {r.failure_gate} | {r.error}")

        if test_suite.all_passed(test_results):
            st.success("All tests met expectations.")
        else:
            st.warning("Some tests did not meet expectations.")
