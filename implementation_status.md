# Implementation Status

**Target Version:** `0.9.0` Beta
**Baseline Version:** `0.3.3`
**Active Branch:** `feat/v0.9-07-beta-proof`
**Last Updated:** 2026-04-17

---

## Overall Progress

Current state:

- PR-01 through PR-06 are complete
- PR-07 is in progress

| Track | Status | Notes |
|-------|--------|-------|
| Source of truth | complete | Canonical docs and CI truth checks are the baseline for later PRs |
| Contract freeze | complete | PR-02 froze lifecycle, planned-only workflow surfaces, and protocol-boundary rules |
| Golden-path contract | complete | PR-03 froze command names, starter profiles, docs order, and public-import rules |
| Minimal session flow | complete | PR-04: GovernanceSession, AIGC.open_session, SessionPreCallResult |
| Starters and migration | complete | PR-05: aigc workflow init, aigc policy init, starter scaffolds, migration guide |
| Diagnostics | complete | PR-06: aigc workflow lint, aigc workflow doctor, frozen reason codes |
| Beta proof | in progress | PR-07: quickstart docs, demo slice, failure-and-fix proof, clean-env harness |
| Engine hardening | complete | PR-08 complete |
| Exports and ops | not started | Starts in PR-09 |
| Optional adapters | not started | Starts in PR-10a and PR-10b |
| Beta freeze | not started | Starts in PR-11 |

---

## Active Source of Truth

- `CLAUDE.md` is the collaborator contract for demo rules, workflow semantics,
  adapter fail-closed boundaries, PR structure, `PR-07` stop-ship, and the
  `origin/main` freeze.
- `docs/plans/AIGC V0.9.0 IMPLEMENTATION_PLAN.md` is the one active
  implementation plan.
- `docs/architecture/AIGC_HIGH_LEVEL_DESIGN.md` is the target-state design
  contract that PR-02 is locking against the implementation plan.
- `docs/dev/pr_context.md`, `RELEASE_GATES.md`, and this file are the release
  truth packet that must stay aligned with `CLAUDE.md`.

---

## Release Rules

- Do NOT open or merge a PR from `origin/develop` -> `origin/main` until
  `v0.9.0` is formally declared a GO.
- PR-07 is the mandatory stop-ship checkpoint. If the golden path fails there,
  no further public-surface work proceeds until the default path is repaired.
- The default adopter path must succeed without Bedrock or A2A.
- PR-03 is golden-path contract freeze only. It updates docs, CI, sentinel
  tests, and public-import hygiene only.
- No workflow runtime, starter generation, shipped workflow CLI commands,
  policy-init behavior, schema changes, demo behavior changes, or adapter
  implementations land in PR-03.
- Workflow runtime implementation begins in PR-04.

---

## PR Status

| PR | Branch | Status | Notes |
|----|--------|--------|-------|
| PR-01 | `feat/v0.9-01-source-of-truth` | complete | Canonical plan, release packet, supersession banners, and CI truth checks |
| PR-02 | `feat/v0.9-02-contract-freeze` | complete | Freeze lifecycle, `SessionPreCallResult`, `AIGC.open_session(...)`, and evidence separation |
| PR-03 | `feat/v0.9-03-golden-path-contract` | complete | Freeze CLI shape, starter profiles, public-import rules, docs order, and first-user reason codes |
| PR-04 | `feat/v0.9-04-minimal-session-flow` | complete | Smallest real governed local workflow path |
| PR-05 | `feat/v0.9-05-starters-and-migration` | complete | Starters, thin presets, and migration helpers |
| PR-06 | `feat/v0.9-06-doctor-and-lint` | complete | Diagnostics: workflow lint, doctor, frozen reason codes |
| PR-07 | `feat/v0.9-07-beta-proof` | in progress | Mandatory stop-ship checkpoint for quickstart, demo, and failure-and-fix proof |
| PR-08 | `feat/v0.9-08-engine-hardening` | complete | Sequencing, approvals, budgets, and validator-hook hardening |
| PR-09 | `feat/v0.9-09-exports-and-ops` | not started | Trace, export, and operator polish |
| PR-10a | `feat/v0.9-10-bedrock-adapter` | not started | Optional Bedrock adapter with alias-backed identity rules |
| PR-10b | `feat/v0.9-10-a2a-adapter` | not started | Optional A2A adapter with strict wire-contract rules |
| PR-11 | `feat/v0.9-11-beta-freeze` -> `release/v0.9.0` | not started | Public API freeze, beta gate verification, and release cut |

---

## PR-03 Deliverables

- [x] create `feat/v0.9-03-golden-path-contract` from current `develop`
- [x] rewrite `docs/dev/pr_context.md` for the PR-03 branch, scope, and exit
      gates
- [x] update `RELEASE_GATES.md` for the PR-03 golden-path contract gate
- [x] update `implementation_status.md` for PR-03 progress and deliverables
- [x] freeze the golden-path CLI inventory in the canonical plan and HLD
- [x] freeze scaffold profiles and required starter coverage in the canonical
      plan and HLD
- [x] freeze first-adopter docs order and minimum reason-code coverage in the
      canonical plan and HLD
- [x] align `README.md` and `docs/PUBLIC_INTEGRATION_CONTRACT.md` to the
      shipped `v0.3.3` surface while naming `aigc policy init` and
      `aigc workflow ...` as planned-only
- [x] extend doc parity checks for PR-03 contract drift
- [x] add staged CLI-shape and public-import boundary sentinel tests
- [x] remove maintained demo `_internal` imports where public or local
      equivalents already exist

---

## PR-07 Deliverables

- [ ] `docs/dev/pr_context.md` and `implementation_status.md` are aligned to PR-07
- [ ] `docs/reference/WORKFLOW_QUICKSTART.md` exists and covers minimal starter to COMPLETED
- [ ] `docs/reference/TROUBLESHOOTING.md` exists and covers doctor/lint guidance
- [ ] `docs/reference/STARTER_INDEX.md` and `docs/reference/STARTER_RECIPES.md` exist
- [ ] `docs/reference/WORKFLOW_CLI.md` exists and covers policy init, workflow init, workflow lint, workflow doctor only (not trace/export)
- [ ] `docs/PUBLIC_INTEGRATION_CONTRACT.md` v0.9.0 section updated from planned-only to beta
- [ ] `docs/reference/SUPPORTED_ENVIRONMENTS.md` exists
- [ ] `docs/reference/OPERATIONS_RUNBOOK.md` exists
- [ ] `tests/test_pr07_beta_proof.py` passes: minimal → COMPLETED, standard → COMPLETED, regulated failure path
- [ ] `scripts/validate_v090_beta_proof.py` runs end-to-end in a clean venv within 15 minutes
- [ ] `demo-app-api/workflow_routes.py` router imported in `demo-app-api/main.py`
- [ ] `demo-app-react/src/WorkflowLab/WorkflowLab.tsx` exists with 4 tabs
- [ ] no `aigc._internal` imports in any doc, example, demo, or starter
- [ ] Full test suite passes: `python -m pytest -v`, `flake8 aigc`, `python scripts/check_doc_parity.py`, `pytest demo-app-api/tests -q`, `npm --prefix demo-app-react test`, `npm --prefix demo-app-react run build`
