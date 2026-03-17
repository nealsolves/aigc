"""Fluent builder for invocation dicts."""

from __future__ import annotations

from typing import Any


class InvocationBuilder:
    """Fluent builder for constructing invocation dicts.

    Usage::

        invocation = (
            InvocationBuilder()
            .policy("policies/governance.yaml")
            .model("anthropic", "claude-sonnet-4-5-20250929")
            .role("planner")
            .input({"task": "analyse"})
            .output({"result": "ok", "confidence": 0.9})
            .context({"role_declared": True, "schema_exists": True})
            .build()
        )
    """

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    def policy(self, policy_file: str) -> InvocationBuilder:
        """Set the policy file path."""
        self._data["policy_file"] = policy_file
        return self

    def model(self, provider: str, identifier: str) -> InvocationBuilder:
        """Set model provider and identifier."""
        self._data["model_provider"] = provider
        self._data["model_identifier"] = identifier
        return self

    def role(self, role: str) -> InvocationBuilder:
        """Set the invocation role."""
        self._data["role"] = role
        return self

    def input(self, input_data: dict[str, Any]) -> InvocationBuilder:
        """Set the model input."""
        self._data["input"] = input_data
        return self

    def output(self, output_data: dict[str, Any]) -> InvocationBuilder:
        """Set the model output."""
        self._data["output"] = output_data
        return self

    def context(self, context_data: dict[str, Any]) -> InvocationBuilder:
        """Set the invocation context."""
        self._data["context"] = context_data
        return self

    def tools(self, tool_calls: list[dict[str, Any]]) -> InvocationBuilder:
        """Set tool call metadata."""
        self._data["tool_calls"] = tool_calls
        return self

    def build(self) -> dict[str, Any]:
        """Build and validate the invocation dict.

        :return: A validated invocation dict
        :raises InvocationValidationError: If required fields are missing
        """
        from aigc._internal.enforcement import _validate_invocation
        result = dict(self._data)
        _validate_invocation(result)
        return result
