"""
Invocation-only governance pattern (before workflow adoption).

This is the pre-migration pattern: each model call is governed independently
with no workflow correlation between calls.

Usage:
    python invocation_only.py

Requires: aigc v0.9.0-beta or later (development installation: pip install -e <repo>)
"""
import aigc


def _simulate_model_call(prompt: str) -> dict:
    """Simulated model response. Replace with your real model call."""
    return {"result": f"Response to: {prompt[:60]}"}


def run_with_invocation_only(policy_file: str = "policy.yaml") -> list[dict]:
    """Govern two model calls independently. Returns list of audit artifacts."""
    governance = aigc.AIGC()
    artifacts = []

    prompts = ["Analyze the document.", "Summarize the findings."]
    for prompt in prompts:
        # Phase A: pre-call enforcement (validates preconditions)
        pre = governance.enforce_pre_call({
            "policy_file": policy_file,
            "input": {"prompt": prompt},
            "output": {},
            "context": {},
            "model_provider": "anthropic",
            "model_identifier": "claude-sonnet-4-6",
            "role": "ai-assistant",
        })

        # Host: make the actual model call
        output = _simulate_model_call(prompt)

        # Phase B: post-call enforcement (validates output, emits audit artifact)
        artifact = governance.enforce_post_call(pre, output)
        artifacts.append(artifact)

    return artifacts


if __name__ == "__main__":
    artifacts = run_with_invocation_only()
    print(f"Governed {len(artifacts)} invocations independently.")
    for i, a in enumerate(artifacts, 1):
        print(f"  Invocation {i}: {a.get('enforcement_result', 'unknown')}")
