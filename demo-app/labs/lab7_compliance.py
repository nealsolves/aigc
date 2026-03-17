"""Lab 7: Compliance Dashboard.

Full-width layout (no guide rail). Aggregates all audit artifacts from
the session and provides:
  - Summary statistics (total, pass/fail counts, avg risk score)
  - Filterable audit trail table
  - Multi-format export (JSON, CSV)
  - CLI equivalent command display
"""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime
from typing import Any

import streamlit as st


# ---------------------------------------------------------------------------
# No guide rail for Lab 7
# ---------------------------------------------------------------------------
# (get_guide is intentionally not defined — app.py checks hasattr)


# ---------------------------------------------------------------------------
# Main render
# ---------------------------------------------------------------------------
def render() -> None:
    st.header("Lab 7: Compliance Dashboard")
    st.caption(
        "Aggregate view of all audit artifacts generated during this session. "
        "Filter, inspect, and export compliance evidence."
    )

    history: list[dict[str, Any]] = st.session_state.get("audit_history", [])

    if not history:
        st.info(
            "No audit artifacts yet. Run enforcement in any lab to populate "
            "this dashboard."
        )
        return

    # -- Summary stats -----------------------------------------------------
    _render_summary(history)

    st.divider()

    # -- Filters -----------------------------------------------------------
    filtered = _render_filters(history)

    # -- Audit trail table -------------------------------------------------
    st.divider()
    st.subheader(f"Audit Trail ({len(filtered)} artifacts)")
    _render_table(filtered)

    # -- Export ------------------------------------------------------------
    st.divider()
    _render_export(filtered)

    # -- CLI equivalent ----------------------------------------------------
    st.divider()
    _render_cli_equivalent()


# ---------------------------------------------------------------------------
# Summary statistics
# ---------------------------------------------------------------------------
def _render_summary(history: list[dict[str, Any]]) -> None:
    total = len(history)
    pass_count = sum(1 for a in history if a.get("enforcement_result") == "PASS")
    fail_count = total - pass_count
    pass_rate = (pass_count / total * 100) if total else 0

    # Average risk score
    risk_scores = []
    for a in history:
        rs = a.get("metadata", {}).get("risk_scoring")
        if isinstance(rs, dict):
            risk_scores.append(rs.get("score", 0))
        elif isinstance(rs, (int, float)):
            risk_scores.append(float(rs))
    avg_risk = sum(risk_scores) / len(risk_scores) if risk_scores else None

    # Signing coverage
    signed = sum(1 for a in history if a.get("signature") is not None)
    sign_pct = (signed / total * 100) if total else 0

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Total Audits", total)
    col2.metric("PASS", f"{pass_count} ({pass_rate:.0f}%)")
    col3.metric("FAIL", fail_count)
    col4.metric("Avg Risk Score", f"{avg_risk:.2f}" if avg_risk is not None else "N/A")
    col5.metric("Signed", f"{signed} ({sign_pct:.0f}%)")


# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------
def _render_filters(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    col1, col2 = st.columns(2)

    with col1:
        result_filter = st.selectbox(
            "Status",
            ["All", "PASS", "FAIL"],
            key="lab7_result_filter",
        )

    with col2:
        policies = sorted({a.get("policy_file", "—") for a in history})
        policy_filter = st.selectbox(
            "Policy",
            ["All"] + policies,
            key="lab7_policy_filter",
        )

    filtered = history
    if result_filter != "All":
        filtered = [a for a in filtered if a.get("enforcement_result") == result_filter]
    if policy_filter != "All":
        filtered = [a for a in filtered if a.get("policy_file") == policy_filter]

    return filtered


# ---------------------------------------------------------------------------
# Audit trail table
# ---------------------------------------------------------------------------
def _render_table(artifacts: list[dict[str, Any]]) -> None:
    if not artifacts:
        st.info("No artifacts match the current filters.")
        return

    rows = []
    for a in artifacts:
        timestamp = a.get("timestamp", "—")
        if isinstance(timestamp, (int, float)):
            timestamp = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")

        risk_meta = a.get("metadata", {}).get("risk_scoring")
        if isinstance(risk_meta, dict):
            risk_str = f"{risk_meta.get('score', 0):.2f}"
        elif isinstance(risk_meta, (int, float)):
            risk_str = f"{float(risk_meta):.2f}"
        else:
            risk_str = "—"

        checksum = a.get("checksum", "—")
        short_cksum = f"{checksum[:8]}..." if len(checksum) > 8 else checksum

        rows.append({
            "Timestamp": timestamp,
            "Policy": a.get("policy_file", "—"),
            "Result": a.get("enforcement_result", "?"),
            "Risk Score": risk_str,
            "Checksum": short_cksum,
            "Signed": "Yes" if a.get("signature") else "No",
        })

    st.dataframe(rows, use_container_width=True)

    # Expandable per-artifact detail
    for i, a in enumerate(artifacts):
        with st.expander(f"Artifact #{i + 1} — {a.get('enforcement_result', '?')}"):
            st.json(a)


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------
def _render_export(artifacts: list[dict[str, Any]]) -> None:
    st.subheader("Export")

    fmt = st.radio(
        "Format",
        ["JSON", "CSV"],
        horizontal=True,
        key="lab7_export_format",
    )

    if fmt == "JSON":
        data = json.dumps(artifacts, indent=2, default=str)
        mime = "application/json"
        fname = "aigc_compliance_export.json"
    else:
        buf = io.StringIO()
        if artifacts:
            fieldnames = [
                "enforcement_result", "policy_file", "timestamp",
                "checksum", "signature",
            ]
            writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for a in artifacts:
                writer.writerow({
                    "enforcement_result": a.get("enforcement_result"),
                    "policy_file": a.get("policy_file"),
                    "timestamp": a.get("timestamp"),
                    "checksum": a.get("checksum"),
                    "signature": a.get("signature", ""),
                })
        data = buf.getvalue()
        mime = "text/csv"
        fname = "aigc_compliance_export.csv"

    st.download_button(
        f"Download {fmt}",
        data=data,
        file_name=fname,
        mime=mime,
        use_container_width=True,
    )


# ---------------------------------------------------------------------------
# CLI equivalent
# ---------------------------------------------------------------------------
def _render_cli_equivalent() -> None:
    st.subheader("CLI Equivalent")
    st.caption("The same export can be run from the command line:")
    st.code(
        "# Export last 7 days of audit artifacts as CSV\n"
        "aigc audit export --format csv --days 7 --output report.csv\n\n"
        "# Export signed artifacts only as JSON evidence bundle\n"
        "aigc audit export --format json --signed-only --output evidence.json\n\n"
        "# Print compliance summary for last 30 days\n"
        "aigc audit summary --days 30",
        language="bash",
    )
