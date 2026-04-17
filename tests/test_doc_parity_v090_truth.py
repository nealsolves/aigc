from __future__ import annotations

import importlib.util
import textwrap
from pathlib import Path

import pytest


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "check_doc_parity.py"


def _load_doc_parity_module():
    spec = importlib.util.spec_from_file_location("check_doc_parity_test", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_file(root: Path, rel: str, content: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).strip() + "\n", encoding="utf-8")


REFERENCE_TABLE = """
| PR | Branch | Goal |
|----|--------|------|
| PR-01 | `feat/v0.9-01-source-of-truth` | Canonical plan, release packet, and CI truth checks |
| PR-07 | `feat/v0.9-07-beta-proof` | Mandatory stop-ship checkpoint |
| PR-11 | `feat/v0.9-11-beta-freeze` -> `release/v0.9.0` | Final beta freeze and release cut |
"""

FREEZE_GO_RULE = """
Do NOT open or merge a PR from `origin/develop` -> `origin/main` until
`v0.9.0` is formally declared a GO.
"""

STOP_SHIP_RULE = """
PR-07 is the mandatory stop-ship checkpoint. If the golden path fails there,
no further public-surface work proceeds until the default path is repaired.
"""


def _make_release_doc(
    *,
    table: str = REFERENCE_TABLE,
    freeze_rule: str = FREEZE_GO_RULE,
    stop_ship_rule: str = STOP_SHIP_RULE,
    extra: str = "",
) -> str:
    table = textwrap.dedent(table).strip()
    freeze_rule = textwrap.dedent(freeze_rule).strip()
    stop_ship_rule = textwrap.dedent(stop_ship_rule).strip()
    extra = textwrap.dedent(extra).strip()
    return f"""
    # Release Truth

    {freeze_rule}

    ## PR Table

    {table}

    {stop_ship_rule}

    {extra}
    """


def _seed_release_truth_repo(root: Path, *, pr_context: str, release_gates: str,
                             implementation_status: str) -> None:
    _write_file(
        root,
        "CLAUDE.md",
        _make_release_doc(extra="Active branch: `feat/v0.9-01-source-of-truth`"),
    )
    _write_file(root, "docs/dev/pr_context.md", pr_context)
    _write_file(root, "RELEASE_GATES.md", release_gates)
    _write_file(root, "implementation_status.md", implementation_status)


def test_v090_release_truth_accepts_exact_row_mapping_and_coupled_freeze(tmp_path, monkeypatch):
    module = _load_doc_parity_module()
    monkeypatch.setattr(module, "REPO_ROOT", tmp_path)

    good_doc = _make_release_doc(extra="Active branch: `feat/v0.9-01-source-of-truth`")
    _seed_release_truth_repo(
        tmp_path,
        pr_context=good_doc,
        release_gates=good_doc,
        implementation_status=good_doc,
    )

    assert module.check_v090_release_truth() == []


def test_v090_release_truth_rejects_row_level_pr_branch_mismatch(tmp_path, monkeypatch):
    module = _load_doc_parity_module()
    monkeypatch.setattr(module, "REPO_ROOT", tmp_path)

    mismatched_table = """
    | PR | Branch | Goal |
    |----|--------|------|
    | PR-01 | `feat/v0.9-07-beta-proof` | Wrong branch mapping |
    | PR-07 | `feat/v0.9-07-beta-proof` | Mandatory stop-ship checkpoint |
    | PR-11 | `feat/v0.9-11-beta-freeze` -> `release/v0.9.0` | Final beta freeze and release cut |
    """
    mismatched_doc = _make_release_doc(
        table=mismatched_table,
        extra="Active branch: `feat/v0.9-01-source-of-truth`",
    )
    good_doc = _make_release_doc(extra="Active branch: `feat/v0.9-01-source-of-truth`")

    _seed_release_truth_repo(
        tmp_path,
        pr_context=mismatched_doc,
        release_gates=good_doc,
        implementation_status=good_doc,
    )

    errors = module.check_v090_release_truth()
    joined = "\n".join(errors)

    assert "docs/dev/pr_context.md: PR-01 row maps to" in joined, errors


_CANONICAL_PLAN_REL = "docs/plans/AIGC V0.9.0 IMPLEMENTATION_PLAN.md"
_HISTORICAL_PLAN_RELS = [
    "docs/plans/0.9.0 plan backup.md",
    "docs/plans/AIGC V0.9.0 IMPLEMENTATION_PLAN_DRAFT.md",
    "docs/plans/AIGC V0.9.0 IMPLEMENTATION_PLAN_DRAFT_ORIG.md",
    "docs/plans/AIGC_v0.9.0_IMPLEMENTATION_PLAN_UPDATED.md",
]

_CANONICAL_PLAN_CONTENT = """\
# AIGC v0.9.0 Implementation Plan

This document is the canonical implementation plan for the v0.9.0 beta.
"""

_HISTORICAL_PLAN_CONTENT = (
    "> Superseded on 2026-04-15.\n"
    f"> Active file: `{_CANONICAL_PLAN_REL}`.\n"
    "> Status: historical input only for PR-01 source-of-truth review.\n"
)


def _seed_plan_truth_repo(
    root: Path, *, canonical_content: str, stale_content: str
) -> None:
    _write_file(root, _CANONICAL_PLAN_REL, canonical_content)
    for rel in _HISTORICAL_PLAN_RELS:
        _write_file(root, rel, stale_content)


def test_v090_plan_truth_accepts_one_canonical_and_marked_stale_variants(
    tmp_path, monkeypatch
):
    module = _load_doc_parity_module()
    monkeypatch.setattr(module, "REPO_ROOT", tmp_path)

    _seed_plan_truth_repo(
        tmp_path,
        canonical_content=_CANONICAL_PLAN_CONTENT,
        stale_content=_HISTORICAL_PLAN_CONTENT,
    )

    assert module.check_v090_plan_truth() == []


def test_v090_plan_truth_rejects_stale_plan_missing_supersession_banner(
    tmp_path, monkeypatch
):
    module = _load_doc_parity_module()
    monkeypatch.setattr(module, "REPO_ROOT", tmp_path)

    no_banner = "# AIGC v0.9.0 Draft\n\nNo supersession notice.\n"

    _seed_plan_truth_repo(
        tmp_path,
        canonical_content=_CANONICAL_PLAN_CONTENT,
        stale_content=no_banner,
    )

    errors = module.check_v090_plan_truth()
    joined = "\n".join(errors)
    assert "stale plan is not marked superseded" in joined, errors


def test_v090_release_truth_rejects_uncoupled_freeze_and_go_statements(tmp_path, monkeypatch):
    module = _load_doc_parity_module()
    monkeypatch.setattr(module, "REPO_ROOT", tmp_path)

    uncoupled_freeze = """
    Do NOT open or merge a PR from `origin/develop` -> `origin/main`.

    `v0.9.0` is formally declared a GO by the release review.
    """
    uncoupled_doc = _make_release_doc(freeze_rule=uncoupled_freeze)
    good_doc = _make_release_doc(extra="Active branch: `feat/v0.9-01-source-of-truth`")

    _seed_release_truth_repo(
        tmp_path,
        pr_context=good_doc,
        release_gates=uncoupled_doc,
        implementation_status=good_doc,
    )

    errors = module.check_v090_release_truth()

    assert any(
        "RELEASE_GATES.md: missing explicit origin/main freeze language tied to formal GO"
        in error
        for error in errors
    )


_PR02_PLAN_CONTENT = """\
# AIGC v0.9.0 Implementation Plan

### Public surface and migration posture

- `v0.9.0` does not introduce a new module-level `open_session(...)` public API.
- `GovernanceSession`, `SessionPreCallResult`, and `AIGC.open_session(...)`
  are frozen as planned-only contract surfaces before runtime work lands.
  PR-02 documents and tests them; it does not ship placeholder runtime stubs.

### Session and artifact semantics

Canonical session lifecycle states:

- `OPEN`
- `PAUSED`
- `FAILED`
- `COMPLETED`
- `CANCELED`
- `FINALIZED`

Canonical workflow artifact `status` values:

- `COMPLETED`
- `FAILED`
- `CANCELED`
- `INCOMPLETE`

Rules:

- `FINALIZED` is a lifecycle state only and is never serialized as an artifact status.
- `finalize()` from `OPEN` or `PAUSED` is allowed and emits `INCOMPLETE`.

### `SessionPreCallResult` semantics

- `SessionPreCallResult` wraps a valid invocation `PreCallResult` plus immutable `session_id`, `step_id`, `participant_id`, and workflow-bound replay protection.
- The wrapper is single-use.
- A wrapped token cannot be completed through module-level `enforce_post_call(...)`; it must be completed through the owning `GovernanceSession`.
- Session completion validates both underlying invocation integrity and workflow-step binding before post-call enforcement proceeds.

### Bedrock contract lock

- Governed Bedrock handoffs require alias-backed participant identity.
- Descriptive names such as `collaboratorName` are descriptive evidence only and cannot be the sole binding key for governed authorization.

### A2A contract lock

- gRPC is out of scope for `v0.9.0` normalization and must fail with a typed protocol violation.
- Compatibility is validated from `supportedInterfaces[].protocolVersion`, not descriptive Agent Card version text.
- Wire task states must validate as normative ProtoJSON `TASK_STATE_*` values.
- Informal or shorthand task-state names are rejected at the boundary.
"""

_PR02_HLD_CONTENT = """\
# AIGC High-Level Design

Availability boundary: this document describes the intended `1.0.0` public
surface. The shipped `0.3.3` package and CLI do not yet export
`GovernanceSession`, `SessionPreCallResult`, `AgentIdentity`,
`AgentCapabilityManifest`, `ValidatorHook`, `BedrockTraceAdapter`,
`A2AAdapter`, or `aigc workflow ...` commands, and `AIGC.open_session(...)`
is not part of the installable runtime yet.

### 7.1 Session Lifecycle

Canonical lifecycle states:

- `OPEN`
- `PAUSED`
- `FAILED`
- `COMPLETED`
- `CANCELED`
- `FINALIZED`

Canonical serialized workflow artifact `status` values:

- `COMPLETED`
- `FAILED`
- `CANCELED`
- `INCOMPLETE`

| Lifecycle condition when the workflow artifact is emitted | Serialized `status` |
| --------------------------------------------------------- | ------------------- |
| `OPEN` or `PAUSED` finalized without terminal completion | `INCOMPLETE` |

Rules:

- `FINALIZED` is a lifecycle state only. It is never serialized as a workflow artifact `status`.

Workflow adoption remains instance-scoped through `AIGC.open_session(...)`.
The target design does not add a module-level `open_session(...)` convenience.

### 10.1 Bedrock Adapter

- when policy requires trace, Bedrock trace is mandatory and missing trace fails closed
- alias-backed collaborator identity is required for governed participant binding; `collaboratorName` alone is descriptive evidence only

### 10.2 A2A Adapter

- `GRPC`

- compatibility is validated from `supportedInterfaces[].protocolVersion`, not descriptive Agent Card version text
- non-normative or shorthand task-state names are rejected at the boundary
"""

_PR02_README_CONTENT = """\
# README

The target-state `1.0.0` architecture expands this invocation-first model with
planned workflow governance built around `AIGC.open_session(...)`,
`GovernanceSession`, `SessionPreCallResult`, and optional Bedrock/A2A
normalization adapters. These remain planned-only surfaces today and are not
part of the shipped `v0.3.3` runtime or CLI.
"""

_PR02_PUBLIC_CONTRACT_CONTENT = """\
# Public Contract

Planned-only surfaces described in that target-state document — including
`AIGC.open_session(...)`, `GovernanceSession`, `SessionPreCallResult`,
`AgentIdentity`, `AgentCapabilityManifest`, `ValidatorHook`,
`BedrockTraceAdapter`, `A2AAdapter`, and `aigc workflow ...` commands — are
not part of the installable `v0.3.3` artifact today. There is no current
module-level `open_session()` convenience in the shipped package.
"""

_PR02_PR_CONTEXT_CONTENT = """\
# PR Context

Active branch: `feat/v0.9-02-contract-freeze`

PR type:

- docs, CI, and sentinel tests only

Contract Notes

- PR-02 is docs, CI, and sentinel tests only. Workflow runtime implementation
  starts in PR-04.
"""

_PR02_RELEASE_GATES_CONTENT = """\
# Release Gates

## PR-02 — Contract Freeze Gate

- [ ] public-surface sentinel tests confirm no workflow runtime or workflow CLI
      surface shipped early
- [ ] protocol-boundary contract tests freeze Bedrock and A2A fail-closed
      rules without runtime adapters
"""

_PR02_IMPLEMENTATION_STATUS_CONTENT = """\
# Implementation Status

**Active Branch:** `feat/v0.9-02-contract-freeze`

- PR-02 is contract freeze only. It updates docs, CI, and sentinel tests only.
- Workflow runtime implementation begins in PR-04.

## PR-02 Deliverables
"""


def _seed_pr02_contract_repo(
    root: Path,
    *,
    plan: str = _PR02_PLAN_CONTENT,
    hld: str = _PR02_HLD_CONTENT,
    readme: str = _PR02_README_CONTENT,
    public_contract: str = _PR02_PUBLIC_CONTRACT_CONTENT,
    pr_context: str = _PR02_PR_CONTEXT_CONTENT,
    release_gates: str = _PR02_RELEASE_GATES_CONTENT,
    implementation_status: str = _PR02_IMPLEMENTATION_STATUS_CONTENT,
) -> None:
    _write_file(root, "docs/plans/AIGC V0.9.0 IMPLEMENTATION_PLAN.md", plan)
    _write_file(root, "docs/architecture/AIGC_HIGH_LEVEL_DESIGN.md", hld)
    _write_file(root, "README.md", readme)
    _write_file(root, "docs/PUBLIC_INTEGRATION_CONTRACT.md", public_contract)
    _write_file(root, "docs/dev/pr_context.md", pr_context)
    _write_file(root, "RELEASE_GATES.md", release_gates)
    _write_file(root, "implementation_status.md", implementation_status)


def test_v090_pr02_contract_accepts_frozen_contract_docs(tmp_path, monkeypatch):
    module = _load_doc_parity_module()
    monkeypatch.setattr(module, "REPO_ROOT", tmp_path)

    _seed_pr02_contract_repo(tmp_path)

    assert module.check_v090_pr02_contract() == []


def test_v090_pr02_contract_rejects_lifecycle_state_drift(tmp_path, monkeypatch):
    module = _load_doc_parity_module()
    monkeypatch.setattr(module, "REPO_ROOT", tmp_path)

    bad_plan = _PR02_PLAN_CONTENT.replace("- `FINALIZED`\n", "")
    _seed_pr02_contract_repo(tmp_path, plan=bad_plan)

    errors = module.check_v090_pr02_contract()
    joined = "\n".join(errors)

    assert "session lifecycle states list" in joined, errors


def test_v090_pr02_contract_rejects_missing_planned_only_boundary(tmp_path, monkeypatch):
    module = _load_doc_parity_module()
    monkeypatch.setattr(module, "REPO_ROOT", tmp_path)

    bad_public_contract = _PR02_PUBLIC_CONTRACT_CONTENT.replace(
        "There is no current\nmodule-level `open_session()` convenience in the shipped package.\n",
        "",
    )
    _seed_pr02_contract_repo(tmp_path, public_contract=bad_public_contract)

    errors = module.check_v090_pr02_contract()

    assert any(
        "missing planned-only public integration boundary" in error
        for error in errors
    ), errors


def test_v090_pr02_contract_rejects_missing_a2a_protocol_version_rule(
    tmp_path, monkeypatch
):
    module = _load_doc_parity_module()
    monkeypatch.setattr(module, "REPO_ROOT", tmp_path)

    bad_hld = _PR02_HLD_CONTENT.replace(
        "- compatibility is validated from `supportedInterfaces[].protocolVersion`, not descriptive Agent Card version text\n",
        "",
    )
    _seed_pr02_contract_repo(tmp_path, hld=bad_hld)

    errors = module.check_v090_pr02_contract()

    assert any(
        "missing frozen HLD contract" in error and "supportedInterfaces[].protocolVersion" in error
        for error in errors
    ), errors


@pytest.mark.parametrize(
    ("override_key", "bad_content", "expected_label", "expected_needle"),
    [
        (
            "plan",
            _PR02_PLAN_CONTENT.replace(
                "- gRPC is out of scope for `v0.9.0` normalization and must fail with a typed protocol violation.\n",
                "",
            ),
            "missing frozen plan contract",
            "gRPC is out of scope",
        ),
        (
            "readme",
            _PR02_README_CONTENT.replace("`SessionPreCallResult`, and optional Bedrock/A2A\n", ""),
            "missing planned-only README boundary",
            "`SessionPreCallResult`",
        ),
        (
            "pr_context",
            _PR02_PR_CONTEXT_CONTENT.replace(
                "Active branch: `feat/v0.9-02-contract-freeze`\n\n",
                "",
            ),
            "missing PR-02 branch and scope",
            "feat/v0.9-02-contract-freeze",
        ),
        (
            "release_gates",
            _PR02_RELEASE_GATES_CONTENT.replace(
                "## PR-02 — Contract Freeze Gate\n\n",
                "",
            ),
            "missing PR-02 release gate",
            "## PR-02 — Contract Freeze Gate",
        ),
        (
            "implementation_status",
            _PR02_IMPLEMENTATION_STATUS_CONTENT.replace("## PR-02 Deliverables\n", ""),
            "missing PR-02 implementation status",
            "## PR-02 Deliverables",
        ),
        (
            "hld",
            _PR02_HLD_CONTENT.replace("- `GRPC`\n\n", ""),
            "missing frozen HLD contract",
            "`GRPC`",
        ),
    ],
)
def test_v090_pr02_contract_rejects_missing_required_rules(
    tmp_path, monkeypatch, override_key, bad_content, expected_label, expected_needle
):
    module = _load_doc_parity_module()
    monkeypatch.setattr(module, "REPO_ROOT", tmp_path)

    _seed_pr02_contract_repo(tmp_path, **{override_key: bad_content})

    errors = module.check_v090_pr02_contract()

    assert any(
        expected_label in error and expected_needle in error
        for error in errors
    ), errors


@pytest.mark.parametrize(
    ("override_key", "bad_content", "expected_rel", "expected_list_name"),
    [
        (
            "hld",
            _PR02_HLD_CONTENT.replace("- `FINALIZED`\n", ""),
            "docs/architecture/AIGC_HIGH_LEVEL_DESIGN.md",
            "session lifecycle states list",
        ),
        (
            "plan",
            _PR02_PLAN_CONTENT.replace("- `INCOMPLETE`\n", ""),
            "docs/plans/AIGC V0.9.0 IMPLEMENTATION_PLAN.md",
            "workflow artifact statuses list",
        ),
        (
            "hld",
            _PR02_HLD_CONTENT.replace("- `INCOMPLETE`\n", ""),
            "docs/architecture/AIGC_HIGH_LEVEL_DESIGN.md",
            "workflow artifact statuses list",
        ),
    ],
)
def test_v090_pr02_contract_rejects_other_exact_list_drifts(
    tmp_path, monkeypatch, override_key, bad_content, expected_rel, expected_list_name
):
    module = _load_doc_parity_module()
    monkeypatch.setattr(module, "REPO_ROOT", tmp_path)

    _seed_pr02_contract_repo(tmp_path, **{override_key: bad_content})

    errors = module.check_v090_pr02_contract()

    assert any(
        expected_rel in error and expected_list_name in error
        for error in errors
    ), errors


_PR03_PLAN_CONTENT = """\
# AIGC v0.9.0 Implementation Plan

### Public surface and migration posture

- The frozen golden-path CLI inventory is `aigc policy init`, `aigc workflow init`, `aigc workflow lint`, `aigc workflow doctor`, `aigc workflow trace`, and `aigc workflow export`.
- Public examples, quickstarts, starter assets, presets, recipes, and demo code must use only public APIs and must never import from `aigc._internal`.
- Hand-authored workflow DSL remains supported but is advanced mode.

### Golden-path contract freeze

Frozen CLI command inventory:

- `aigc policy init`
- `aigc workflow init`
- `aigc workflow lint`
- `aigc workflow doctor`
- `aigc workflow trace`
- `aigc workflow export`

Frozen scaffold profiles:

- `minimal`
- `standard`
- `regulated-high-assurance`

Required starter coverage:

- local multi-step review
- approval checkpoint
- source required
- tool budget

Frozen first-user diagnostic reason codes:

- `WORKFLOW_INVALID_TRANSITION`
- `WORKFLOW_APPROVAL_REQUIRED`
- `WORKFLOW_SOURCE_REQUIRED`
- `WORKFLOW_TOOL_BUDGET_EXCEEDED`
- `WORKFLOW_UNSUPPORTED_BINDING`
- `WORKFLOW_SESSION_TOKEN_INVALID`
- `WORKFLOW_STARTER_INTEGRITY_ERROR`

Frozen first-adopter docs order:

1. workflow quickstart
2. migration from invocation-only to workflow
3. troubleshooting and `workflow doctor` / `workflow lint` guide
4. starter recipes and starter index
5. workflow CLI guide
6. public API boundary and integration contract
7. supported environments
8. operations runbook
9. adapter docs as advanced follow-on material
"""

_PR03_HLD_CONTENT = """\
# AIGC High-Level Design

Availability boundary: this document describes the intended `1.0.0` public
surface. The shipped `0.3.3` package and CLI do not yet export
`GovernanceSession`, `SessionPreCallResult`, `AgentIdentity`,
`AgentCapabilityManifest`, `ValidatorHook`, `BedrockTraceAdapter`,
`A2AAdapter`, `aigc policy init`, or `aigc workflow ...` commands, and
`AIGC.open_session(...)` is not part of the installable runtime yet.

### 13.4 Frozen First-Adopter Contract

Frozen CLI command inventory:

- `aigc policy init`
- `aigc workflow init`
- `aigc workflow lint`
- `aigc workflow doctor`
- `aigc workflow trace`
- `aigc workflow export`

Frozen scaffold profiles:

- `minimal`
- `standard`
- `regulated-high-assurance`

Required starter coverage:

- local multi-step review
- approval checkpoint
- source required
- tool budget

Rules:

- hand-authored workflow DSL remains supported as advanced mode and is not required for the default path
- public quickstarts, starter packs, presets, demo code, and docs snippets must use public `aigc` imports only and must not depend on `aigc._internal`

Frozen first-user diagnostic reason codes:

- `WORKFLOW_INVALID_TRANSITION`
- `WORKFLOW_APPROVAL_REQUIRED`
- `WORKFLOW_SOURCE_REQUIRED`
- `WORKFLOW_TOOL_BUDGET_EXCEEDED`
- `WORKFLOW_UNSUPPORTED_BINDING`
- `WORKFLOW_SESSION_TOKEN_INVALID`
- `WORKFLOW_STARTER_INTEGRITY_ERROR`

Frozen first-adopter docs order:

1. workflow quickstart
2. migration from invocation-only to workflow
3. troubleshooting and `workflow doctor` / `workflow lint` guide
4. starter recipes and starter index
5. workflow CLI guide
6. public API boundary and integration contract
7. supported environments
8. operations runbook
9. adapter docs as advanced follow-on material
"""

_PR03_README_CONTENT = """\
# README

The planned golden-path CLI names — `aigc policy init`, `aigc workflow init`,
`aigc workflow lint`, `aigc workflow doctor`, `aigc workflow trace`, and
`aigc workflow export` — are also frozen in the repo docs, but none of those
workflow surfaces are part of the shipped `v0.3.3` runtime or CLI.
"""

_PR03_PUBLIC_CONTRACT_CONTENT = """\
# Public Contract

Planned-only surfaces described in that target-state document — including
`aigc policy init` and `aigc workflow ...` commands — are not part of the
installable `v0.3.3` artifact today.

All public examples, starter packs, presets, demo code, and docs snippets
must use public `aigc` imports only and must not depend on `aigc._internal`.
"""

_PR03_PR_CONTEXT_CONTENT = """\
# PR Context

Active branch: `feat/v0.9-03-golden-path-contract`

PR type:

- docs, CI, sentinel tests, and public-import hygiene only

Contract Notes

- The frozen golden-path CLI inventory is `aigc policy init`, `aigc workflow init`, `aigc workflow lint`, `aigc workflow doctor`, `aigc workflow trace`, and `aigc workflow export`, but those commands are still absent from the shipped `v0.3.3` CLI in PR-03.
- PR-03 is docs, CI, sentinel tests, and public-import hygiene only. Workflow runtime implementation still starts in PR-04.
"""

_PR03_RELEASE_GATES_CONTENT = """\
# Release Gates

## PR-03 — Golden-Path Contract Freeze Gate

- [ ] staged CLI sentinel tests prove the current shipped CLI still exposes no `workflow` or `policy init` commands while freezing the future command names in docs
- [ ] public-import boundary tests confirm maintained onboarding examples and demo code use public `aigc` imports only
"""

_PR03_IMPLEMENTATION_STATUS_CONTENT = """\
# Implementation Status

**Active Branch:** `feat/v0.9-03-golden-path-contract`

- PR-03 is golden-path contract freeze only. It updates docs, CI, sentinel tests, and public-import hygiene only.

## PR-03 Deliverables
"""


def _seed_pr03_contract_repo(
    root: Path,
    *,
    plan: str = _PR03_PLAN_CONTENT,
    hld: str = _PR03_HLD_CONTENT,
    readme: str = _PR03_README_CONTENT,
    public_contract: str = _PR03_PUBLIC_CONTRACT_CONTENT,
    pr_context: str = _PR03_PR_CONTEXT_CONTENT,
    release_gates: str = _PR03_RELEASE_GATES_CONTENT,
    implementation_status: str = _PR03_IMPLEMENTATION_STATUS_CONTENT,
) -> None:
    _write_file(root, "docs/plans/AIGC V0.9.0 IMPLEMENTATION_PLAN.md", plan)
    _write_file(root, "docs/architecture/AIGC_HIGH_LEVEL_DESIGN.md", hld)
    _write_file(root, "README.md", readme)
    _write_file(root, "docs/PUBLIC_INTEGRATION_CONTRACT.md", public_contract)
    _write_file(root, "docs/dev/pr_context.md", pr_context)
    _write_file(root, "RELEASE_GATES.md", release_gates)
    _write_file(root, "implementation_status.md", implementation_status)


def test_v090_pr03_contract_accepts_frozen_golden_path_docs(tmp_path, monkeypatch):
    module = _load_doc_parity_module()
    monkeypatch.setattr(module, "REPO_ROOT", tmp_path)

    _seed_pr03_contract_repo(tmp_path)

    assert module.check_v090_pr03_contract() == []


def test_v090_pr03_contract_rejects_cli_inventory_drift(tmp_path, monkeypatch):
    module = _load_doc_parity_module()
    monkeypatch.setattr(module, "REPO_ROOT", tmp_path)

    bad_plan = _PR03_PLAN_CONTENT.replace("- `aigc policy init`\n", "")
    _seed_pr03_contract_repo(tmp_path, plan=bad_plan)

    errors = module.check_v090_pr03_contract()

    assert any(
        "CLI command inventory list" in error
        and "docs/plans/AIGC V0.9.0 IMPLEMENTATION_PLAN.md" in error
        for error in errors
    ), errors


def test_v090_pr03_contract_rejects_docs_order_drift(tmp_path, monkeypatch):
    module = _load_doc_parity_module()
    monkeypatch.setattr(module, "REPO_ROOT", tmp_path)

    bad_hld = _PR03_HLD_CONTENT.replace(
        "5. workflow CLI guide\n6. public API boundary and integration contract\n",
        "5. public API boundary and integration contract\n6. workflow CLI guide\n",
    )
    _seed_pr03_contract_repo(tmp_path, hld=bad_hld)

    errors = module.check_v090_pr03_contract()

    assert any(
        "first-adopter docs order list" in error
        and "docs/architecture/AIGC_HIGH_LEVEL_DESIGN.md" in error
        for error in errors
    ), errors


def test_v090_pr03_contract_rejects_missing_readme_cli_boundary(tmp_path, monkeypatch):
    module = _load_doc_parity_module()
    monkeypatch.setattr(module, "REPO_ROOT", tmp_path)

    bad_readme = _PR03_README_CONTENT.replace("`aigc policy init`, ", "")
    _seed_pr03_contract_repo(tmp_path, readme=bad_readme)

    errors = module.check_v090_pr03_contract()

    assert any(
        "missing planned-only README CLI boundary" in error
        and "`aigc policy init`" in error
        for error in errors
    ), errors


def test_v090_pr03_contract_rejects_missing_release_gate(tmp_path, monkeypatch):
    module = _load_doc_parity_module()
    monkeypatch.setattr(module, "REPO_ROOT", tmp_path)

    bad_release_gates = _PR03_RELEASE_GATES_CONTENT.replace(
        "## PR-03 — Golden-Path Contract Freeze Gate\n\n",
        "",
    )
    _seed_pr03_contract_repo(tmp_path, release_gates=bad_release_gates)

    errors = module.check_v090_pr03_contract()

    assert any(
        "missing PR-03 release gate" in error
        and "## PR-03 — Golden-Path Contract Freeze Gate" in error
        for error in errors
    ), errors


# ---------------------------------------------------------------------------
# PR-04 Seeded Contract Tests
# ---------------------------------------------------------------------------

_PR04_PLAN_CONTENT = """\
# AIGC v0.9.0 Implementation Plan

PR-04 implements GovernanceSession, AIGC.open_session(...), and SessionPreCallResult.
"""

_PR04_HLD_CONTENT = """\
# AIGC High Level Design

Availability boundary: The currently shipped package remains v0.3.3.
The upcoming unreleased v0.9.0-beta line will add GovernanceSession, SessionPreCallResult,
and AIGC.open_session(...).

## Planned for v0.9.0-beta (not yet released)

| Surface | Intended role |
| ------- | ------------- |
| `GovernanceSession` | workflow governance primitive |
| `SessionPreCallResult` | workflow-scoped split handoff |
| `AIGC.open_session(...)` | instance-scoped workflow entrypoint |

## Planned for 1.0.0 (not in v0.9.0-beta)

| Planned surface | Intended role in `1.0.0` |
| --------------- | ------------------------ |
| `AgentIdentity` | participant identity contract |
"""

_PR04_README_CONTENT = """\
# AIGC README

The upcoming unreleased v0.9.0-beta line will add workflow governance built
around `AIGC.open_session(...)`, `GovernanceSession`, and `SessionPreCallResult`.
The currently shipped package remains `v0.3.3`.
"""

_PR04_PUBLIC_CONTRACT_CONTENT = """\
# AIGC Public Integration Contract

The following surfaces are planned for the upcoming unreleased v0.9.0-beta line
and are not part of the installable `v0.3.3` artifact: `AIGC.open_session(...)`,
`GovernanceSession`, `SessionPreCallResult`.

The following surfaces remain planned-only: `AgentIdentity`, `AgentCapabilityManifest`,
`aigc policy init`, and `aigc workflow ...` commands.
"""

_PR04_PR_CONTEXT_CONTENT = """\
# PR Context - v0.9.0 PR-04 Minimal Session Flow

Active branch: `feat/v0.9-04-minimal-session-flow`

PR-04 lands GovernanceSession, AIGC.open_session, and SessionPreCallResult.
"""

_PR04_RELEASE_GATES_CONTENT = """\
# Release Gates

## PR-03 — Golden-Path Contract Freeze Gate

- [ ] staged CLI sentinel tests pass
"""

_PR04_IMPLEMENTATION_STATUS_CONTENT = """\
# Implementation Status

**Active Branch:** `feat/v0.9-04-minimal-session-flow`

- PR-04 is in progress
"""

_PR04_PROJECT_MD_CONTENT = """\
# PROJECT.md

The currently shipped package remains `v0.3.3`. The upcoming unreleased v0.9.0-beta
line will add `GovernanceSession`, `SessionPreCallResult`, and `AIGC.open_session(...)`.
"""

_PR04_ENFORCEMENT_PIPELINE_CONTENT = """\
# Enforcement Pipeline

The shipped `0.3.3` runtime remains invocation-scoped. Its provenance, lineage,
and risk-history additions are groundwork for the upcoming unreleased v0.9.0-beta
line, which will ship the initial `GovernanceSession` primitive. The currently
shipped package remains `v0.3.3`.
"""


def _seed_pr04_contract_repo(
    root: Path,
    *,
    plan: str = _PR04_PLAN_CONTENT,
    hld: str = _PR04_HLD_CONTENT,
    readme: str = _PR04_README_CONTENT,
    public_contract: str = _PR04_PUBLIC_CONTRACT_CONTENT,
    pr_context: str = _PR04_PR_CONTEXT_CONTENT,
    release_gates: str = _PR04_RELEASE_GATES_CONTENT,
    implementation_status: str = _PR04_IMPLEMENTATION_STATUS_CONTENT,
    project_md: str = _PR04_PROJECT_MD_CONTENT,
    enforcement_pipeline: str = _PR04_ENFORCEMENT_PIPELINE_CONTENT,
) -> None:
    _write_file(root, "docs/plans/AIGC V0.9.0 IMPLEMENTATION_PLAN.md", plan)
    _write_file(root, "docs/architecture/AIGC_HIGH_LEVEL_DESIGN.md", hld)
    _write_file(root, "README.md", readme)
    _write_file(root, "docs/PUBLIC_INTEGRATION_CONTRACT.md", public_contract)
    _write_file(root, "docs/dev/pr_context.md", pr_context)
    _write_file(root, "RELEASE_GATES.md", release_gates)
    _write_file(root, "implementation_status.md", implementation_status)
    _write_file(root, "PROJECT.md", project_md)
    _write_file(root, "docs/architecture/ENFORCEMENT_PIPELINE.md", enforcement_pipeline)


def test_v090_pr04_contract_accepts_valid_pr04_docs(tmp_path, monkeypatch):
    """Seeded valid PR-04 docs pass check_v090_pr04_contract()."""
    module = _load_doc_parity_module()
    monkeypatch.setattr(module, "REPO_ROOT", tmp_path)

    _seed_pr04_contract_repo(tmp_path)

    errors = module.check_v090_pr04_contract()
    assert errors == [], f"Unexpected errors: {errors}"


def test_v090_pr04_contract_rejects_surface_availability_drift(tmp_path, monkeypatch):
    """README/public contract still have old planned-only language → errors returned."""
    module = _load_doc_parity_module()
    monkeypatch.setattr(module, "REPO_ROOT", tmp_path)

    bad_readme = """\
# AIGC README

The target-state 1.0.0 architecture expands this invocation-first model with
planned workflow governance. None of those workflow surfaces are part of the
shipped `v0.3.3` runtime or CLI.
"""
    _seed_pr04_contract_repo(tmp_path, readme=bad_readme)

    errors = module.check_v090_pr04_contract()

    assert any("README.md" in e for e in errors), (
        f"Expected README error for missing v0.9.0-beta wording, got: {errors}"
    )


def test_v090_pr04_contract_rejects_hld_project_enforcement_old_wording(tmp_path, monkeypatch):
    """HLD/PROJECT/ENFORCEMENT docs with old unqualified language → errors returned."""
    module = _load_doc_parity_module()
    monkeypatch.setattr(module, "REPO_ROOT", tmp_path)

    bad_enforcement = """\
# Enforcement Pipeline

The shipped 0.3.3 runtime remains invocation-scoped. Its additions are groundwork
for this future session model, not a shipped `GovernanceSession` workflow runtime.
"""
    _seed_pr04_contract_repo(tmp_path, enforcement_pipeline=bad_enforcement)

    errors = module.check_v090_pr04_contract()

    assert any("ENFORCEMENT_PIPELINE" in e for e in errors), (
        f"Expected ENFORCEMENT_PIPELINE error for old unqualified language, got: {errors}"
    )


def test_v090_pr04_contract_rejects_missing_positive_beta_wording(tmp_path, monkeypatch):
    """Old wording removed but no positive v0.9.0-beta replacement added → errors returned."""
    module = _load_doc_parity_module()
    monkeypatch.setattr(module, "REPO_ROOT", tmp_path)

    # PROJECT.md with old wording removed but no positive replacement
    bad_project_md = """\
# PROJECT.md

0.3.3 extends AIGC's invocation-governance runtime with provenance, lineage,
and risk-trend primitives that future workflow governance will build on.
"""
    _seed_pr04_contract_repo(tmp_path, project_md=bad_project_md)

    errors = module.check_v090_pr04_contract()

    assert any("PROJECT.md" in e for e in errors), (
        f"Expected PROJECT.md error for missing positive v0.9.0-beta wording, got: {errors}"
    )


def test_v090_pr04_contract_rejects_active_branch_drift(tmp_path, monkeypatch):
    """Wrong branch in pr_context/implementation_status → errors returned."""
    module = _load_doc_parity_module()
    monkeypatch.setattr(module, "REPO_ROOT", tmp_path)

    bad_pr_context = _PR04_PR_CONTEXT_CONTENT.replace(
        "Active branch: `feat/v0.9-04-minimal-session-flow`",
        "Active branch: `feat/v0.9-03-golden-path-contract`",
    )
    _seed_pr04_contract_repo(tmp_path, pr_context=bad_pr_context)

    errors = module.check_v090_pr04_contract()

    assert any(
        "PR-04 active branch" in e and "pr_context.md" in e
        for e in errors
    ), f"Expected active branch drift error, got: {errors}"


# ---------------------------------------------------------------------------
# PR-05 contract seeded tests
# ---------------------------------------------------------------------------

_PR05_PR_CONTEXT_CONTENT = """\
# PR Context

Active branch: `feat/v0.9-05-starters-and-migration`

PR-05 ships `aigc workflow init`, `aigc policy init`, starter scaffolds, and migration helpers.
"""

_PR05_IMPLEMENTATION_STATUS_CONTENT = """\
# Implementation Status

**Target Version:** `0.9.0` Beta
**Active Branch:** `feat/v0.9-05-starters-and-migration`

PR-04 is complete.
Starters and migration: in progress.
"""

_PR05_PUBLIC_CONTRACT_CONTENT = """\
# Public Integration Contract

Also planned for the upcoming unreleased v0.9.0-beta: `aigc workflow init`,
`aigc policy init`, `aigc.presets.MinimalPreset`, starter scaffolds.
"""

_PR05_README_CONTENT = """\
## Shipped in v0.9.0-beta

`aigc workflow init` and `aigc policy init` are now available.
Use `aigc workflow lint`, `aigc workflow doctor`, `aigc workflow trace`,
and `aigc workflow export` (planned for future releases).
"""

_PR05_HLD_CONTENT = """\
v0.9.0-beta adds `GovernanceSession`, `SessionPreCallResult`,
`aigc workflow init`, and `aigc policy init`.
`ValidatorHook`, `BedrockTraceAdapter`, `A2AAdapter`, `aigc workflow lint`,
`aigc workflow doctor`, `aigc workflow trace`, and `aigc workflow export`
remain planned-only and are not part of any currently released artifact.
"""


def _seed_pr05_contract_repo(
    root: Path,
    *,
    pr_context: str = _PR05_PR_CONTEXT_CONTENT,
    implementation_status: str = _PR05_IMPLEMENTATION_STATUS_CONTENT,
    public_contract: str = _PR05_PUBLIC_CONTRACT_CONTENT,
    readme: str = _PR05_README_CONTENT,
    hld: str = _PR05_HLD_CONTENT,
) -> None:
    _write_file(root, "docs/dev/pr_context.md", pr_context)
    _write_file(root, "implementation_status.md", implementation_status)
    _write_file(root, "docs/PUBLIC_INTEGRATION_CONTRACT.md", public_contract)
    _write_file(root, "README.md", readme)
    _write_file(root, "docs/architecture/AIGC_HIGH_LEVEL_DESIGN.md", hld)


def test_pr05_contract_accepts_valid_docs(tmp_path, monkeypatch):
    """Seeded valid PR-05 docs pass check_v090_pr05_contract()."""
    module = _load_doc_parity_module()
    monkeypatch.setattr(module, "REPO_ROOT", tmp_path)

    _seed_pr05_contract_repo(tmp_path)

    errors = module.check_v090_pr05_contract()
    assert errors == [], f"Unexpected errors: {errors}"


def test_pr05_contract_rejects_wrong_active_branch(tmp_path, monkeypatch):
    """pr_context.md with wrong branch name → error returned."""
    module = _load_doc_parity_module()
    monkeypatch.setattr(module, "REPO_ROOT", tmp_path)

    bad_pr_context = _PR05_PR_CONTEXT_CONTENT.replace(
        "Active branch: `feat/v0.9-05-starters-and-migration`",
        "Active branch: `feat/v0.9-04-minimal-session-flow`",
    )
    _seed_pr05_contract_repo(tmp_path, pr_context=bad_pr_context)

    errors = module.check_v090_pr05_contract()

    assert any("PR-05 active branch" in e for e in errors), (
        f"Expected active branch error, got: {errors}"
    )


def test_pr05_contract_rejects_missing_pr05_surfaces(tmp_path, monkeypatch):
    """README missing aigc policy init → error returned."""
    module = _load_doc_parity_module()
    monkeypatch.setattr(module, "REPO_ROOT", tmp_path)

    bad_readme = "# README\n\nOnly `aigc workflow init` is mentioned here.\n"
    _seed_pr05_contract_repo(tmp_path, readme=bad_readme)

    errors = module.check_v090_pr05_contract()

    assert any("aigc policy init" in e and "README.md" in e for e in errors), (
        f"Expected README error for missing aigc policy init, got: {errors}"
    )
