"""Lab 2: Signing & Verification.

Demonstrates HMAC-SHA256 artifact signing:
  - Generate a signing key
  - Run enforcement with signing enabled
  - Verify the signed artifact
  - Tamper with a field and see verification fail
  - Rotate keys and observe cross-key verification failure
"""

from __future__ import annotations

import copy
import secrets
from typing import Any

import streamlit as st

from aigc import (
    AIGC,
    HMACSigner,
    InvocationBuilder,
    AIGCError,
    CallbackAuditSink,
)
from aigc.signing import sign_artifact, verify_artifact

from shared.state import get_aigc, sample_policy_path, record_artifact
from shared.ai_client import get_scenario
from shared.artifact_display import render_artifact, render_artifact_diff
from shared.guide_rail import LabGuide, GuideStep, GuideWorkflow


# ---------------------------------------------------------------------------
# Guide rail
# ---------------------------------------------------------------------------
def get_guide() -> LabGuide:
    return LabGuide(
        lab_id="lab2",
        title="Signing & Verification",
        overview="Sign audit artifacts with HMAC-SHA256 and prove tamper detection.",
        mode="linear",
        steps=[
            GuideStep(
                title="Generate a key",
                instruction=(
                    'Under **Step 1**, click **"Generate Key"**. '
                    "This creates a random 32-byte HMAC-SHA256 secret. "
                    "The hex key appears in the text field. "
                    "You need this key before you can sign or verify anything."
                ),
                what_to_expect="A 64-character hex string fills the key field.",
                completion_key="lab2_key_set",
            ),
            GuideStep(
                title="Run signed enforcement",
                instruction=(
                    'Under **Step 2**, click **"Run & Sign"**. '
                    "This runs the full governance pipeline on a mock medical scenario "
                    "and then signs the resulting audit artifact with your HMAC key. "
                    "The signature is a cryptographic proof that the artifact hasn't been altered."
                ),
                what_to_expect=(
                    "A signature hex string appears under Step 2, and the full "
                    "audit artifact renders below with Signed = Yes."
                ),
                completion_key="lab2_signed_artifact",
            ),
            GuideStep(
                title="Verify the signature",
                instruction=(
                    'Under **Step 3**, click **"Verify Signature"**. '
                    "This recomputes the HMAC hash over the artifact and compares it "
                    "to the stored signature. If they match, the artifact is authentic."
                ),
                what_to_expect=(
                    'Green message: **"Signature VALID"**. '
                    "The artifact has not been modified since signing."
                ),
                completion_key="lab2_verified",
            ),
            GuideStep(
                title="(Optional) Tamper with the artifact",
                instruction=(
                    'Under **Step 3**, click **"Tamper (flip result)"**. '
                    "This silently flips the enforcement_result field from PASS to FAIL "
                    "(or vice versa), simulating a malicious edit. "
                    "The signature is NOT updated — it still reflects the original artifact."
                ),
                what_to_expect=(
                    "The artifact's enforcement_result changes. "
                    "The signature stays the same."
                ),
            ),
            GuideStep(
                title="(Optional) Verify again — it should fail",
                instruction=(
                    'Click **"Verify Signature"** one more time. '
                    "The recomputed hash no longer matches the stored signature "
                    "because the artifact was tampered with."
                ),
                what_to_expect=(
                    'Red message: **"Signature INVALID"**. '
                    "This proves that HMAC signing detects even a single-field change."
                ),
            ),
        ],
        glossary={
            "HMAC-SHA256": "Hash-based Message Authentication Code using SHA-256. Proves artifact integrity and authenticity.",
            "Signing": "Computing a keyed hash over the canonical artifact bytes.",
            "Verification": "Recomputing the hash and comparing to the stored signature.",
            "Tamper detection": "Any modification to a signed artifact invalidates the signature, proving the artifact was altered.",
        },
    )


# ---------------------------------------------------------------------------
# Main render
# ---------------------------------------------------------------------------
def render() -> None:
    st.header("Lab 2: Signing & Verification")
    st.caption(
        "Prove that audit artifacts haven't been tampered with using "
        "HMAC-SHA256 signatures."
    )

    # -- Step 1: Key management --------------------------------------------
    st.subheader("Step 1. Generate HMAC Key (hex)")
    key_col, action_col = st.columns([2, 1])

    with key_col:
        current_key = st.session_state.get("signing_key", "")
        st.text_input(
            "HMAC Key (hex)",
            value=current_key,
            key="lab2_key_display",
            disabled=True,
            label_visibility="collapsed",
        )

    with action_col:
        if st.button("Generate Key", use_container_width=True):
            new_key = secrets.token_hex(32)
            st.session_state["signing_key"] = new_key
            signer = HMACSigner(bytes.fromhex(new_key))
            st.session_state["signer"] = signer
            st.session_state["lab2_key_set"] = True
            st.rerun()

    st.divider()

    # -- Two columns: Step 2 sign | Step 3 verify -------------------------
    sign_col, verify_col = st.columns(2)

    with sign_col:
        st.subheader("Step 2. Sign")
        if st.button("Run & Sign", type="primary", use_container_width=True):
            _run_and_sign()

        artifact = st.session_state.get("lab2_signed_artifact")
        if artifact:
            sig = artifact.get("signature", "—")
            st.code(f"Signature: {sig}", language=None)

    with verify_col:
        st.subheader("Step 3. Verify")

        artifact = st.session_state.get("lab2_signed_artifact")
        signer = st.session_state.get("signer")

        if artifact and signer:
            if st.button("Verify Signature", use_container_width=True):
                try:
                    valid = verify_artifact(artifact, signer)
                    if valid:
                        st.success("Signature VALID — artifact is authentic.")
                        st.session_state["lab2_verified"] = True
                    else:
                        st.error("Signature INVALID — artifact has been modified.")
                except Exception as exc:
                    st.error(f"Verification error: {exc}")

            st.divider()

            # Tamper button
            if st.button("Tamper (flip result)", type="secondary", use_container_width=True):
                _tamper_artifact()
                st.rerun()

        elif not st.session_state.get("signing_key"):
            st.info("Generate a key first.")
        else:
            st.info('Run & Sign an artifact first.')

    # Render artifact outside columns to avoid nested-column violation
    artifact = st.session_state.get("lab2_signed_artifact")
    if artifact:
        st.divider()
        render_artifact(artifact)


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------
def _run_and_sign() -> None:
    """Run enforcement with signing enabled."""
    signer = st.session_state.get("signer")
    if not signer:
        st.error("Generate a signing key first.")
        return

    scenario = get_scenario("signing_basic")
    policy_path = sample_policy_path("medical_ai.yaml")

    try:
        aigc = get_aigc(signer=signer)
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
        st.session_state["lab2_signed_artifact"] = artifact
        st.session_state["lab2_last_artifact"] = artifact
        st.success("Enforcement PASSED — artifact signed.")
    except AIGCError as exc:
        artifact = getattr(exc, "audit_artifact", None)
        if artifact:
            st.session_state["lab2_signed_artifact"] = artifact
        st.error(f"Enforcement failed: {exc}")


def _tamper_artifact() -> None:
    """Modify the signed artifact to demonstrate tamper detection."""
    artifact = st.session_state.get("lab2_signed_artifact")
    if not artifact:
        return

    # Flip the enforcement result
    current = artifact.get("enforcement_result", "PASS")
    artifact["enforcement_result"] = "FAIL" if current == "PASS" else "PASS"
    st.session_state["lab2_signed_artifact"] = artifact
