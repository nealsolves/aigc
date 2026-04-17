#!/usr/bin/env python3
"""
PR-07 clean-environment proof harness.

Creates a fresh venv, installs the repo in editable mode, and runs the
full quickstart journey end to end. Exits 0 when all gates PASS within
budget, exits 1 otherwise.

Writes a JSON summary to stdout.

Usage:
    python scripts/validate_v090_beta_proof.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import venv
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.resolve()
BUDGET_SECONDS = 900  # 15-minute budget for the three success paths combined


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _venv_python(venv_dir: Path) -> str:
    bin_dir = venv_dir / ("Scripts" if sys.platform == "win32" else "bin")
    suffix = ".exe" if sys.platform == "win32" else ""
    return str(bin_dir / f"python{suffix}")


def _venv_env(venv_dir: Path) -> dict:
    env = os.environ.copy()
    bin_dir = venv_dir / ("Scripts" if sys.platform == "win32" else "bin")
    env["VIRTUAL_ENV"] = str(venv_dir)
    env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")
    env.pop("PYTHONHOME", None)
    return env


def _run(cmd: list[str], env: dict | None = None, cwd: Path | None = None,
         capture: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        capture_output=capture,
        text=True,
        env=env or os.environ.copy(),
        cwd=str(cwd or REPO_ROOT),
    )


def _run_workflow_in_venv(
    python: str, env: dict, workflow_py: Path, func_name: str, tmp_dir: Path
) -> dict:
    """Run a workflow function inside the venv Python; return the artifact dict.

    Writes a thin runner script that imports the generated workflow_example.py,
    calls ``func_name()``, and prints the artifact as JSON.  Executing the runner
    via a subprocess ensures imports are resolved against the venv installation,
    not the parent interpreter — which is the point of the clean-env proof.
    """
    runner = tmp_dir / f"_runner_{func_name}.py"
    runner.write_text(
        "import sys, json, importlib.util\n"
        f"spec = importlib.util.spec_from_file_location('wf', {str(workflow_py)!r})\n"
        "mod = importlib.util.module_from_spec(spec)\n"
        "spec.loader.exec_module(mod)\n"
        f"artifact = mod.{func_name}()\n"
        "print(json.dumps(artifact))\n"
    )
    r = _run([python, str(runner)], env=env)
    assert r.returncode == 0, (
        f"Workflow runner for {func_name!r} exited {r.returncode}:\n{r.stderr}"
    )
    return json.loads(r.stdout.strip())


def run_gate(name: str, fn) -> dict:
    start = time.time()
    error = None
    passed = False
    try:
        fn()
        passed = True
    except AssertionError as exc:
        error = str(exc)
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
    elapsed = round(time.time() - start, 2)
    status = "PASS" if passed else "FAIL"
    print(f"  [{status}] {name} ({elapsed}s)" + (f" — {error}" if error else ""),
          flush=True)
    return {"gate": name, "passed": passed, "elapsed_s": elapsed, "error": error}


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> int:
    tmp_dir = Path(tempfile.mkdtemp(prefix="aigc_beta_proof_"))
    venv_dir = tmp_dir / "venv"
    gates: list[dict] = []
    success_elapsed = 0.0

    print(f"PR-07 clean-environment proof harness", flush=True)
    print(f"Working dir: {tmp_dir}", flush=True)
    print(f"Repo root:   {REPO_ROOT}", flush=True)
    print()

    # ------------------------------------------------------------------
    # Gate 1: create venv and install
    # ------------------------------------------------------------------
    def gate_install():
        print("  Creating virtual environment...", end="", flush=True)
        venv.create(str(venv_dir), with_pip=True, clear=True)
        print(" done", flush=True)
        print("  Installing package in editable mode...", end="", flush=True)
        python = _venv_python(venv_dir)
        env = _venv_env(venv_dir)
        r = _run([python, "-m", "pip", "install", "--no-build-isolation",
                  "-e", str(REPO_ROOT), "-q"], env=env)
        assert r.returncode == 0, f"pip install failed:\n{r.stderr}"
        print(" done", flush=True)

    gates.append(run_gate("venv_install", gate_install))

    env = _venv_env(venv_dir)
    python = _venv_python(venv_dir)

    # ------------------------------------------------------------------
    # Gate 2: minimal quickstart
    # ------------------------------------------------------------------
    def gate_minimal():
        nonlocal success_elapsed
        d = tmp_dir / "minimal"
        d.mkdir()
        t0 = time.time()

        r = _run([python, "-m", "aigc", "workflow", "init",
                  "--profile", "minimal", "--output-dir", str(d)], env=env)
        assert r.returncode == 0, f"aigc workflow init failed:\n{r.stderr}"

        artifact = _run_workflow_in_venv(
            python, env, d / "workflow_example.py", "run_minimal_workflow", tmp_dir
        )

        assert artifact["status"] == "COMPLETED", (
            f"Expected COMPLETED, got {artifact['status']}"
        )
        assert len(artifact["steps"]) == 2, (
            f"Expected 2 steps, got {len(artifact['steps'])}"
        )
        success_elapsed += time.time() - t0

    gates.append(run_gate("minimal_quickstart", gate_minimal))

    # ------------------------------------------------------------------
    # Gate 3: standard quickstart
    # ------------------------------------------------------------------
    def gate_standard():
        nonlocal success_elapsed
        d = tmp_dir / "standard"
        d.mkdir()
        t0 = time.time()

        r = _run([python, "-m", "aigc", "workflow", "init",
                  "--profile", "standard", "--output-dir", str(d)], env=env)
        assert r.returncode == 0, f"aigc workflow init failed:\n{r.stderr}"

        artifact = _run_workflow_in_venv(
            python, env, d / "workflow_example.py", "run_standard_workflow", tmp_dir
        )

        assert artifact["status"] == "COMPLETED", (
            f"Expected COMPLETED, got {artifact['status']}"
        )
        assert len(artifact["steps"]) == 3, (
            f"Expected 3 steps, got {len(artifact['steps'])}"
        )
        success_elapsed += time.time() - t0

    gates.append(run_gate("standard_quickstart", gate_standard))

    # ------------------------------------------------------------------
    # Gate 4: regulated failure (intentional — must raise)
    # ProvenanceGate runs at INSERTION_PRE_OUTPUT (inside enforce_step_post_call).
    # ------------------------------------------------------------------
    def gate_failure():
        d = tmp_dir / "regulated"
        d.mkdir()

        r = _run([python, "-m", "aigc", "workflow", "init",
                  "--profile", "regulated-high-assurance", "--output-dir", str(d)], env=env)
        assert r.returncode == 0, f"aigc workflow init failed:\n{r.stderr}"

        # Write a helper script that runs a governed step without source_ids.
        # ProvenanceGate fires during enforce_step_post_call.
        broken_script = tmp_dir / "run_broken.py"
        policy_path = str(d / "policy.yaml").replace("\\", "/")
        broken_script.write_text(f"""\
import sys
sys.path.insert(0, r"{REPO_ROOT}")
import aigc
from aigc import AIGC, ProvenanceGate

policy_file = r"{policy_path}"
gate = ProvenanceGate(require_source_ids=True)
governance = AIGC(custom_gates=[gate])

with governance.open_session(policy_file=policy_file) as session:
    pre = session.enforce_step_pre_call({{
        "policy_file": policy_file,
        "input": {{"prompt": "test"}},
        "output": {{}},
        "context": {{"caller_id": "test"}},   # no provenance.source_ids
        "model_provider": "anthropic",
        "model_identifier": "claude-sonnet-4-6",
        "role": "ai-assistant",
    }})
    # ProvenanceGate fires here:
    session.enforce_step_post_call(pre, {{"result": "output"}})
""")
        r = _run([python, str(broken_script)], env=env)
        assert r.returncode != 0, (
            "Expected non-zero exit from broken script (failure path should raise), "
            f"got returncode={r.returncode}"
        )

    gates.append(run_gate("regulated_failure", gate_failure))

    # ------------------------------------------------------------------
    # Gate 5: doctor diagnosis
    # ------------------------------------------------------------------
    def gate_diagnosis():
        d = tmp_dir / "regulated"  # already generated in gate 4
        r = _run([python, "-m", "aigc", "workflow", "doctor",
                  str(d), "--json"], env=env)
        assert r.returncode == 0, (
            f"aigc workflow doctor exited {r.returncode}:\n{r.stderr}"
        )
        findings = json.loads(r.stdout)
        codes = [f["code"] for f in findings]
        assert "WORKFLOW_SOURCE_REQUIRED" in codes, (
            f"Expected WORKFLOW_SOURCE_REQUIRED in doctor findings. Got: {codes}\n"
            f"Full output: {r.stdout}"
        )

    gates.append(run_gate("doctor_diagnosis", gate_diagnosis))

    # ------------------------------------------------------------------
    # Gate 6: regulated fix applied — unmodified script has source_ids -> COMPLETED
    # ------------------------------------------------------------------
    def gate_fix():
        nonlocal success_elapsed
        d = tmp_dir / "regulated"
        t0 = time.time()

        artifact = _run_workflow_in_venv(
            python, env, d / "workflow_example.py", "run_regulated_workflow", tmp_dir
        )

        assert artifact["status"] == "COMPLETED", (
            f"Expected COMPLETED after fix, got {artifact['status']}"
        )
        success_elapsed += time.time() - t0

    gates.append(run_gate("regulated_fix_rerun", gate_fix))

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    print()
    all_passed = all(g["passed"] for g in gates)
    within_budget = success_elapsed <= BUDGET_SECONDS
    summary = {
        "summary": "PASS" if (all_passed and within_budget) else "FAIL",
        "all_gates_passed": all_passed,
        "total_success_path_elapsed_s": round(success_elapsed, 2),
        "within_budget": within_budget,
        "budget_seconds": BUDGET_SECONDS,
        "gates": gates,
    }
    print(json.dumps(summary, indent=2))

    if not within_budget:
        print(
            f"\nWARNING: success paths took {success_elapsed:.1f}s "
            f"(budget: {BUDGET_SECONDS}s)",
            file=sys.stderr,
        )

    return 0 if (all_passed and within_budget) else 1


if __name__ == "__main__":
    sys.exit(main())
