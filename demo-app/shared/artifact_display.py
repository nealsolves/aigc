"""Reusable audit artifact viewer components."""

from __future__ import annotations

import json
from typing import Any

import streamlit as st


# ---------------------------------------------------------------------------
# Main artifact card
# ---------------------------------------------------------------------------
def render_artifact(artifact: dict[str, Any], expanded: bool = False) -> None:
    """Render an audit artifact as a Streamlit expander card.

    Shows PASS/FAIL badge, key fields, and full JSON in a collapsible section.
    """
    result = artifact.get("enforcement_result", "UNKNOWN")
    policy = artifact.get("policy_file", "—")
    role = artifact.get("invocation_summary", {}).get("role", "—")
    checksum = artifact.get("checksum", "—")

    # Badge colour
    badge = "\u2705 PASS" if result == "PASS" else "\u274c FAIL"

    # Use container instead of expander to avoid nested-expander violations
    # when render_artifact is called inside other expanders or columns.
    st.markdown(f"**{badge}** | `{policy}` | role=`{role}`")
    with st.container(border=True):
        # -- Summary row ---------------------------------------------------
        cols = st.columns(4)
        cols[0].metric("Result", result)
        cols[1].metric("Role", role)

        risk_data = artifact.get("metadata", {}).get("risk_scoring")
        if risk_data is not None:
            score_data = risk_data if isinstance(risk_data, dict) else {"score": risk_data}
            cols[2].metric("Risk Score", f"{score_data.get('score', 0):.2f}")
        else:
            cols[2].metric("Risk Score", "N/A")

        signed = artifact.get("signature") is not None
        cols[3].metric("Signed", "Yes" if signed else "No")

        # -- Gates evaluated -----------------------------------------------
        gates = artifact.get("metadata", {}).get("gates_evaluated", [])
        if gates:
            st.caption("Gates evaluated:")
            st.code(" -> ".join(gates), language=None)

        # -- Failures (if FAIL) --------------------------------------------
        failures = artifact.get("failures", [])
        if failures:
            st.error("Failures:")
            for f in failures:
                st.markdown(f"- **{f.get('gate', '?')}**: {f.get('message', '?')}")

        # -- Chain info (if present) ---------------------------------------
        chain_id = artifact.get("chain_id")
        if chain_id:
            st.caption(
                f"Chain: {chain_id[:8]}... | "
                f"Index: {artifact.get('chain_index', '?')} | "
                f"Prev checksum: {_trunc(artifact.get('previous_audit_checksum'))}"
            )

        # -- Checksum ------------------------------------------------------
        st.caption(f"Checksum: `{checksum}`")

        # -- Full JSON -----------------------------------------------------
        with st.expander("Raw JSON", expanded=False):
            st.json(artifact)


# ---------------------------------------------------------------------------
# Risk gauge
# ---------------------------------------------------------------------------
def render_risk_gauge(score: float, threshold: float, mode: str = "") -> None:
    """Render a horizontal risk gauge bar.

    Green zone: 0 to threshold
    Red zone: threshold to 1.0
    Marker at the current score
    """
    pct = max(0.0, min(1.0, score)) * 100
    threshold_pct = max(0.0, min(1.0, threshold)) * 100

    color = "#22c55e" if score <= threshold else "#ef4444"
    mode_label = f" ({mode})" if mode else ""

    html = f"""
    <div style="margin: 8px 0;">
      <div style="display:flex; justify-content:space-between; font-size:12px; color:#888;">
        <span>0.0</span>
        <span>Score: <b style="color:{color}">{score:.2f}</b>{mode_label}</span>
        <span>1.0</span>
      </div>
      <div style="position:relative; height:24px; background:linear-gradient(to right,
           #22c55e 0%, #22c55e {threshold_pct}%,
           #ef4444 {threshold_pct}%, #ef4444 100%);
           border-radius:6px; overflow:hidden;">
        <!-- threshold marker -->
        <div style="position:absolute; left:{threshold_pct}%; top:0; height:100%;
             width:2px; background:#333;"></div>
        <!-- score marker -->
        <div style="position:absolute; left:{pct}%; top:0; height:100%;
             width:4px; background:#1e293b; border-radius:2px;
             transform:translateX(-50%);"></div>
      </div>
      <div style="font-size:11px; color:#888; text-align:center; margin-top:2px;">
        Threshold: {threshold:.2f}
      </div>
    </div>
    """
    st.html(html)


# ---------------------------------------------------------------------------
# Signal breakdown table
# ---------------------------------------------------------------------------
def render_signal_breakdown(basis: list[dict[str, Any]]) -> None:
    """Render a risk-factor breakdown table from a RiskScore basis list."""
    if not basis:
        st.caption("No risk factors defined.")
        return

    rows = []
    for entry in basis:
        rows.append({
            "Factor": entry.get("name", "—"),
            "Weight": f"{entry.get('weight', 0):.2f}",
            "Triggered": "\u2705" if entry.get("triggered") else "\u274c",
            "Contribution": f"{entry.get('contribution', 0):.2f}",
        })
    st.table(rows)


# ---------------------------------------------------------------------------
# Artifact diff (side-by-side)
# ---------------------------------------------------------------------------
def render_artifact_diff(a: dict[str, Any], b: dict[str, Any]) -> None:
    """Render a side-by-side diff of two artifacts."""
    col1, col2 = st.columns(2)
    with col1:
        st.caption("Before")
        st.json(a)
    with col2:
        st.caption("After")
        st.json(b)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _trunc(value: str | None, length: int = 12) -> str:
    if not value:
        return "null"
    if len(value) <= length:
        return value
    return f"{value[:6]}...{value[-4:]}"
