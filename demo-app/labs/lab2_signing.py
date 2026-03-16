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
        mode="workflows",
        workflows=[
            GuideWorkflow(
                name="Sign an Artifact",
                description="Generate a key, run enforcement, and inspect the signature.",
                steps=[
                    GuideStep(
                        title="Generate a key",
                        instruction='Click "Generate Key" to create a random 32-byte HMAC secret.',
                        what_to_expect="A hex key appears in the key field.",
                        completion_key="lab2_key_set",
                    ),
                    GuideStep(
                        title="Run signed enforcement",
                        instruction='Click "Run & Sign" to enforce and sign the artifact.',
                        what_to_expect="A signed artifact appears with a signature field.",
                        completion_key="lab2_signed_artifact",
                    ),
                    GuideStep(
                        title="Verify",
                        instruction='Click "Verify Signature" to confirm the signature is valid.',
                        what_to_expect="Green checkmark — the artifact is authentic.",
                        completion_key="lab2_verified",
                    ),
                ],
            ),
            GuideWorkflow(
                name="Tamper Detection",
                description="Modify a signed artifact and see verification fail.",
                steps=[
                    GuideStep(
                        title="Tamper with the artifact",
                        instruction='Click "Tamper" to flip the enforcement result.',
                        what_to_expect="The artifact is modified in-place.",
                    ),
                    GuideStep(
                        title="Re-verify",
                        instruction='Click "Verify Signature" again.',
                        what_to_expect="Red X — the signature no longer matches.",
                    ),
                ],
            ),
            GuideWorkflow(
                name="Key Rotation",
                description="Generate a new key and see cross-key verification fail.",
                steps=[
                    GuideStep(
                        title="Generate a new key",
                        instruction='Click "Generate Key" to create a second key.',
                        what_to_expect="The key field updates. Old key is gone.",
                    ),
                    GuideStep(
                        title="Verify with new key",
                        instruction="Verify the artifact signed with the old key.",
                        what_to_expect="Verification fails — wrong key.",
                    ),
                ],
            ),
        ],
        glossary={
            "HMAC-SHA256": "Hash-based Message Authentication Code using SHA-256. Proves artifact integrity and authenticity.",
            "Signing": "Computing a keyed hash over the canonical artifact bytes.",
            "Verification": "Recomputing the hash and comparing to the stored signature.",
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

    # -- Key management ----------------------------------------------------
    key_col, action_col = st.columns([2, 1])

    with key_col:
        current_key = st.session_state.get("signing_key", "")
        st.text_input(
            "HMAC Key (hex)",
            value=current_key,
            key="lab2_key_display",
            disabled=True,
        )

    with action_col:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Generate Key", use_container_width=True):
            new_key = secrets.token_hex(32)
            st.session_state["signing_key"] = new_key
            signer = HMACSigner(bytes.fromhex(new_key))
            st.session_state["signer"] = signer
            st.session_state["lab2_key_set"] = True
            st.rerun()

    st.divider()

    # -- Two columns: sign | verify ----------------------------------------
    sign_col, verify_col = st.columns(2)

    with sign_col:
        st.subheader("Sign")
        if st.button("Run & Sign", type="primary", use_container_width=True):
            _run_and_sign()

        artifact = st.session_state.get("lab2_signed_artifact")
        if artifact:
            sig = artifact.get("signature", "—")
            st.code(f"Signature: {sig}", language=None)
            render_artifact(artifact)

    with verify_col:
        st.subheader("Verify")

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
