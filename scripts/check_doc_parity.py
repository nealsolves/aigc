#!/usr/bin/env python3
"""Documentation parity checker for the AIGC repository.

Validates that documentation stays synchronized with implementation:
  A. Current-state parity across canonical docs
  B. Public API boundary (no aigc._internal in user-facing docs)
  C. Schema-example parity (policy YAML examples vs JSON Schema)
  D. Local link hygiene (broken markdown links)
  E. Archive hygiene (headers, no active->archive references)
  F. Gate-ID consistency (canonical gate IDs in gates_evaluated examples)
  G. Parity-set docs exist and are non-empty

Usage:
    python scripts/check_doc_parity.py

Exit codes:
    0 — all checks pass
    1 — one or more checks failed
"""
from __future__ import annotations

import fnmatch
import json
import re
import subprocess
import sys
from pathlib import Path

import yaml
from jsonschema import Draft7Validator, ValidationError

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = REPO_ROOT / "doc_parity_manifest.yaml"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_manifest() -> dict:
    with open(MANIFEST_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def is_internal_doc(path: str, internal_patterns: list[str]) -> bool:
    """Return True if *path* (relative to repo root) matches an internal pattern."""
    for pattern in internal_patterns:
        if fnmatch.fnmatch(path, pattern):
            return True
    return False


def collect_md_files() -> list[Path]:
    """Collect all git-tracked .md files to avoid scanning gitignored artifacts."""
    try:
        output = subprocess.check_output(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard",
             "*.md", "**/*.md"],
            cwd=REPO_ROOT,
            text=True,
        )
        result = [REPO_ROOT / line for line in output.strip().splitlines() if line]
    except (subprocess.CalledProcessError, FileNotFoundError):
        # Fallback: rglob with basic exclusions (e.g. outside a git repo)
        excluded = {"aigc-env", "node_modules", ".git", ".pytest_cache",
                    ".venv", "venv", "dist"}
        result = []
        for p in REPO_ROOT.rglob("*.md"):
            parts = p.relative_to(REPO_ROOT).parts
            if any(part in excluded for part in parts):
                continue
            if any(part.endswith(".egg-info") for part in parts):
                continue
            result.append(p)
    return sorted(result)


# ---------------------------------------------------------------------------
# Check A: Current-state parity
# ---------------------------------------------------------------------------

def check_current_state_parity(manifest: dict) -> list[str]:
    """Ensure parity docs agree on version, test_count, audit_schema_version."""
    errors: list[str] = []
    version = manifest["version"]
    test_count = str(manifest["test_count"])
    audit_ver = manifest["audit_schema_version"]

    parity_docs = manifest["parity_docs"]

    for rel in parity_docs:
        path = REPO_ROOT / rel
        if not path.exists():
            # Existence checked separately in check F
            continue
        text = path.read_text(encoding="utf-8")

        # Version check — only flag if the doc mentions an SDK version
        # that differs from manifest. We look for "v0.x.y" patterns
        # (the project convention for SDK version references).
        # This excludes document-metadata versions like "Version: 1.0.0".
        sdk_version_refs = re.findall(r"\bv(\d+\.\d+\.\d+)\b", text)
        if sdk_version_refs and version not in sdk_version_refs:
            errors.append(
                f"[current-state] {rel}: mentions version(s) "
                f"{set('v' + v for v in sdk_version_refs)} but manifest "
                f"expects 'v{version}'"
            )

        # Test count — only check docs that mention test counts
        # Match patterns like "304 tests" or "304 tests" in tables
        if re.search(r"\d+\s+tests?", text):
            if not re.search(rf"\b{test_count}\b.*tests?", text):
                errors.append(
                    f"[current-state] {rel}: expected test count "
                    f"'{test_count}' (from manifest) not found — "
                    f"but doc mentions test counts"
                )

        # Audit schema version — only check docs that reference it
        if "audit" in text.lower() and "schema" in text.lower() and "version" in text.lower():
            if re.search(r"audit.schema.version|schema\s+version", text, re.I):
                if audit_ver not in text:
                    errors.append(
                        f"[current-state] {rel}: expected audit schema "
                        f"version '{audit_ver}' (from manifest) not found — "
                        f"but doc references audit schema version"
                    )

    return errors


# ---------------------------------------------------------------------------
# Check B: Public API boundary
# ---------------------------------------------------------------------------

_INTERNAL_IMPORT_RE = re.compile(
    r"""
    (?:from\s+aigc\._internal|import\s+aigc\._internal)  # import statements
    | aigc\._internal\.\w+                                 # dotted references
    """,
    re.VERBOSE,
)

# Patterns that indicate the reference is explicitly marked as internal
_INTERNAL_DISCLAIMER_RE = re.compile(
    r"private|internal.*(detail|implementation)|not\s+public|may\s+change",
    re.IGNORECASE,
)


def check_public_api_boundary(manifest: dict) -> list[str]:
    """Fail if user-facing docs import/reference aigc._internal."""
    errors: list[str] = []
    internal_patterns = manifest.get("internal_docs", [])

    for path in collect_md_files():
        rel = str(path.relative_to(REPO_ROOT))
        if is_internal_doc(rel, internal_patterns):
            continue

        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()

        for i, line in enumerate(lines, 1):
            if _INTERNAL_IMPORT_RE.search(line):
                # Check if surrounding context disclaims it as internal
                context_start = max(0, i - 4)
                context_end = min(len(lines), i + 3)
                context = "\n".join(lines[context_start:context_end])
                if not _INTERNAL_DISCLAIMER_RE.search(context):
                    errors.append(
                        f"[api-boundary] {rel}:{i}: references "
                        f"aigc._internal without internal disclaimer"
                    )

    return errors


# ---------------------------------------------------------------------------
# Check C: Schema-example parity
# ---------------------------------------------------------------------------

_YAML_BLOCK_RE = re.compile(
    r"```ya?ml\s*\n(.*?)```",
    re.DOTALL,
)

_JSON_BLOCK_RE = re.compile(
    r"```json\s*\n(.*?)```",
    re.DOTALL,
)


def _is_complete_policy(obj: dict) -> bool:
    """True if obj has all required policy schema fields (not a snippet)."""
    # Policy schema requires: policy_version, roles
    return "policy_version" in obj and "roles" in obj


def _is_complete_audit_artifact(obj: dict) -> bool:
    """True if obj has all required audit artifact fields (not a snippet)."""
    required = {"audit_schema_version", "policy_file", "policy_schema_version",
                "policy_version", "model_provider", "model_identifier", "role",
                "enforcement_result", "failures", "input_checksum",
                "output_checksum", "timestamp", "context", "metadata"}
    return required <= set(obj.keys())


def check_schema_example_parity(manifest: dict) -> list[str]:
    """Validate policy/audit examples in docs against their JSON schemas."""
    errors: list[str] = []
    internal_patterns = manifest.get("internal_docs", [])

    # Load schemas
    policy_schema_path = REPO_ROOT / "schemas" / "policy_dsl.schema.json"
    audit_schema_path = REPO_ROOT / "schemas" / "audit_artifact.schema.json"

    if not policy_schema_path.exists() or not audit_schema_path.exists():
        errors.append("[schema-parity] Missing schema files")
        return errors

    policy_schema = json.loads(policy_schema_path.read_text(encoding="utf-8"))
    audit_schema = json.loads(audit_schema_path.read_text(encoding="utf-8"))
    policy_validator = Draft7Validator(policy_schema)
    audit_validator = Draft7Validator(audit_schema)

    for path in collect_md_files():
        rel = str(path.relative_to(REPO_ROOT))
        if is_internal_doc(rel, internal_patterns):
            continue
        text = path.read_text(encoding="utf-8")

        # Check YAML blocks that look like policies
        for m in _YAML_BLOCK_RE.finditer(text):
            block = m.group(1)
            try:
                obj = yaml.safe_load(block)
            except yaml.YAMLError:
                continue
            if not isinstance(obj, dict):
                continue
            if _is_complete_policy(obj):
                try:
                    policy_validator.validate(obj)
                except ValidationError as e:
                    # Calculate line number
                    line = text[:m.start()].count("\n") + 1
                    errors.append(
                        f"[schema-parity] {rel}:{line}: policy example "
                        f"fails schema validation: {e.message}"
                    )

        # Check JSON blocks that look like audit artifacts
        for m in _JSON_BLOCK_RE.finditer(text):
            block = m.group(1)
            try:
                obj = json.loads(block)
            except json.JSONDecodeError:
                continue
            if not isinstance(obj, dict):
                continue
            if _is_complete_audit_artifact(obj):
                try:
                    audit_validator.validate(obj)
                except ValidationError as e:
                    line = text[:m.start()].count("\n") + 1
                    errors.append(
                        f"[schema-parity] {rel}:{line}: audit artifact "
                        f"example fails schema validation: {e.message}"
                    )

    return errors


# ---------------------------------------------------------------------------
# Check D: Local link hygiene
# ---------------------------------------------------------------------------

_MD_LINK_RE = re.compile(
    r"\[([^\]]*)\]\(([^)]+)\)",
)


def check_link_hygiene() -> list[str]:
    """Fail on broken local markdown links."""
    errors: list[str] = []

    for path in collect_md_files():
        rel = str(path.relative_to(REPO_ROOT))
        text = path.read_text(encoding="utf-8")

        for i, line in enumerate(text.splitlines(), 1):
            for m in _MD_LINK_RE.finditer(line):
                target = m.group(2)

                # Skip external URLs
                if target.startswith(("http://", "https://", "mailto:")):
                    continue

                # Skip anchor-only links
                if target.startswith("#"):
                    continue

                # Strip anchor fragment
                target_path = target.split("#")[0]
                if not target_path:
                    continue

                # Resolve relative to the file's directory
                resolved = (path.parent / target_path).resolve()
                if not resolved.exists():
                    errors.append(
                        f"[link-hygiene] {rel}:{i}: broken link "
                        f"to '{target_path}'"
                    )

    return errors


# ---------------------------------------------------------------------------
# Check E: Archive hygiene
# ---------------------------------------------------------------------------

_ARCHIVE_HEADER_RE = re.compile(
    r"archived|superseded|deprecated|no longer active",
    re.IGNORECASE,
)


def check_archive_hygiene() -> list[str]:
    """If docs/_archive/ exists, validate archive headers and references."""
    errors: list[str] = []
    archive_dir = REPO_ROOT / "docs" / "_archive"

    if not archive_dir.exists():
        return errors

    # Check archived docs have archive headers (first 10 lines)
    for path in archive_dir.rglob("*.md"):
        rel = str(path.relative_to(REPO_ROOT))
        text = path.read_text(encoding="utf-8")
        header = "\n".join(text.splitlines()[:10])
        if not _ARCHIVE_HEADER_RE.search(header):
            errors.append(
                f"[archive-hygiene] {rel}: archived doc missing "
                f"archive/deprecated header in first 10 lines"
            )

    # Check active docs don't reference archived docs as canonical
    archive_rel = "docs/_archive/"
    for path in collect_md_files():
        rel = str(path.relative_to(REPO_ROOT))
        if rel.startswith(archive_rel):
            continue
        text = path.read_text(encoding="utf-8")
        for i, line in enumerate(text.splitlines(), 1):
            for m in _MD_LINK_RE.finditer(line):
                target = m.group(2)
                if "_archive/" in target or "_archive\\" in target:
                    errors.append(
                        f"[archive-hygiene] {rel}:{i}: active doc "
                        f"links to archived doc '{target}'"
                    )

    return errors


# ---------------------------------------------------------------------------
# Check F: Gate-ID consistency
# ---------------------------------------------------------------------------

_GATES_EVALUATED_RE = re.compile(
    r'"gates_evaluated"',
)


def check_gate_id_consistency(manifest: dict) -> list[str]:
    """Ensure parity docs use canonical gate IDs in gates_evaluated examples."""
    errors: list[str] = []
    canonical = set(manifest.get("canonical_gate_ids", []))
    if not canonical:
        return errors

    # Known non-canonical aliases that indicate drift
    non_canonical_map = {
        "tool_validation": "tool_constraint_validation",
    }

    for rel in manifest["parity_docs"]:
        path = REPO_ROOT / rel
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")

        # Check JSON code blocks that contain gates_evaluated
        for m in _JSON_BLOCK_RE.finditer(text):
            block = m.group(1)
            if "gates_evaluated" not in block:
                continue
            line_offset = text[:m.start()].count("\n") + 1
            for alias, correct in non_canonical_map.items():
                if f'"{alias}"' in block:
                    errors.append(
                        f"[gate-id] {rel}:{line_offset}: "
                        f"gates_evaluated uses non-canonical ID "
                        f"'{alias}' (should be '{correct}')"
                    )

    return errors


# ---------------------------------------------------------------------------
# Check G: Parity-set docs exist
# ---------------------------------------------------------------------------

def check_parity_docs_exist(manifest: dict) -> list[str]:
    """Ensure all parity-set docs exist and are non-empty."""
    errors: list[str] = []

    for rel in manifest["parity_docs"]:
        path = REPO_ROOT / rel
        if not path.exists():
            errors.append(f"[parity-set] {rel}: file does not exist")
        elif path.stat().st_size == 0:
            errors.append(f"[parity-set] {rel}: file is empty")

    return errors


# ---------------------------------------------------------------------------
# Check H: Semantic behavioral claims
# ---------------------------------------------------------------------------

_RISK_SCORED_BLOCKING_RE = re.compile(
    r"risk_scored[^\n]{0,80}(?:threshold[^\n]{0,40}(?:FAIL|block|enforc)"
    r"|(?:FAIL|block|enforc)[^\n]{0,40}threshold)",
    re.I,
)

_AUDIT_CMD_RE = re.compile(r"aigc\s+audit\s+(?:export|summary)", re.I)

# Docs that describe live CLI behavior (not historical/archive docs)
_CLI_BEHAVIOR_DOCS = [
    "README.md",
    "demo-app-streamlit/labs/lab7_compliance.py",
    "docs/AIGC_FRAMEWORK.md",
]

# Docs that describe live risk-mode semantics
_RISK_SEMANTICS_DOCS = [
    "README.md",
    "docs/AIGC_FRAMEWORK.md",
    "demo-app-streamlit/labs/lab1_risk_scoring.py",
]


def check_semantic_claims() -> list[str]:
    """Check that docs don't contain known false semantic claims.

    H1: risk_scored must not be described as blocking on threshold exceedance.
    H2: aigc audit commands must not appear in active CLI-behavior docs.
    """
    errors: list[str] = []

    for rel in _RISK_SEMANTICS_DOCS:
        path = REPO_ROOT / rel
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for m in _RISK_SCORED_BLOCKING_RE.finditer(text):
            line = text[: m.start()].count("\n") + 1
            errors.append(
                f"[semantic-H1] {rel}:{line}: describes risk_scored as blocking "
                f"on threshold exceedance — only strict mode blocks; "
                f"matched: {m.group()!r}"
            )

    for rel in _CLI_BEHAVIOR_DOCS:
        path = REPO_ROOT / rel
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for m in _AUDIT_CMD_RE.finditer(text):
            line = text[: m.start()].count("\n") + 1
            errors.append(
                f"[semantic-H2] {rel}:{line}: references 'aigc audit' which does "
                f"not exist in the CLI; use 'aigc compliance export' instead"
            )

    return errors


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    print("=" * 60)
    print("AIGC Documentation Parity Checker")
    print("=" * 60)

    manifest = load_manifest()
    all_errors: list[str] = []
    checks = [
        ("A. Current-state parity", lambda: check_current_state_parity(manifest)),
        ("B. Public API boundary", lambda: check_public_api_boundary(manifest)),
        ("C. Schema-example parity", lambda: check_schema_example_parity(manifest)),
        ("D. Local link hygiene", check_link_hygiene),
        ("E. Archive hygiene", check_archive_hygiene),
        ("F. Gate-ID consistency", lambda: check_gate_id_consistency(manifest)),
        ("G. Parity-set docs exist", lambda: check_parity_docs_exist(manifest)),
        ("H. Semantic behavioral claims", check_semantic_claims),
    ]

    for name, check_fn in checks:
        print(f"\n--- {name} ---")
        errors = check_fn()
        if errors:
            for e in errors:
                print(f"  FAIL: {e}")
            all_errors.extend(errors)
        else:
            print("  PASS")

    print("\n" + "=" * 60)
    if all_errors:
        print(f"FAILED: {len(all_errors)} parity error(s) found")
        return 1
    else:
        print("PASSED: all documentation parity checks OK")
        return 0


if __name__ == "__main__":
    sys.exit(main())
