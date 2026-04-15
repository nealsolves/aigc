from __future__ import annotations

import importlib.util
import textwrap
from pathlib import Path


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
