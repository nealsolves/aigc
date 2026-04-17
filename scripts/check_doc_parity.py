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
  H. Implementation-truth consistency
  I. Semantic behavioral claims
  J. v0.9.0 plan truth
  K. v0.9.0 release truth
  L. v0.9.0 PR-02 contract freeze truth

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

_REQUIRED_PARITY_DOCS = [
    "README.md",
    "PROJECT.md",
    "CHANGELOG.md",
    "docs/AIGC_FRAMEWORK.md",
    "docs/INTEGRATION_GUIDE.md",
    "docs/PUBLIC_INTEGRATION_CONTRACT.md",
    "docs/architecture/ARCHITECTURAL_INVARIANTS.md",
    "docs/architecture/ENFORCEMENT_PIPELINE.md",
]

_REQUIRED_BOUNDARY_DOCS = [
    "docs/PUBLIC_INTEGRATION_CONTRACT.md",
]

_REQUIRED_TARGET_STATE_DOCS = [
    "docs/architecture/AIGC_HIGH_LEVEL_DESIGN.md",
]

_CURRENT_RUNTIME_SEMVER_RE = re.compile(r"\b(\d+\.\d+\.\d+)\b")
_CURRENT_RUNTIME_CONTEXT_MARKERS = (
    "current release",
    "current runtime",
    "current public runtime surface",
    "runtime baseline",
    "shipped",
    "installable",
    "since",
    "starting in",
    "new in",
)
_TARGET_STATE_CONTEXT_MARKERS = (
    "target-state",
    "target state",
    "planned",
    "planned-only",
    "version:",
    "status:",
    "ga",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_manifest() -> dict:
    with open(MANIFEST_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(
            f"doc_parity_manifest.yaml is empty or invalid "
            f"(expected a mapping, got {type(data).__name__})"
        )
    return data


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
        result = [
            REPO_ROOT / line
            for line in output.strip().splitlines()
            if line and (REPO_ROOT / line).exists()
        ]
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


def get_manifest_doc_list(
    manifest: dict,
    key: str,
    label: str,
    required_docs: list[str] | None = None,
) -> tuple[list[str], list[str]]:
    """Return a manifest-backed doc list plus validation errors."""
    errors: list[str] = []
    value = manifest.get(key)

    if value is None:
        errors.append(f"[{label}] manifest missing required '{key}' list")
        return [], errors
    if not isinstance(value, list):
        errors.append(f"[{label}] manifest '{key}' must be a list")
        return [], errors
    if not value:
        errors.append(f"[{label}] manifest '{key}' must not be empty")
        return [], errors

    docs: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            errors.append(
                f"[{label}] manifest '{key}' must contain only non-empty strings"
            )
            continue
        docs.append(item)

    missing_required = [
        rel for rel in (required_docs or []) if rel not in docs
    ]
    if missing_required:
        errors.append(
            f"[{label}] manifest '{key}' missing required doc(s): "
            + ", ".join(missing_required)
        )

    return docs, errors


def extract_current_runtime_version_refs(text: str) -> set[str]:
    """Extract version references that describe the shipped runtime."""
    refs = set(re.findall(r"\bv(\d+\.\d+\.\d+)\b", text))

    for line in text.splitlines():
        if not _CURRENT_RUNTIME_SEMVER_RE.search(line):
            continue

        lower = line.lower()
        if any(marker in lower for marker in _TARGET_STATE_CONTEXT_MARKERS):
            continue
        if any(marker in lower for marker in _CURRENT_RUNTIME_CONTEXT_MARKERS):
            refs.update(_CURRENT_RUNTIME_SEMVER_RE.findall(line))

    return refs


# ---------------------------------------------------------------------------
# Check A: Current-state parity
# ---------------------------------------------------------------------------

def check_current_state_parity(manifest: dict) -> list[str]:
    """Ensure parity docs agree on version, test_count, audit_schema_version."""
    errors: list[str] = []
    version = manifest["version"]
    test_count = str(manifest["test_count"])
    audit_ver = manifest["audit_schema_version"]

    parity_docs = manifest.get("parity_docs", [])

    for rel in parity_docs:
        path = REPO_ROOT / rel
        if not path.exists():
            # Existence checked separately in check F
            continue
        text = path.read_text(encoding="utf-8")

        # Version check — only flag if the doc mentions a shipped-runtime
        # version that differs from the manifest. This accepts either `v0.x.y`
        # or bare `0.x.y` when the surrounding line clearly describes the
        # current runtime rather than a target-state contract.
        sdk_version_refs = extract_current_runtime_version_refs(text)
        if sdk_version_refs and version not in sdk_version_refs:
            errors.append(
                f"[current-state] {rel}: mentions current-runtime version(s) "
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

    for rel in manifest.get("parity_docs", []):
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
    parity_docs, errors = get_manifest_doc_list(
        manifest,
        "parity_docs",
        "parity-set",
        required_docs=_REQUIRED_PARITY_DOCS,
    )

    for rel in parity_docs:
        path = REPO_ROOT / rel
        if not path.exists():
            errors.append(f"[parity-set] {rel}: file does not exist")
        elif path.stat().st_size == 0:
            errors.append(f"[parity-set] {rel}: file is empty")

    return errors


# ---------------------------------------------------------------------------
# Check H: Runtime onboarding boundary docs
# ---------------------------------------------------------------------------

_BOUNDARY_DOC_WARNING_RE = re.compile(
    r"(planned-only|planned only).*(not part of the installable|do not yet "
    r"export|not part of the shipped)",
    re.IGNORECASE | re.DOTALL,
)

_BOUNDARY_DOC_DO_NOT_USE_RE = re.compile(
    r"do\s+not\s+build\s+current\s+integrations|"
    r"not safe for current integrations|"
    r"do\s+not\s+use .* current integrations",
    re.IGNORECASE | re.DOTALL,
)


def check_availability_boundary_docs(manifest: dict) -> list[str]:
    """Ensure onboarding docs warn against planned-only surfaces."""
    boundary_docs, errors = get_manifest_doc_list(
        manifest,
        "availability_boundary_docs",
        "boundary-doc",
        required_docs=_REQUIRED_BOUNDARY_DOCS,
    )

    for rel in boundary_docs:
        path = REPO_ROOT / rel
        if not path.exists():
            errors.append(f"[boundary-doc] {rel}: file does not exist")
            continue
        if path.stat().st_size == 0:
            errors.append(f"[boundary-doc] {rel}: file is empty")
            continue

        text = path.read_text(encoding="utf-8")

        if "GovernanceSession" not in text or "aigc workflow" not in text:
            errors.append(
                f"[boundary-doc] {rel}: must name planned-only workflow "
                "surfaces such as GovernanceSession and aigc workflow commands"
            )

        if not _BOUNDARY_DOC_WARNING_RE.search(text):
            errors.append(
                f"[boundary-doc] {rel}: missing explicit planned-only / not "
                "shipped availability warning"
            )

        if not _BOUNDARY_DOC_DO_NOT_USE_RE.search(text):
            errors.append(
                f"[boundary-doc] {rel}: missing explicit 'do not build current "
                "integrations against these names' warning"
            )

    return errors


# ---------------------------------------------------------------------------
# Check I: Target-state contract coverage
# ---------------------------------------------------------------------------

_TARGET_STATE_STATUS_RE = re.compile(
    r"Status:\s*Target-State Design",
    re.IGNORECASE,
)

_TARGET_STATE_BOUNDARY_RE = re.compile(
    r"Availability boundary:.*?(?:do not yet export|planned-only|not part of "
    r"the installable)",
    re.IGNORECASE | re.DOTALL,
)

_TARGET_STATE_PLANNED_SURFACE_RE = re.compile(
    r"Planned-only additions.*?not exported by `0\.3\.3`.*?not available\s+"
    r"in the `0\.3\.3` CLI",
    re.IGNORECASE | re.DOTALL,
)

_TARGET_STATE_STABILITY_GUARD_RE = re.compile(
    r"`?1\.x`?\s+stability promise.*?does not apply to the shipped\s+"
    r"`0\.3\.3`\s+artifact.*?activates only after `1\.0\.0` formally ships",
    re.IGNORECASE | re.DOTALL,
)


def check_target_state_docs(manifest: dict) -> list[str]:
    """Ensure target-state docs are explicit future-contract docs."""
    target_docs, errors = get_manifest_doc_list(
        manifest,
        "target_state_docs",
        "target-state",
        required_docs=_REQUIRED_TARGET_STATE_DOCS,
    )
    parity_docs = set(manifest.get("parity_docs", []))

    for rel in target_docs:
        path = REPO_ROOT / rel
        if not path.exists():
            errors.append(f"[target-state] {rel}: file does not exist")
            continue
        if path.stat().st_size == 0:
            errors.append(f"[target-state] {rel}: file is empty")
            continue
        if rel in parity_docs:
            errors.append(
                f"[target-state] {rel}: appears in both target_state_docs and "
                "parity_docs"
            )

        text = path.read_text(encoding="utf-8")
        header = "\n".join(text.splitlines()[:25])

        if not _TARGET_STATE_STATUS_RE.search(header):
            errors.append(
                f"[target-state] {rel}: missing 'Status: Target-State Design' "
                "marker near the top of the document"
            )

        if not _TARGET_STATE_BOUNDARY_RE.search(text):
            errors.append(
                f"[target-state] {rel}: missing an explicit availability "
                "boundary for planned-only surfaces"
            )

        if not _TARGET_STATE_PLANNED_SURFACE_RE.search(text):
            errors.append(
                f"[target-state] {rel}: missing an explicit planned-only "
                "workflow API fence for the `0.3.3` public surface"
            )

        if not _TARGET_STATE_STABILITY_GUARD_RE.search(text):
            errors.append(
                f"[target-state] {rel}: missing a guard that delays the `1.x` "
                "stability promise until `1.0.0` GA"
            )

    return errors


# ---------------------------------------------------------------------------
# Check J: Implementation-truth consistency
# ---------------------------------------------------------------------------

def check_implementation_truth(manifest: dict) -> list[str]:
    """Verify manifest values match actual implementation sources.

    Reads the canonical values directly from:
      - pyproject.toml  (project.version)
      - aigc/__init__.py  (__version__)
      - aigc/_internal/audit.py  (AUDIT_SCHEMA_VERSION)
      - README.md  ("Current release:" line)
      - CHANGELOG.md  (first versioned section header)

    Fails if any source disagrees with the manifest or with each other.
    """
    errors: list[str] = []
    manifest_version = manifest["version"]
    manifest_audit_ver = manifest["audit_schema_version"]

    # 1. pyproject.toml
    pyproject_path = REPO_ROOT / "pyproject.toml"
    pyproject_version: str | None = None
    if pyproject_path.exists():
        text = pyproject_path.read_text(encoding="utf-8")
        m = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
        if m:
            pyproject_version = m.group(1)
            if pyproject_version != manifest_version:
                errors.append(
                    f"[impl-truth] pyproject.toml version '{pyproject_version}' "
                    f"!= manifest version '{manifest_version}'"
                )
        else:
            errors.append("[impl-truth] pyproject.toml: could not parse version")
    else:
        errors.append("[impl-truth] pyproject.toml not found")

    # 2. aigc/__init__.py __version__
    init_path = REPO_ROOT / "aigc" / "__init__.py"
    if init_path.exists():
        text = init_path.read_text(encoding="utf-8")
        m = re.search(r'^__version__\s*=\s*"([^"]+)"', text, re.MULTILINE)
        if m:
            init_version = m.group(1)
            if init_version != manifest_version:
                errors.append(
                    f"[impl-truth] aigc/__init__.py __version__ '{init_version}' "
                    f"!= manifest version '{manifest_version}'"
                )
        else:
            errors.append("[impl-truth] aigc/__init__.py: could not parse __version__")
    else:
        errors.append("[impl-truth] aigc/__init__.py not found")

    # 3. AUDIT_SCHEMA_VERSION in aigc/_internal/audit.py
    audit_py_path = REPO_ROOT / "aigc" / "_internal" / "audit.py"
    if audit_py_path.exists():
        text = audit_py_path.read_text(encoding="utf-8")
        m = re.search(r'^AUDIT_SCHEMA_VERSION\s*=\s*"([^"]+)"', text, re.MULTILINE)
        if m:
            code_audit_ver = m.group(1)
            if code_audit_ver != manifest_audit_ver:
                errors.append(
                    f"[impl-truth] aigc/_internal/audit.py AUDIT_SCHEMA_VERSION "
                    f"'{code_audit_ver}' != manifest audit_schema_version "
                    f"'{manifest_audit_ver}'"
                )
        else:
            errors.append(
                "[impl-truth] aigc/_internal/audit.py: could not parse "
                "AUDIT_SCHEMA_VERSION"
            )
    else:
        errors.append("[impl-truth] aigc/_internal/audit.py not found")

    # 4. README.md "Current release:" line
    readme_path = REPO_ROOT / "README.md"
    if readme_path.exists():
        text = readme_path.read_text(encoding="utf-8")
        m = re.search(r"Current release:\s*`v([\d.]+)`", text)
        if m:
            readme_version = m.group(1)
            if readme_version != manifest_version:
                errors.append(
                    f"[impl-truth] README.md 'Current release' shows "
                    f"'v{readme_version}' != manifest version '{manifest_version}'"
                )
        else:
            errors.append(
                "[impl-truth] README.md: could not find 'Current release:' line"
            )
    else:
        errors.append("[impl-truth] README.md not found")

    # 5. CHANGELOG.md — first versioned section must be the manifest version
    #    (not Unreleased), confirming the release is promoted.
    changelog_path = REPO_ROOT / "CHANGELOG.md"
    if changelog_path.exists():
        text = changelog_path.read_text(encoding="utf-8")
        # Match the first "## [X.Y.Z]" or "## [Unreleased]" header
        m = re.search(r"^## \[([^\]]+)\]", text, re.MULTILINE)
        if m:
            first_section = m.group(1)
            if first_section.lower() == "unreleased":
                errors.append(
                    f"[impl-truth] CHANGELOG.md top section is '[Unreleased]' — "
                    f"promote to '[{manifest_version}]' before release"
                )
            elif first_section != manifest_version:
                errors.append(
                    f"[impl-truth] CHANGELOG.md top section '[{first_section}]' "
                    f"!= manifest version '{manifest_version}'"
                )
        else:
            errors.append(
                "[impl-truth] CHANGELOG.md: could not find a versioned section header"
            )
    else:
        errors.append("[impl-truth] CHANGELOG.md not found")

    return errors


# ---------------------------------------------------------------------------
# Check K: Semantic behavioral claims
# ---------------------------------------------------------------------------

_RISK_SCORED_BLOCKING_RE = re.compile(
    r"risk_scored[^\n]{0,80}(?:threshold[^\n]{0,40}(?:FAIL|block|enforc)"
    r"|(?:FAIL|block|enforc)[^\n]{0,40}threshold)",
    re.I,
)

_AUDIT_CMD_RE = re.compile(r"aigc\s+audit\s+(?:export|summary)", re.I)
_WRAPPED_FUNCTION_ERROR_MIGRATION_RE = re.compile(
    r"wrapped_function_error[^\n]{0,160}"
    r"(?:existed before v0\.3\.2|pre-?dates? v0\.3\.2|no schema changes required)",
    re.I,
)

# Docs that describe live CLI behavior (not historical/archive docs)
_CLI_BEHAVIOR_DOCS = [
    "README.md",
    "docs/AIGC_FRAMEWORK.md",
]

# Docs that describe live risk-mode semantics
_RISK_SEMANTICS_DOCS = [
    "README.md",
    "docs/AIGC_FRAMEWORK.md",
]

# Docs that describe the v0.3.2 wrapped-function failure taxonomy.
_WRAPPED_FUNCTION_ERROR_DOCS = [
    "CHANGELOG.md",
    "docs/design/v0.3.2_DESIGN_SPEC.md",
]


def check_semantic_claims() -> list[str]:
    """Check that docs don't contain known false semantic claims.

    I1: risk_scored must not be described as blocking on threshold exceedance.
    I2: aigc audit commands must not appear in active CLI-behavior docs.
    I3: wrapped_function_error must not be described as pre-v0.3.2 or
        schema-neutral.
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
                f"[semantic-I1] {rel}:{line}: describes risk_scored as blocking "
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
                f"[semantic-I2] {rel}:{line}: references 'aigc audit' which does "
                f"not exist in the CLI; use 'aigc compliance export' instead"
            )

    for rel in _WRAPPED_FUNCTION_ERROR_DOCS:
        path = REPO_ROOT / rel
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for m in _WRAPPED_FUNCTION_ERROR_MIGRATION_RE.finditer(text):
            line = text[: m.start()].count("\n") + 1
            errors.append(
                f"[semantic-I3] {rel}:{line}: describes "
                f"'wrapped_function_error' as pre-v0.3.2 or as requiring no "
                f"schema change; this value is additive in v0.3.2"
            )

    return errors


# ---------------------------------------------------------------------------
# Check J: v0.9.0 plan truth
# ---------------------------------------------------------------------------

_V090_CANONICAL_PLAN = "docs/plans/AIGC V0.9.0 IMPLEMENTATION_PLAN.md"
_V090_HISTORICAL_PLANS = [
    "docs/plans/0.9.0 plan backup.md",
    "docs/plans/AIGC V0.9.0 IMPLEMENTATION_PLAN_DRAFT.md",
    "docs/plans/AIGC V0.9.0 IMPLEMENTATION_PLAN_DRAFT_ORIG.md",
    "docs/plans/AIGC_v0.9.0_IMPLEMENTATION_PLAN_UPDATED.md",
]
_V090_ALL_EXPECTED_PLANS = [_V090_CANONICAL_PLAN, *_V090_HISTORICAL_PLANS]
_SUPERSEDED_PLAN_RE = re.compile(r"superseded|historical input only", re.I)


def _read_header(rel: str, max_lines: int = 25) -> str:
    path = REPO_ROOT / rel
    if not path.exists():
        return ""
    return "\n".join(path.read_text(encoding="utf-8").splitlines()[:max_lines])


def _read_text(rel: str) -> str:
    path = REPO_ROOT / rel
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def check_v090_plan_truth() -> list[str]:
    """Ensure there is exactly one active v0.9.0 implementation plan."""
    errors: list[str] = []
    plans_dir = REPO_ROOT / "docs" / "plans"

    if not plans_dir.exists():
        return ["[v0.9.0-plan] docs/plans directory does not exist"]

    discovered = []
    for path in plans_dir.glob("*.md"):
        lower_name = path.name.lower()
        if "0.9.0" not in lower_name:
            continue
        if "implementation_plan" in lower_name or lower_name == "0.9.0 plan backup.md":
            discovered.append(str(path.relative_to(REPO_ROOT)))
    discovered = sorted(discovered)

    expected = set(_V090_ALL_EXPECTED_PLANS)
    extras = sorted(set(discovered) - expected)
    for rel in extras:
        errors.append(
            f"[v0.9.0-plan] unexpected v0.9.0 implementation-plan candidate: {rel}"
        )

    for rel in _V090_ALL_EXPECTED_PLANS:
        if not (REPO_ROOT / rel).exists():
            errors.append(f"[v0.9.0-plan] missing expected file: {rel}")

    active_candidates: list[str] = []
    for rel in _V090_ALL_EXPECTED_PLANS:
        path = REPO_ROOT / rel
        if not path.exists():
            continue
        header = _read_header(rel)
        is_historical = bool(_SUPERSEDED_PLAN_RE.search(header))

        if rel == _V090_CANONICAL_PLAN:
            if is_historical:
                errors.append(
                    f"[v0.9.0-plan] canonical plan is marked historical: {rel}"
                )
            if "canonical implementation plan" not in header.lower():
                errors.append(
                    f"[v0.9.0-plan] canonical plan header does not declare "
                    f"canonical status: {rel}"
                )
        else:
            if not is_historical:
                errors.append(
                    f"[v0.9.0-plan] stale plan is not marked superseded: {rel}"
                )
            if _V090_CANONICAL_PLAN not in header:
                errors.append(
                    f"[v0.9.0-plan] stale plan header does not point to the "
                    f"canonical file: {rel}"
                )

        if not is_historical:
            active_candidates.append(rel)

    if active_candidates != [_V090_CANONICAL_PLAN]:
        errors.append(
            f"[v0.9.0-plan] expected exactly one active plan "
            f"({_V090_CANONICAL_PLAN}); found {active_candidates}"
        )

    return errors


# ---------------------------------------------------------------------------
# Check K: v0.9.0 release truth
# ---------------------------------------------------------------------------

_V090_RELEASE_FILES = [
    "CLAUDE.md",
    "docs/dev/pr_context.md",
    "RELEASE_GATES.md",
    "implementation_status.md",
]
_PR_TABLE_ROW_RE = re.compile(r"^\|\s*(PR-\d+[a-z]?)\s*\|\s*(.+?)\s*\|", re.MULTILINE)
_BRANCH_CODE_RE = re.compile(r"`([^`]+)`")
_STOP_SHIP_RE = re.compile(r"PR-07[\s\S]{0,240}stop-ship|stop-ship[\s\S]{0,240}PR-07", re.I)
_GO_RE = re.compile(r"formally declared (?:a )?GO", re.I)
_FREEZE_KEYWORDS_RE = re.compile(r"\b(?:until|only then|only after)\b", re.I)
_LIST_ITEM_RE = re.compile(r"^(?:[-*+] |\d+\.\s)")


def _extract_pr_branch_map(text: str) -> list[tuple[str, tuple[str, ...]]]:
    result: list[tuple[str, tuple[str, ...]]] = []
    for pr_id, branch_cell in _PR_TABLE_ROW_RE.findall(text):
        branches = tuple(_BRANCH_CODE_RE.findall(branch_cell))
        if branches:
            result.append((pr_id, branches))
    return result


def _compare_pr_branch_maps(
    rel: str,
    expected: list[tuple[str, tuple[str, ...]]],
    actual: list[tuple[str, tuple[str, ...]]],
) -> list[str]:
    errors: list[str] = []
    expected_dict = dict(expected)
    actual_dict = dict(actual)

    for pr_id, expected_branches in expected:
        actual_branches = actual_dict.get(pr_id)
        if actual_branches is None:
            errors.append(
                f"[v0.9.0-release] {rel}: missing PR table row for {pr_id}"
            )
            continue
        if actual_branches != expected_branches:
            errors.append(
                f"[v0.9.0-release] {rel}: {pr_id} row maps to "
                f"{list(actual_branches)} but CLAUDE.md maps it to "
                f"{list(expected_branches)}"
            )

    for pr_id in actual_dict:
        if pr_id not in expected_dict:
            errors.append(
                f"[v0.9.0-release] {rel}: unexpected PR table row {pr_id}"
            )

    actual_order = [pr_id for pr_id, _ in actual]
    expected_order = [pr_id for pr_id, _ in expected]
    if actual_order and actual_order != expected_order:
        errors.append(
            f"[v0.9.0-release] {rel}: PR table order {actual_order} does not "
            f"match CLAUDE.md order {expected_order}"
        )

    return errors


def _iter_rule_segments(text: str) -> list[str]:
    """Split text into normalized paragraphs and list-item rules."""
    segments: list[str] = []
    current: list[str] = []

    def flush() -> None:
        if current:
            segments.append(" ".join(current))
            current.clear()

    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            flush()
            continue
        if stripped.startswith("|"):
            flush()
            continue
        if _LIST_ITEM_RE.match(stripped):
            flush()
            current.append(stripped)
            continue
        current.append(stripped)

    flush()
    return segments


def _has_freeze_go_coupling(text: str) -> bool:
    """True when one rule statement couples the freeze directly to formal GO."""
    for segment in _iter_rule_segments(text):
        normalized = re.sub(r"\s+", " ", segment)
        if "origin/develop" not in normalized or "origin/main" not in normalized:
            continue
        if not _GO_RE.search(normalized):
            continue
        if not _FREEZE_KEYWORDS_RE.search(normalized):
            continue
        return True
    return False


def check_v090_release_truth() -> list[str]:
    """Ensure release-truth docs agree on v0.9.0 sequencing rules."""
    errors: list[str] = []
    claude_path = REPO_ROOT / "CLAUDE.md"

    if not claude_path.exists():
        return ["[v0.9.0-release] CLAUDE.md does not exist"]

    claude_text = claude_path.read_text(encoding="utf-8")
    pr_map = _extract_pr_branch_map(claude_text)

    if not pr_map:
        return ["[v0.9.0-release] could not parse v0.9.0 PR table from CLAUDE.md"]

    for rel in _V090_RELEASE_FILES:
        path = REPO_ROOT / rel
        if not path.exists():
            errors.append(f"[v0.9.0-release] missing required file: {rel}")
            continue

        text = path.read_text(encoding="utf-8")
        actual_pr_map = _extract_pr_branch_map(text)
        if not actual_pr_map:
            errors.append(
                f"[v0.9.0-release] {rel}: could not parse a v0.9.0 PR table"
            )
        else:
            errors.extend(_compare_pr_branch_maps(rel, pr_map, actual_pr_map))

        if not _STOP_SHIP_RE.search(text):
            errors.append(
                f"[v0.9.0-release] {rel}: missing explicit PR-07 stop-ship rule"
            )

        if not _has_freeze_go_coupling(text):
            errors.append(
                f"[v0.9.0-release] {rel}: missing explicit origin/main freeze "
                f"language tied to formal GO"
            )

    return errors


# ---------------------------------------------------------------------------
# Check L: v0.9.0 PR-02 contract freeze truth
# ---------------------------------------------------------------------------

_V090_PR02_ACTIVE_BRANCH = "feat/v0.9-02-contract-freeze"
_V090_PLAN_REL = "docs/plans/AIGC V0.9.0 IMPLEMENTATION_PLAN.md"
_V090_HLD_REL = "docs/architecture/AIGC_HIGH_LEVEL_DESIGN.md"
_V090_PUBLIC_CONTRACT_REL = "docs/PUBLIC_INTEGRATION_CONTRACT.md"
_V090_PR_CONTEXT_REL = "docs/dev/pr_context.md"
_V090_EXPECTED_SESSION_STATES = [
    "OPEN",
    "PAUSED",
    "FAILED",
    "COMPLETED",
    "CANCELED",
    "FINALIZED",
]
_V090_EXPECTED_WORKFLOW_STATUSES = [
    "COMPLETED",
    "FAILED",
    "CANCELED",
    "INCOMPLETE",
]


def _normalize_inline_markdown(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("`", "")).strip()


def _extract_bullets_after_label(text: str, label: str) -> list[str] | None:
    idx = text.find(label)
    if idx == -1:
        return None

    items: list[str] = []
    started = False
    for raw_line in text[idx + len(label):].splitlines():
        stripped = raw_line.strip()
        if not stripped:
            if started:
                break
            continue
        if stripped.startswith("- "):
            items.append(_normalize_inline_markdown(stripped[2:]))
            started = True
            continue
        if started:
            break

    return items if items else None


def _extract_numbered_items_after_label(text: str, label: str) -> list[str] | None:
    idx = text.find(label)
    if idx == -1:
        return None

    items: list[str] = []
    started = False
    for raw_line in text[idx + len(label):].splitlines():
        stripped = raw_line.strip()
        # Deliberately match _extract_bullets_after_label(): once list parsing
        # has started, a blank line terminates the list instead of being
        # skipped. Keep numbered lists contiguous in contract docs.
        if not stripped:
            if started:
                break
            continue
        match = re.match(r"^\d+\.\s+(.*)$", stripped)
        if match:
            items.append(_normalize_inline_markdown(match.group(1)))
            started = True
            continue
        if started:
            break

    return items if items else None


def _require_all(
    errors: list[str],
    rel: str,
    text: str,
    required: list[str],
    label: str,
    error_prefix: str = "[v0.9.0-pr02]",
) -> None:
    normalized_text = re.sub(r"\s+", " ", text)
    for needle in required:
        normalized_needle = re.sub(r"\s+", " ", needle)
        if normalized_needle not in normalized_text:
            errors.append(f"{error_prefix} {rel}: missing {label}: {needle}")


def _check_exact_list(
    errors: list[str],
    rel: str,
    text: str,
    label: str,
    expected: list[str],
    name: str,
    error_prefix: str = "[v0.9.0-pr02]",
) -> None:
    actual = _extract_bullets_after_label(text, label)
    if actual is None:
        errors.append(f"{error_prefix} {rel}: could not find {name} list")
        return
    if actual != expected:
        errors.append(
            f"{error_prefix} {rel}: {name} list {actual} does not match "
            f"expected {expected}"
        )


def _check_exact_numbered_list(
    errors: list[str],
    rel: str,
    text: str,
    label: str,
    expected: list[str],
    name: str,
) -> None:
    actual = _extract_numbered_items_after_label(text, label)
    if actual is None:
        errors.append(f"[v0.9.0-pr03] {rel}: could not find {name} list")
        return
    if actual != expected:
        errors.append(
            f"[v0.9.0-pr03] {rel}: {name} list {actual} does not match "
            f"expected {expected}"
        )


def check_v090_pr02_contract() -> list[str]:
    """Ensure PR-02 freezes the intended workflow contract without shipping it."""
    errors: list[str] = []

    required_files = [
        _V090_PLAN_REL,
        _V090_HLD_REL,
        "README.md",
        _V090_PUBLIC_CONTRACT_REL,
        _V090_PR_CONTEXT_REL,
        "RELEASE_GATES.md",
        "implementation_status.md",
    ]
    texts: dict[str, str] = {}
    for rel in required_files:
        text = _read_text(rel)
        if not text:
            errors.append(f"[v0.9.0-pr02] missing required file: {rel}")
            continue
        texts[rel] = text

    if errors:
        return errors

    _check_exact_list(
        errors,
        _V090_PLAN_REL,
        texts[_V090_PLAN_REL],
        "Canonical session lifecycle states:",
        _V090_EXPECTED_SESSION_STATES,
        "session lifecycle states",
    )
    _check_exact_list(
        errors,
        _V090_HLD_REL,
        texts[_V090_HLD_REL],
        "Canonical lifecycle states:",
        _V090_EXPECTED_SESSION_STATES,
        "session lifecycle states",
    )
    _check_exact_list(
        errors,
        _V090_PLAN_REL,
        texts[_V090_PLAN_REL],
        "Canonical workflow artifact `status` values:",
        _V090_EXPECTED_WORKFLOW_STATUSES,
        "workflow artifact statuses",
    )
    _check_exact_list(
        errors,
        _V090_HLD_REL,
        texts[_V090_HLD_REL],
        "Canonical serialized workflow artifact `status` values:",
        _V090_EXPECTED_WORKFLOW_STATUSES,
        "workflow artifact statuses",
    )

    _require_all(
        errors,
        _V090_PLAN_REL,
        texts[_V090_PLAN_REL],
        [
            "- `FINALIZED` is a lifecycle state only and is never serialized as an artifact status.",
            "- `finalize()` from `OPEN` or `PAUSED` is allowed and emits `INCOMPLETE`.",
            "- `v0.9.0` does not introduce a new module-level `open_session(...)` public API.",
            "PR-02 documents and tests them; it does not ship placeholder runtime stubs.",
            "- A wrapped token cannot be completed through module-level `enforce_post_call(...)`; it must be completed through the owning `GovernanceSession`.",
            "- Session completion validates both underlying invocation integrity and workflow-step binding before post-call enforcement proceeds.",
            "- Governed Bedrock handoffs require alias-backed participant identity.",
            "- Descriptive names such as `collaboratorName` are descriptive evidence only and cannot be the sole binding key for governed authorization.",
            "- gRPC is out of scope for `v0.9.0` normalization and must fail with a typed protocol violation.",
            "- Compatibility is validated from `supportedInterfaces[].protocolVersion`, not descriptive Agent Card version text.",
            "- Wire task states must validate as normative ProtoJSON `TASK_STATE_*` values.",
            "- Informal or shorthand task-state names are rejected at the boundary.",
        ],
        "frozen plan contract",
    )
    _require_all(
        errors,
        _V090_HLD_REL,
        texts[_V090_HLD_REL],
        [
            "`SessionPreCallResult`",
            "`AIGC.open_session(...)`\nis not part of the installable runtime yet.",
            "The target design does not add a module-level `open_session(...)` convenience.",
            "| `OPEN` or `PAUSED` finalized without terminal completion | `INCOMPLETE` |",
            "- alias-backed collaborator identity is required for governed participant\n  binding; `collaboratorName` alone is descriptive evidence only",
            "- when policy requires trace, Bedrock trace is mandatory and missing trace\n  fails closed",
            "- `GRPC`",
            "- compatibility is validated from `supportedInterfaces[].protocolVersion`, not\n  descriptive Agent Card version text",
            "- non-normative or shorthand task-state names are rejected at the boundary",
        ],
        "frozen HLD contract",
    )
    _require_all(
        errors,
        "README.md",
        texts["README.md"],
        [
            "`AIGC.open_session(...)`",
            "`GovernanceSession`",
            "`SessionPreCallResult`",
            "not\npart of the shipped `v0.3.3` runtime or CLI",
        ],
        "planned-only README boundary",
    )
    _require_all(
        errors,
        _V090_PUBLIC_CONTRACT_REL,
        texts[_V090_PUBLIC_CONTRACT_REL],
        [
            "`AIGC.open_session(...)`",
            "`SessionPreCallResult`",
            "There is no current\nmodule-level `open_session()` convenience in the shipped package.",
        ],
        "planned-only public integration boundary",
    )
    _require_all(
        errors,
        _V090_PR_CONTEXT_REL,
        texts[_V090_PR_CONTEXT_REL],
        [
            f"Active branch: `{_V090_PR02_ACTIVE_BRANCH}`",
            "- docs, CI, and sentinel tests only",
            "- PR-02 is docs, CI, and sentinel tests only. Workflow runtime implementation\n  starts in PR-04.",
        ],
        "PR-02 branch and scope",
    )
    _require_all(
        errors,
        "RELEASE_GATES.md",
        texts["RELEASE_GATES.md"],
        [
            "## PR-02 — Contract Freeze Gate",
            "- [ ] public-surface sentinel tests confirm no workflow runtime or workflow CLI\n      surface shipped early",
            "- [ ] protocol-boundary contract tests freeze Bedrock and A2A fail-closed\n      rules without runtime adapters",
        ],
        "PR-02 release gate",
    )
    _require_all(
        errors,
        "implementation_status.md",
        texts["implementation_status.md"],
        [
            f"**Active Branch:** `{_V090_PR02_ACTIVE_BRANCH}`",
            "- PR-02 is contract freeze only. It updates docs, CI, and sentinel tests only.",
            "- Workflow runtime implementation begins in PR-04.",
            "## PR-02 Deliverables",
        ],
        "PR-02 implementation status",
    )

    return errors


# ---------------------------------------------------------------------------
# Check M: v0.9.0 PR-03 golden-path contract truth
# ---------------------------------------------------------------------------

_V090_PR03_ACTIVE_BRANCH = "feat/v0.9-03-golden-path-contract"
_V090_PR04_ACTIVE_BRANCH = "feat/v0.9-04-minimal-session-flow"
_V090_PR05_ACTIVE_BRANCH = "feat/v0.9-05-starters-and-migration"
_V090_PR05_PUBLIC_CONTRACT_REL = "docs/PUBLIC_INTEGRATION_CONTRACT.md"
_V090_PROJECT_MD_REL = "PROJECT.md"
_V090_ENFORCEMENT_PIPELINE_REL = "docs/architecture/ENFORCEMENT_PIPELINE.md"
_V090_PR03_EXPECTED_CLI_COMMANDS = [
    "aigc policy init",
    "aigc workflow init",
    "aigc workflow lint",
    "aigc workflow doctor",
    "aigc workflow trace",
    "aigc workflow export",
]
_V090_PR03_EXPECTED_SCAFFOLD_PROFILES = [
    "minimal",
    "standard",
    "regulated-high-assurance",
]
_V090_PR03_EXPECTED_STARTER_COVERAGE = [
    "local multi-step review",
    "approval checkpoint",
    "source required",
    "tool budget",
]
_V090_PR03_EXPECTED_REASON_CODES = [
    "WORKFLOW_INVALID_TRANSITION",
    "WORKFLOW_APPROVAL_REQUIRED",
    "WORKFLOW_SOURCE_REQUIRED",
    "WORKFLOW_TOOL_BUDGET_EXCEEDED",
    "WORKFLOW_UNSUPPORTED_BINDING",
    "WORKFLOW_SESSION_TOKEN_INVALID",
    "WORKFLOW_STARTER_INTEGRITY_ERROR",
]
_V090_PR03_EXPECTED_DOCS_ORDER = [
    "workflow quickstart",
    "migration from invocation-only to workflow",
    "troubleshooting and workflow doctor / workflow lint guide",
    "starter recipes and starter index",
    "workflow CLI guide",
    "public API boundary and integration contract",
    "supported environments",
    "operations runbook",
    "adapter docs as advanced follow-on material",
]


def check_v090_pr03_contract() -> list[str]:
    """Ensure PR-03 freezes the first-adopter contract without shipping it."""
    errors: list[str] = []

    required_files = [
        _V090_PLAN_REL,
        _V090_HLD_REL,
        "README.md",
        _V090_PUBLIC_CONTRACT_REL,
        _V090_PR_CONTEXT_REL,
        "RELEASE_GATES.md",
        "implementation_status.md",
    ]
    texts: dict[str, str] = {}
    for rel in required_files:
        text = _read_text(rel)
        if not text:
            errors.append(f"[v0.9.0-pr03] missing required file: {rel}")
            continue
        texts[rel] = text

    if errors:
        return errors

    for rel in (_V090_PLAN_REL, _V090_HLD_REL):
        text = texts[rel]
        _check_exact_list(
            errors,
            rel,
            text,
            "Frozen CLI command inventory:",
            _V090_PR03_EXPECTED_CLI_COMMANDS,
            "CLI command inventory",
            error_prefix="[v0.9.0-pr03]",
        )
        _check_exact_list(
            errors,
            rel,
            text,
            "Frozen scaffold profiles:",
            _V090_PR03_EXPECTED_SCAFFOLD_PROFILES,
            "scaffold profiles",
            error_prefix="[v0.9.0-pr03]",
        )
        _check_exact_list(
            errors,
            rel,
            text,
            "Required starter coverage:",
            _V090_PR03_EXPECTED_STARTER_COVERAGE,
            "starter coverage",
            error_prefix="[v0.9.0-pr03]",
        )
        _check_exact_list(
            errors,
            rel,
            text,
            "Frozen first-user diagnostic reason codes:",
            _V090_PR03_EXPECTED_REASON_CODES,
            "first-user reason codes",
            error_prefix="[v0.9.0-pr03]",
        )
        _check_exact_numbered_list(
            errors,
            rel,
            text,
            "Frozen first-adopter docs order:",
            _V090_PR03_EXPECTED_DOCS_ORDER,
            "first-adopter docs order",
        )

    _require_all(
        errors,
        _V090_PLAN_REL,
        texts[_V090_PLAN_REL],
        [
            "- Hand-authored workflow DSL remains supported but is advanced mode.",
            "- Public examples, quickstarts, starter assets, presets, recipes, and demo code must use only public APIs and must never import from `aigc._internal`.",
        ],
        "frozen plan golden-path rules",
        error_prefix="[v0.9.0-pr03]",
    )
    _require_all(
        errors,
        _V090_HLD_REL,
        texts[_V090_HLD_REL],
        [
            "- hand-authored workflow DSL remains supported as advanced mode and is not required for the default path",
            "- public quickstarts, starter packs, presets, demo code, and docs snippets must use public `aigc` imports only and must not depend on `aigc._internal`",
            "`aigc policy init`",
        ],
        "frozen HLD golden-path rules",
        error_prefix="[v0.9.0-pr03]",
    )
    _require_all(
        errors,
        "README.md",
        texts["README.md"],
        [
            "`aigc policy init`",
            "`aigc workflow init`",
            "`aigc workflow lint`",
            "`aigc workflow doctor`",
            "`aigc workflow trace`",
            "`aigc workflow export`",
            "none of those workflow surfaces are part of the shipped `v0.3.3` runtime or CLI",
        ],
        "planned-only README CLI boundary",
        error_prefix="[v0.9.0-pr03]",
    )
    _require_all(
        errors,
        _V090_PUBLIC_CONTRACT_REL,
        texts[_V090_PUBLIC_CONTRACT_REL],
        [
            "`aigc policy init`",
            "`aigc workflow ...` commands",
            "must use public `aigc` imports only and must not depend on `aigc._internal`",
        ],
        "planned-only public integration boundary",
        error_prefix="[v0.9.0-pr03]",
    )
    _require_all(
        errors,
        _V090_PR_CONTEXT_REL,
        texts[_V090_PR_CONTEXT_REL],
        [
            f"Active branch: `{_V090_PR03_ACTIVE_BRANCH}`",
            "- docs, CI, sentinel tests, and public-import hygiene only",
            "- The frozen golden-path CLI inventory is `aigc policy init`,",
            "- PR-03 is docs, CI, sentinel tests, and public-import hygiene only. Workflow\n  runtime implementation still starts in PR-04.",
        ],
        "PR-03 branch and scope",
        error_prefix="[v0.9.0-pr03]",
    )
    _require_all(
        errors,
        "RELEASE_GATES.md",
        texts["RELEASE_GATES.md"],
        [
            "## PR-03 — Golden-Path Contract Freeze Gate",
            "- [ ] staged CLI sentinel tests prove the current shipped CLI still exposes no\n      `workflow` or `policy init` commands while freezing the future command\n      names in docs",
            "- [ ] public-import boundary tests confirm maintained onboarding examples and\n      demo code use public `aigc` imports only",
        ],
        "PR-03 release gate",
        error_prefix="[v0.9.0-pr03]",
    )
    _require_all(
        errors,
        "implementation_status.md",
        texts["implementation_status.md"],
        [
            f"**Active Branch:** `{_V090_PR03_ACTIVE_BRANCH}`",
            "- PR-03 is golden-path contract freeze only. It updates docs, CI, sentinel\n  tests, and public-import hygiene only.",
            "## PR-03 Deliverables",
        ],
        "PR-03 implementation status",
        error_prefix="[v0.9.0-pr03]",
    )

    return errors


def check_v090_pr04_contract() -> list[str]:
    """Verify PR-04 doc state: session surfaces described as upcoming v0.9.0-beta, not shipped."""
    errors: list[str] = []

    required_files = [
        _V090_PLAN_REL,
        _V090_HLD_REL,
        "README.md",
        _V090_PUBLIC_CONTRACT_REL,
        _V090_PR_CONTEXT_REL,
        "RELEASE_GATES.md",
        "implementation_status.md",
        _V090_PROJECT_MD_REL,
        _V090_ENFORCEMENT_PIPELINE_REL,
    ]
    texts: dict[str, str] = {}
    for rel in required_files:
        text = _read_text(rel)
        if not text:
            errors.append(f"[v0.9.0-pr04] missing required file: {rel}")
            continue
        texts[rel] = text

    if errors:
        return errors

    pfx = "[v0.9.0-pr04]"

    # -- Active branch --
    _require_all(
        errors,
        _V090_PR_CONTEXT_REL,
        texts[_V090_PR_CONTEXT_REL],
        [f"Active branch: `{_V090_PR04_ACTIVE_BRANCH}`"],
        "PR-04 active branch",
        error_prefix=pfx,
    )
    _require_all(
        errors,
        "implementation_status.md",
        texts["implementation_status.md"],
        [f"**Active Branch:** `{_V090_PR04_ACTIVE_BRANCH}`"],
        "PR-04 active branch",
        error_prefix=pfx,
    )

    # -- README: positive assertion that surfaces are described as upcoming v0.9.0-beta --
    _require_all(
        errors,
        "README.md",
        texts["README.md"],
        ["upcoming unreleased v0.9.0-beta"],
        "upcoming v0.9.0-beta wording (positive assertion required — absence of old wording is not sufficient)",
        error_prefix=pfx,
    )
    # README: old planned-only language must be gone
    for forbidden in [
        "none of those workflow surfaces are part of the shipped `v0.3.3` runtime or CLI",
    ]:
        normalized = re.sub(r"\s+", " ", texts["README.md"])
        if re.sub(r"\s+", " ", forbidden) in normalized:
            errors.append(
                f"{pfx} README.md: must not contain old planned-only language: {forbidden!r}"
            )

    # -- PUBLIC_INTEGRATION_CONTRACT: v0.9.0-beta paragraph present, old listing gone --
    _require_all(
        errors,
        _V090_PUBLIC_CONTRACT_REL,
        texts[_V090_PUBLIC_CONTRACT_REL],
        ["planned for the upcoming unreleased v0.9.0-beta line"],
        "v0.9.0-beta planned paragraph (positive assertion required)",
        error_prefix=pfx,
    )
    for forbidden in [
        "not part of the installable `v0.3.3` artifact today",
    ]:
        normalized = re.sub(r"\s+", " ", texts[_V090_PUBLIC_CONTRACT_REL])
        if re.sub(r"\s+", " ", forbidden) in normalized:
            errors.append(
                f"{pfx} {_V090_PUBLIC_CONTRACT_REL}: must not retain old planned-only listing: {forbidden!r}"
            )

    # -- HLD: "Planned for v0.9.0-beta (not yet released)" row set present, old unqualified table gone --
    _require_all(
        errors,
        _V090_HLD_REL,
        texts[_V090_HLD_REL],
        ["Planned for v0.9.0-beta (not yet released)"],
        "HLD v0.9.0-beta planned row set (positive assertion required)",
        error_prefix=pfx,
    )
    for forbidden in [
        "Planned-only additions for `1.0.0` — not exported by `0.3.3`",
    ]:
        normalized = re.sub(r"\s+", " ", texts[_V090_HLD_REL])
        if re.sub(r"\s+", " ", forbidden) in normalized:
            errors.append(
                f"{pfx} {_V090_HLD_REL}: must not retain old unqualified planned-only table header: {forbidden!r}"
            )

    # -- PROJECT.md: upcoming v0.9.0-beta wording present, old stale phrase gone --
    _require_all(
        errors,
        _V090_PROJECT_MD_REL,
        texts[_V090_PROJECT_MD_REL],
        ["upcoming unreleased v0.9.0-beta"],
        "PROJECT.md upcoming v0.9.0-beta wording (positive assertion required)",
        error_prefix=pfx,
    )
    for forbidden in [
        "does not yet ship the planned `GovernanceSession` workflow runtime",
    ]:
        normalized = re.sub(r"\s+", " ", texts[_V090_PROJECT_MD_REL])
        if re.sub(r"\s+", " ", forbidden) in normalized:
            errors.append(
                f"{pfx} {_V090_PROJECT_MD_REL}: must not contain stale phrase: {forbidden!r}"
            )

    # -- ENFORCEMENT_PIPELINE.md: upcoming v0.9.0-beta wording present, old phrases gone --
    _require_all(
        errors,
        _V090_ENFORCEMENT_PIPELINE_REL,
        texts[_V090_ENFORCEMENT_PIPELINE_REL],
        ["upcoming unreleased v0.9.0-beta"],
        "ENFORCEMENT_PIPELINE.md upcoming v0.9.0-beta wording (positive assertion required)",
        error_prefix=pfx,
    )
    for forbidden in [
        "future session model",
        "not a shipped `GovernanceSession` workflow runtime",
    ]:
        normalized = re.sub(r"\s+", " ", texts[_V090_ENFORCEMENT_PIPELINE_REL])
        if re.sub(r"\s+", " ", forbidden) in normalized:
            errors.append(
                f"{pfx} {_V090_ENFORCEMENT_PIPELINE_REL}: must not contain old unqualified phrase: {forbidden!r}"
            )

    return errors


def check_v090_pr05_contract() -> list[str]:
    """Verify PR-05 deliverables remain present: starters-and-migration surfaces are shipped."""
    errors: list[str] = []

    required_files = [
        _V090_PR05_PUBLIC_CONTRACT_REL,
        "README.md",
        _V090_HLD_REL,
        "implementation_status.md",
    ]
    texts: dict[str, str] = {}
    for rel in required_files:
        text = _read_text(rel)
        if not text:
            errors.append(f"[v0.9.0-pr05] missing required file: {rel}")
            continue
        texts[rel] = text

    if errors:
        return errors

    pfx = "[v0.9.0-pr05]"

    # -- PUBLIC_INTEGRATION_CONTRACT: PR-05 surfaces present, CLI entries removed from beyond-beta --
    _require_all(
        errors,
        _V090_PR05_PUBLIC_CONTRACT_REL,
        texts[_V090_PR05_PUBLIC_CONTRACT_REL],
        ["aigc workflow init", "aigc policy init", "MinimalPreset"],
        "PR-05 surfaces in PUBLIC_INTEGRATION_CONTRACT",
        error_prefix=pfx,
    )
    # CLI commands must no longer appear in the "beyond v0.9.0-beta" beyond-listing
    for forbidden in ["aigc policy init`, and `aigc workflow ...", "aigc workflow ...`\ncommands"]:
        normalized = re.sub(r"\s+", " ", texts[_V090_PR05_PUBLIC_CONTRACT_REL])
        if re.sub(r"\s+", " ", forbidden) in normalized:
            errors.append(
                f"{pfx} {_V090_PR05_PUBLIC_CONTRACT_REL}: "
                f"must not retain CLI commands in beyond-beta listing: {forbidden!r}"
            )

    # -- README.md: both shipped CLI commands present; planned-only listing updated --
    _require_all(
        errors,
        "README.md",
        texts["README.md"],
        ["aigc workflow init", "aigc policy init"],
        "PR-05 shipped CLI commands in README (positive assertion required)",
        error_prefix=pfx,
    )
    for forbidden in [
        "aigc policy init`, `aigc workflow init`",
    ]:
        normalized_readme = re.sub(r"\s+", " ", texts["README.md"])
        if re.sub(r"\s+", " ", forbidden) in normalized_readme:
            errors.append(
                f"{pfx} README.md: planned-only sentence not updated: {forbidden!r}"
            )

    # -- AIGC_HIGH_LEVEL_DESIGN.md: both shipped commands present; planned-only sentence updated --
    _require_all(
        errors,
        _V090_HLD_REL,
        texts[_V090_HLD_REL],
        ["aigc workflow init", "aigc policy init"],
        "PR-05 shipped CLI commands in HLD (positive assertion required)",
        error_prefix=pfx,
    )
    # The old planned-only sentence (whitespace-normalized): check it is gone
    normalized_hld = re.sub(r"\s+", " ", texts[_V090_HLD_REL])
    for forbidden in [
        "`aigc policy init`, and `aigc workflow ...` commands remain planned-only",
    ]:
        if re.sub(r"\s+", " ", forbidden) in normalized_hld:
            errors.append(
                f"{pfx} {_V090_HLD_REL}: planned-only sentence not updated: {forbidden!r}"
            )

    # -- implementation_status.md: PR-05 complete and starters row present --
    _require_all(
        errors,
        "implementation_status.md",
        texts["implementation_status.md"],
        ["PR-01 through PR-06 are complete", "Starters and migration"],
        "PR-01 through PR-06 complete + starters row",
        error_prefix=pfx,
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
        ("H. Implementation-truth consistency", lambda: check_implementation_truth(manifest)),
        ("I. Semantic behavioral claims", check_semantic_claims),
        ("J. v0.9.0 plan truth", check_v090_plan_truth),
        ("K. v0.9.0 release truth", check_v090_release_truth),
        ("L. v0.9.0 PR-05 starters-and-migration contract truth", check_v090_pr05_contract),
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
