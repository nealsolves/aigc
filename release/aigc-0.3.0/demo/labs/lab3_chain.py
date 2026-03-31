"""Lab 3: Tamper-Evident Audit Chain.

Demonstrates hash-chained audit artifacts:
  - Build a chain by running enforcement multiple times
  - Verify chain integrity
  - Tamper with a link and see where the chain breaks
  - Export the chain as JSON
"""

from __future__ import annotations

import copy
import json
from typing import Any

import streamlit as st

from aigc import InvocationBuilder, AuditChain, AIGCError

from shared.state import get_aigc, sample_policy_path
from shared.ai_client import get_scenario, list_scenarios
from shared.artifact_display import render_artifact
from shared.guide_rail import LabGuide, GuideStep


# ---------------------------------------------------------------------------
# Guide rail
# ---------------------------------------------------------------------------
def get_guide() -> LabGuide:
    return LabGuide(
        lab_id="lab3",
        title="Tamper-Evident Audit Chain",
        overview="Build a hash-linked chain of artifacts and prove tamper detection.",
        mode="iterative",
        iteration_target=5,
        iterative_steps=[
            GuideStep(
                title="Run enforcement",
                instruction='Click "Run & Append" to enforce and add an artifact to the chain.',
                what_to_expect="A new link appears in the chain visualization.",
            ),
            GuideStep(
                title="Inspect the link",
                instruction="Observe how each link references the previous checksum.",
                what_to_expect="The chain forms a linked list of audit evidence.",
            ),
            GuideStep(
                title="Verify integrity",
                instruction='Click "Verify Chain" to check all links.',
                what_to_expect="Green = intact. Red = tampered.",
            ),
        ],
        glossary={
            "Chain": "A sequence of artifacts where each references the hash of the previous one.",
            "Genesis Link": "The first artifact in a chain (previous_audit_checksum = null).",
            "Tamper Detection": "Modifying any artifact breaks the hash link from that point forward.",
        },
    )


# ---------------------------------------------------------------------------
# Main render
# ---------------------------------------------------------------------------
def render() -> None:
    st.header("Lab 3: Tamper-Evident Audit Chain")
    st.caption(
        "Each enforcement appends to a hash chain. Any modification breaks the "
        "chain from that point forward."
    )

    chain: AuditChain = st.session_state.get("chain", AuditChain())

    # -- Controls ----------------------------------------------------------
    ctrl1, ctrl2, ctrl3, ctrl4 = st.columns(4)

    with ctrl1:
        if st.button("Run & Append", type="primary", use_container_width=True):
            _run_and_append()
            st.rerun()

    with ctrl2:
        if st.button("Verify Chain", use_container_width=True):
            _verify_chain()

    with ctrl3:
        tamper_idx = st.number_input(
            "Tamper link #",
            min_value=0,
            max_value=max(0, chain.length - 1),
            value=0,
            key="lab3_tamper_idx",
        )
        if st.button("Tamper", use_container_width=True):
            _tamper_link(int(tamper_idx))
            st.rerun()

    with ctrl4:
        if st.button("Reset Chain", use_container_width=True):
            st.session_state["chain"] = AuditChain()
            st.session_state["lab3_chain_verified"] = None
            st.rerun()

    # -- Chain stats -------------------------------------------------------
    st.divider()
    stats1, stats2, stats3 = st.columns(3)
    stats1.metric("Chain Length", chain.length)
    stats2.metric("Chain ID", chain.chain_id[:12] + "...")
    verified = st.session_state.get("lab3_chain_verified")
    if verified is not None:
        valid, errors = verified
        stats3.metric("Integrity", "INTACT" if valid else "BROKEN")
    else:
        stats3.metric("Integrity", "Not checked")

    # -- Verification errors -----------------------------------------------
    if verified is not None:
        valid, errors = verified
        if valid:
            st.success("Chain integrity verified — all links intact.")
        else:
            st.error(f"Chain BROKEN — {len(errors)} error(s):")
            for err in errors:
                st.markdown(f"- {err}")

    # -- Chain visualization -----------------------------------------------
    st.divider()
    st.subheader("Chain Links")

    if chain.length == 0:
        st.info('Click "Run & Append" to start building the chain.')
    else:
        _render_chain_visual(chain)

    # -- Export ------------------------------------------------------------
    if chain.length > 0:
        st.divider()
        chain_data = []
        for a in chain._artifacts:
            chain_data.append(a)
        export_json = json.dumps(chain_data, indent=2, default=str)
        st.download_button(
            "Export Chain (JSON)",
            data=export_json,
            file_name="audit_chain.json",
            mime="application/json",
        )


# ---------------------------------------------------------------------------
# Chain visual
# ---------------------------------------------------------------------------
def _render_chain_visual(chain: AuditChain) -> None:
    """Render chain as a horizontal sequence of linked cards."""
    artifacts = chain._artifacts

    for i, artifact in enumerate(artifacts):
        checksum = artifact.get("checksum", "—")
        prev = artifact.get("previous_audit_checksum")
        result = artifact.get("enforcement_result", "?")
        color = "#22c55e" if result == "PASS" else "#ef4444"

        with st.container(border=True):
            cols = st.columns([1, 4])
            with cols[0]:
                st.markdown(f"### #{i}")
            with cols[1]:
                st.markdown(f"**Result:** :{('green' if result == 'PASS' else 'red')}[{result}]")
                st.caption(f"Checksum: `{checksum[:16]}...`")
                st.caption(f"Prev: `{(prev[:16] + '...') if prev else 'null (genesis)'}`")

        if i < len(artifacts) - 1:
            st.markdown(
                "<div style='text-align:center; font-size:20px; color:#888;'>&#x2193;</div>",
                unsafe_allow_html=True,
            )


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------
def _run_and_append() -> None:
    """Enforce and then append the artifact to the chain."""
    chain: AuditChain = st.session_state.get("chain", AuditChain())
    chain_scenarios = list_scenarios("chain_entry_")
    idx = chain.length % len(chain_scenarios) if chain_scenarios else 0
    scenario_name = chain_scenarios[idx] if chain_scenarios else "signing_basic"
    scenario = get_scenario(scenario_name)

    policy_path = sample_policy_path("medical_ai.yaml")

    try:
        aigc = get_aigc()
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
        # Append to chain AFTER enforcement (chain is standalone)
        chain.append(artifact)
        st.session_state["lab3_chain_verified"] = None  # reset verification
    except AIGCError as exc:
        st.error(f"Enforcement failed: {exc}")


def _verify_chain() -> None:
    """Verify the current chain."""
    chain: AuditChain = st.session_state.get("chain", AuditChain())
    result = chain.verify()
    st.session_state["lab3_chain_verified"] = result


def _tamper_link(index: int) -> None:
    """Tamper with a specific chain link."""
    chain: AuditChain = st.session_state.get("chain", AuditChain())
    if index >= chain.length:
        st.error(f"Link #{index} doesn't exist.")
        return

    # Directly modify the artifact in the chain's internal list
    artifact = chain._artifacts[index]
    current = artifact.get("enforcement_result", "PASS")
    artifact["enforcement_result"] = "FAIL" if current == "PASS" else "PASS"
    st.session_state["lab3_chain_verified"] = None
    st.warning(f"Tampered with link #{index} — enforcement_result flipped.")
