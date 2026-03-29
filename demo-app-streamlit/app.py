"""AIGC Governance Lab — Milestone 2 Demo App.

Entry point and navigation shell.  Run with:
    cd demo-app-streamlit && streamlit run app.py
"""

from __future__ import annotations

import importlib

import streamlit as st

from shared.state import init_state

# ---------------------------------------------------------------------------
# Page config (must be first Streamlit call)
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="AIGC Governance Lab",
    page_icon="\U0001f6e1\ufe0f",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Session state bootstrap
# ---------------------------------------------------------------------------
init_state()

# ---------------------------------------------------------------------------
# Lab registry
# ---------------------------------------------------------------------------
LABS: dict[str, tuple[str, str]] = {
    "lab1": ("1. Risk Scoring", "labs.lab1_risk_scoring"),
    "lab2": ("2. Signing & Verification", "labs.lab2_signing"),
    "lab3": ("3. Audit Chain", "labs.lab3_chain"),
    "lab4": ("4. Policy Composition", "labs.lab4_composition"),
    "lab5": ("5. Loaders & Versioning", "labs.lab5_loaders"),
    "lab6": ("6. Custom Gates", "labs.lab6_custom_gates"),
    "lab7": ("7. Compliance Dashboard", "labs.lab7_compliance"),
}

# ---------------------------------------------------------------------------
# Sidebar — navigation + global config
# ---------------------------------------------------------------------------
with st.sidebar:
    st.title("AIGC Governance Lab")
    st.caption("v0.3.0 — Milestone 2 Demo")
    st.divider()

    for key, (label, _) in LABS.items():
        is_active = st.session_state.current_lab == key
        if st.button(
            label,
            key=f"nav_{key}",
            use_container_width=True,
            type="primary" if is_active else "secondary",
        ):
            st.session_state.current_lab = key
            st.rerun()

    st.divider()

    # -- Global audit stats ------------------------------------------------
    history = st.session_state.audit_history
    if history:
        pass_count = sum(1 for a in history if a.get("enforcement_result") == "PASS")
        fail_count = len(history) - pass_count
        st.metric("Total Audits", len(history))
        col_p, col_f = st.columns(2)
        col_p.metric("PASS", pass_count)
        col_f.metric("FAIL", fail_count)
    else:
        st.caption("No audit artifacts yet. Run a lab to generate some.")

    st.divider()
    st.caption("Mode: Mock (no API tokens)")

# ---------------------------------------------------------------------------
# Main content — render selected lab with optional guide rail
# ---------------------------------------------------------------------------
current = st.session_state.current_lab
_, module_path = LABS[current]
module = importlib.import_module(module_path)

# Lab 7 uses full width; all others get 75/25 split with guide rail
if current == "lab7" or not hasattr(module, "get_guide"):
    module.render()
else:
    from shared.guide_rail import render_lab_guide

    lab_col, guide_col = st.columns([3, 1])
    with lab_col:
        module.render()
    with guide_col:
        render_lab_guide(module.get_guide())
