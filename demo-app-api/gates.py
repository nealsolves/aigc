"""Custom EnforcementGate implementations for the Lab 6 demo."""
from __future__ import annotations

import inspect
import re
from typing import Any, Mapping

from aigc import EnforcementGate, GateResult


class SessionAuthorizationGate(EnforcementGate):
    """Fails if the caller session is not marked authorized in context."""

    @property
    def name(self) -> str:
        return "session_authorization_gate"

    @property
    def insertion_point(self) -> str:
        return "pre_authorization"

    def evaluate(
        self,
        invocation: Mapping[str, Any],
        policy: Mapping[str, Any],
        context: dict[str, Any],
    ) -> GateResult:
        authorized = bool(invocation.get("context", {}).get("session_authorized"))
        if not authorized:
            return GateResult(
                passed=False,
                failures=[{"gate": self.name, "message": "session is not authorized"}],
            )
        return GateResult(passed=True, metadata={"session_authorized": True})


class DomainAllowlistGate(EnforcementGate):
    """Fails if context.domain is outside the demo allowlist."""

    _ALLOWED = {"medical", "nutrition"}

    @property
    def name(self) -> str:
        return "domain_allowlist_gate"

    @property
    def insertion_point(self) -> str:
        return "post_authorization"

    def evaluate(
        self,
        invocation: Mapping[str, Any],
        policy: Mapping[str, Any],
        context: dict[str, Any],
    ) -> GateResult:
        domain = str(invocation.get("context", {}).get("domain", ""))
        if domain not in self._ALLOWED:
            return GateResult(
                passed=False,
                failures=[{
                    "gate": self.name,
                    "message": f"domain '{domain}' is outside the allowlist",
                }],
            )
        return GateResult(passed=True, metadata={"allowed_domain": domain})


class ConfidenceGate(EnforcementGate):
    """Fails if output.confidence < 0.5."""

    @property
    def name(self) -> str:
        return "confidence_gate"

    @property
    def insertion_point(self) -> str:
        return "pre_output"

    def evaluate(
        self,
        invocation: Mapping[str, Any],
        policy: Mapping[str, Any],
        context: dict[str, Any],
    ) -> GateResult:
        confidence = invocation.get("output", {}).get("confidence", 1.0)
        if confidence < 0.5:
            return GateResult(
                passed=False,
                failures=[{"gate": self.name, "message": f"confidence {confidence:.2f} < 0.5"}],
            )
        return GateResult(passed=True, metadata={"confidence": confidence})


class PIIDetectionGate(EnforcementGate):
    """Fails if output contains email, phone, or SSN patterns."""

    _EMAIL = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
    _PHONE = re.compile(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b")
    _SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")

    @property
    def name(self) -> str:
        return "pii_detection_gate"

    @property
    def insertion_point(self) -> str:
        return "post_output"

    def evaluate(
        self,
        invocation: Mapping[str, Any],
        policy: Mapping[str, Any],
        context: dict[str, Any],
    ) -> GateResult:
        text = str(invocation.get("output", {}).get("result", ""))
        found = []
        if self._EMAIL.search(text):
            found.append("email address")
        if self._PHONE.search(text):
            found.append("phone number")
        if self._SSN.search(text):
            found.append("SSN")
        if found:
            return GateResult(
                passed=False,
                failures=[{"gate": self.name, "message": f"PII detected: {', '.join(found)}"}],
            )
        return GateResult(passed=True, metadata={"pii_found": []})


class ResponseLengthGate(EnforcementGate):
    """Fails if output.result exceeds 500 characters."""

    @property
    def name(self) -> str:
        return "response_length_gate"

    @property
    def insertion_point(self) -> str:
        return "pre_output"

    def evaluate(
        self,
        invocation: Mapping[str, Any],
        policy: Mapping[str, Any],
        context: dict[str, Any],
    ) -> GateResult:
        text = str(invocation.get("output", {}).get("result", ""))
        if len(text) > 500:
            return GateResult(
                passed=False,
                failures=[{
                    "gate": self.name,
                    "message": f"Response length {len(text)} > 500 chars",
                }],
            )
        return GateResult(passed=True, metadata={"length": len(text)})


class AuditMetadataGate(EnforcementGate):
    """Always passes; injects metadata into the audit artifact."""

    @property
    def name(self) -> str:
        return "audit_metadata_gate"

    @property
    def insertion_point(self) -> str:
        return "post_output"

    def evaluate(
        self,
        invocation: Mapping[str, Any],
        policy: Mapping[str, Any],
        context: dict[str, Any],
    ) -> GateResult:
        return GateResult(
            passed=True,
            metadata={"demo_gate": True, "gate_version": "1.0"},
        )


GATES: dict[str, EnforcementGate] = {
    g.name: g
    for g in [
        SessionAuthorizationGate(),
        DomainAllowlistGate(),
        ConfidenceGate(),
        ResponseLengthGate(),
        PIIDetectionGate(),
        AuditMetadataGate(),
    ]
}


def get_gate_info(gate: EnforcementGate) -> dict:
    return {
        "name": gate.name,
        "insertion_point": gate.insertion_point,
        "description": (gate.__class__.__doc__ or "").strip(),
        "source": inspect.getsource(gate.__class__),
    }
