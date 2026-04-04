"""Custom PolicyLoaderBase subclasses for the AIGC demo API.

These loaders demonstrate the pluggable loader architecture introduced in
AIGC v0.3.0. Pass a loader instance to AIGC(policy_loader=...) to control
how policies are resolved — no filesystem path required.
"""

import yaml as yaml_lib
from aigc import PolicyLoaderBase


class InMemoryPolicyLoader(PolicyLoaderBase):
    """Holds a single policy dict loaded from a raw YAML string.

    Demonstrates pluggable loader architecture: the policy source is
    arbitrary YAML text rather than a file path. The SDK calls
    ``load(policy_ref)`` transparently — the caller never touches the disk.

    Usage::

        loader = InMemoryPolicyLoader(yaml_text)
        aigc = AIGC(policy_loader=loader)
        artifact = aigc.enforce(invocation)
    """

    def __init__(self, yaml_text: str) -> None:
        self._policy = yaml_lib.safe_load(yaml_text)

    def load(self, policy_ref: str) -> dict:  # noqa: ARG002
        return self._policy
