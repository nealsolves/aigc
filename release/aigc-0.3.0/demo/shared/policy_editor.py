"""YAML policy editor with live validation and policy selector."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
import streamlit as st

from shared.state import SAMPLE_POLICIES_DIR


# ---------------------------------------------------------------------------
# Policy selector dropdown
# ---------------------------------------------------------------------------
def render_policy_selector(
    key: str = "policy_selector",
    policy_dir: Path | None = None,
) -> str | None:
    """Dropdown to select from sample policies. Returns file path or None."""
    pdir = policy_dir or SAMPLE_POLICIES_DIR
    policies = sorted(pdir.glob("*.yaml"))

    if not policies:
        st.warning("No sample policies found.")
        return None

    names = [p.name for p in policies]
    choice = st.selectbox("Select a policy", names, key=key)
    return str(pdir / choice) if choice else None


# ---------------------------------------------------------------------------
# YAML editor with live validation
# ---------------------------------------------------------------------------
def render_policy_editor(
    default_policy: str = "",
    key: str = "policy_editor",
    height: int = 300,
    label: str = "Policy YAML",
) -> dict[str, Any] | None:
    """Render a YAML text editor with live parse validation.

    Returns parsed policy dict if valid YAML, None if invalid.
    """
    raw = st.text_area(label, value=default_policy, height=height, key=key)

    if not raw.strip():
        return None

    try:
        parsed = yaml.safe_load(raw)
        if not isinstance(parsed, dict):
            st.error("Policy must be a YAML mapping (dict).")
            return None
        st.success("Valid YAML")
        return parsed
    except yaml.YAMLError as exc:
        st.error(f"YAML parse error: {exc}")
        return None


# ---------------------------------------------------------------------------
# Read a policy file and return its raw text + parsed dict
# ---------------------------------------------------------------------------
def load_policy_text(path: str) -> tuple[str, dict[str, Any] | None]:
    """Read a policy YAML file. Returns (raw_text, parsed_dict_or_None)."""
    try:
        raw = Path(path).read_text()
        parsed = yaml.safe_load(raw)
        return raw, parsed if isinstance(parsed, dict) else None
    except Exception as exc:
        return f"# Error loading {path}: {exc}", None
