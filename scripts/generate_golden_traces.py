"""
Automatic Golden Trace Capture

This script is intended to be used with real invocation logs
or sample runs. It captures invocation artifacts and
creates templated golden traces with minimal manual effort.

Usage:
    python generate_golden_traces.py --input logs/invocations.json
"""

import json
import argparse
from copy import deepcopy
from pathlib import Path
from src.enforcement import enforce_invocation

GOLDEN_DIR = Path("tests/golden_traces")

def make_golden_invocation(inv):
    """
    Remove variable artifacts and create a stable golden trace.
    """
    normalized = deepcopy(inv)

    # Remove timestamps if present
    normalized.pop("timestamp", None)

    # Remove request-scoped ids when present
    normalized.pop("request_id", None)
    normalized.pop("trace_id", None)
    normalized.pop("invocation_id", None)

    return normalized

def main(input_file: str):
    """
    Read a list of invocation records, apply governance, and
    generate golden traces.
    """
    with open(input_file, "r", encoding="utf-8") as f:
        invocations = json.load(f)

    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)

    for idx, inv in enumerate(invocations):
        print(f"Processing invocation #{idx}")

        # Enforce to ensure it's valid
        audit = enforce_invocation(inv)

        # Make stable golden payload
        golden = make_golden_invocation(inv)

        # Write golden invocation
        out_path = GOLDEN_DIR / f"auto_golden_invocation_{idx}.json"
        with open(out_path, "w", encoding="utf-8") as out:
            json.dump(golden, out, indent=2, sort_keys=True)

        # Create associated expected audit (partial)
        audit_template = {
            "model_provider": audit["model_provider"],
            "model_identifier": audit["model_identifier"],
            "policy_version": audit["policy_version"],
            "role": audit["role"],
        }
        audit_path = GOLDEN_DIR / f"auto_golden_expected_audit_{idx}.json"
        with open(audit_path, "w", encoding="utf-8") as out:
            json.dump(audit_template, out, indent=2, sort_keys=True)

        print(f"Generated golden: {out_path}, {audit_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=str, required=True)
    args = parser.parse_args()
    main(args.input)
