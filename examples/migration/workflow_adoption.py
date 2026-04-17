"""
Workflow governance pattern (after additive migration from invocation-only).

The same two governed model calls, now correlated under a GovernanceSession.
No logic was rewritten -- the governance calls are wrapped additively.

Diff from invocation_only.py:
  1. Create governance = aigc.AIGC() instance (same as before)
  2. Wrap calls in: with governance.open_session(...) as session:
  3. Replace governance.enforce_pre_call  -> session.enforce_step_pre_call
  4. Replace governance.enforce_post_call -> session.enforce_step_post_call
  5. Add session.complete() at the end

Usage:
    python workflow_adoption.py

Requires: aigc v0.9.0-beta or later (development installation: pip install -e <repo>)
"""
import aigc


def _simulate_model_call(prompt: str) -> dict:
    """Simulated model response. Replace with your real model call."""
    return {"result": f"Response to: {prompt[:60]}"}


def run_with_workflow_adoption(policy_file: str = "policy.yaml") -> dict:
    """Same two calls, now correlated under a GovernanceSession.

    Returns the workflow artifact (status + correlated step checksums).
    """
    governance = aigc.AIGC()

    with governance.open_session(policy_file=policy_file) as session:
        prompts = ["Analyze the document.", "Summarize the findings."]
        for prompt in prompts:
            # Phase A: was governance.enforce_pre_call(...)
            pre = session.enforce_step_pre_call({
                "policy_file": policy_file,
                "input": {"prompt": prompt},
                "output": {},
                "context": {},
                "model_provider": "anthropic",
                "model_identifier": "claude-sonnet-4-6",
                "role": "ai-assistant",
            })

            # Host: model call unchanged
            output = _simulate_model_call(prompt)

            # Phase B: was governance.enforce_post_call(pre, output)
            session.enforce_step_post_call(pre, output)

        session.complete()

    return session.workflow_artifact


if __name__ == "__main__":
    artifact = run_with_workflow_adoption()
    print(f"Workflow status: {artifact['status']}")
    print(f"Correlated steps: {len(artifact['steps'])}")
    print(f"Session ID: {artifact['session_id']}")
