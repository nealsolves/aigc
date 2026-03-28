"""Centralized session state management for the AIGC demo app."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import streamlit as st

from aigc import AIGC, AuditChain, HMACSigner, CallbackAuditSink


# ---------------------------------------------------------------------------
# Paths — resolve sample policies relative to the demo-app directory
# ---------------------------------------------------------------------------
DEMO_APP_DIR = Path(__file__).resolve().parent.parent
SAMPLE_POLICIES_DIR = DEMO_APP_DIR / "sample_policies"

# Ensure the aigc package is importable when running from demo-app/
_project_root = DEMO_APP_DIR.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))


# ---------------------------------------------------------------------------
# Session state initialization
# ---------------------------------------------------------------------------
def init_state() -> None:
    """Initialize all session state keys with defaults.

    Safe to call on every rerun — only sets keys that don't exist yet.
    """
    defaults: dict = {
        # Navigation
        "current_lab": "lab1",

        # AIGC core objects
        "signer": None,            # HMACSigner | None
        "signing_key": "",         # hex string of current key
        "chain": AuditChain(),
        "custom_gates": [],

        # Audit history (in-memory for demo)
        "audit_history": [],

        # Lab 1 — Risk Scoring
        "risk_score_history": [],
        "lab1_last_artifact": None,
        "lab1_mode": "risk_scored",

        # Lab 2 — Signing
        "lab2_last_artifact": None,
        "lab2_signed_artifact": None,

        # Lab 3 — Audit Chain
        "lab3_chain_verified": None,

        # Lab 4 — Composition
        "lab4_composed_policy": None,
        "lab4_escalation_violations": None,

        # Lab 5 — Loaders & Versioning
        "lab5_loaded_policy": None,
        "lab5_version_result": None,
        "lab5_test_results": None,

        # Lab 6 — Custom Gates
        "lab6_selected_recipe": None,
        "lab6_last_artifact": None,

        # Lab 7 — Compliance
        "lab7_export_path": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


# ---------------------------------------------------------------------------
# AIGC instance factory
# ---------------------------------------------------------------------------
def get_aigc(**overrides) -> AIGC:
    """Build an AIGC instance with current session configuration.

    Parameters in *overrides* take precedence over session state values.
    A fresh instance is created on every call so that labs can swap signers,
    gates, etc. without cross-lab pollution.
    """
    sink = CallbackAuditSink(callback=record_artifact)

    kwargs: dict = {
        "sink": sink,
        "on_sink_failure": "log",
        "strict_mode": False,
        "signer": st.session_state.get("signer"),
    }

    # Remove chain-related keys — chain is managed standalone, not via AIGC
    overrides.pop("use_chain", None)

    # Custom gates
    gates = overrides.pop("custom_gates", None)
    if gates is not None:
        kwargs["custom_gates"] = gates
    elif st.session_state.get("custom_gates"):
        kwargs["custom_gates"] = st.session_state["custom_gates"]

    kwargs.update(overrides)
    return AIGC(**kwargs)


# ---------------------------------------------------------------------------
# Audit history helpers
# ---------------------------------------------------------------------------
def record_artifact(artifact: dict) -> None:
    """Callback sink — appends artifact to session history.

    NOTE: Do NOT append to the chain here.  The chain is managed exclusively
    by AIGC.enforce() when the AIGC instance is constructed with chain=.
    """
    st.session_state.audit_history.append(artifact)


def clear_history() -> None:
    """Reset audit history and chain."""
    st.session_state.audit_history = []
    st.session_state.chain = AuditChain()
    st.session_state.risk_score_history = []


# ---------------------------------------------------------------------------
# Helper — resolve a sample policy path
# ---------------------------------------------------------------------------
def sample_policy_path(name: str) -> str:
    """Return the absolute path to a sample policy file."""
    return str(SAMPLE_POLICIES_DIR / name)
