# Implementation Status

**Target Version:** `0.9.0` Beta
**Baseline Version:** `0.3.3`
**Active Branch:** `develop`
**Last Updated:** 2026-04-18

---

## Overall Progress

- PR-01 through PR-08 are complete.
- PR-09, PR-10a, PR-10b, and PR-11 have not started.

| Track | Status | Notes |
|-------|--------|-------|
| Source of truth | complete | Canonical docs, release packet, and parity checks are aligned |
| Contract freeze | complete | Lifecycle, artifact separation, and instance-scoped workflow entry are frozen |
| Golden-path contract | complete | Beta CLI inventory, starter profiles, docs order, and public-import rules are frozen |
| Minimal session flow | complete | `GovernanceSession`, `AIGC.open_session(...)`, and `SessionPreCallResult` ship on `develop` |
| Starters and migration | complete | `aigc workflow init`, `aigc policy init`, starter scaffolds, presets, and migration docs ship |
| Diagnostics | complete | `aigc workflow lint` and `aigc workflow doctor` ship with stable first-user codes |
| Beta proof | complete | Clean-env proof, real failure/diagnosis/fix/rerun flow, and demo parity are in place |
| Engine hardening | complete | Budgets, transitions, protocol constraints, approvals, handoffs, and internal validator hooks are hardened |
| Exports and ops | not started | Begins in PR-09 |
| Optional adapters | not started | Begin in PR-10a and PR-10b |
| Beta freeze | not started | Begins in PR-11 |

---

## Release Rules

- Do NOT open or merge a PR from `origin/develop` -> `origin/main` until
  `v0.9.0` is formally declared a GO.
- PR-07 is the mandatory stop-ship checkpoint. If the golden path fails there,
  no further public-surface work proceeds until the default path is repaired.
- The default adopter path must succeed without Bedrock or A2A.

---

## PR Status

| PR | Branch | Status | Notes |
|----|--------|--------|-------|
| PR-01 | `feat/v0.9-01-source-of-truth` | complete | Canonical plan, release packet, supersession banners, and CI truth checks |
| PR-02 | `feat/v0.9-02-contract-freeze` | complete | Freeze lifecycle, `SessionPreCallResult`, `AIGC.open_session(...)`, and evidence separation |
| PR-03 | `feat/v0.9-03-golden-path-contract` | complete | Freeze beta CLI shape, starter profiles, docs order, and public-import rules |
| PR-04 | `feat/v0.9-04-minimal-session-flow` | complete | Smallest real governed local workflow path |
| PR-05 | `feat/v0.9-05-starters-and-migration` | complete | Starters, thin presets, and migration helpers |
| PR-06 | `feat/v0.9-06-doctor-and-lint` | complete | Diagnostics: lint, doctor, stable reason codes |
| PR-07 | `feat/v0.9-07-beta-proof` | complete | Mandatory stop-ship proof for quickstart, diagnosis, fix, rerun, and demo parity |
| PR-08 | `feat/v0.9-08-engine-hardening` | complete | Sequencing, approvals, budgets, transitions, handoffs, protocol rules, and internal validator hooks |
| PR-09 | `feat/v0.9-09-exports-and-ops` | not started | Trace, export, and operator polish |
| PR-10a | `feat/v0.9-10-bedrock-adapter` | not started | Optional Bedrock adapter with alias-backed identity rules |
| PR-10b | `feat/v0.9-10-a2a-adapter` | not started | Optional A2A adapter with strict wire-contract rules |
| PR-11 | `feat/v0.9-11-beta-freeze` -> `release/v0.9.0` | not started | Public API freeze, beta gate verification, and release cut |

---

## PR-05 Deliverables

- [x] `aigc workflow init`
- [x] `aigc policy init`
- [x] `minimal`, `standard`, and `regulated-high-assurance` starter scaffolds
- [x] thin presets exposed through `aigc.presets`
- [x] invocation-only migration guidance and smoke coverage
- [x] public-import-only starter and example coverage

## PR-07 Deliverables

- [x] `docs/reference/WORKFLOW_QUICKSTART.md` covers minimal starter to `COMPLETED`
- [x] `docs/reference/TROUBLESHOOTING.md` covers doctor/lint usage and the regulated failure-and-fix flow
- [x] `docs/reference/WORKFLOW_CLI.md` documents policy init, workflow init, workflow lint, and workflow doctor only
- [x] `docs/reference/STARTER_INDEX.md`, `docs/reference/STARTER_RECIPES.md`, `docs/reference/SUPPORTED_ENVIRONMENTS.md`, and `docs/reference/OPERATIONS_RUNBOOK.md` ship as first-adopter docs
- [x] `tests/test_pr07_beta_proof.py` validates minimal PASS, standard PASS, broken regulated starter, doctor diagnosis, fix-in-place, and rerun
- [x] `scripts/validate_v090_beta_proof.py` validates the same clean-env journey in a fresh venv
- [x] demo workflow routes and the React lab follow the same failure-and-fix story
- [x] no maintained public docs, demos, or starters import `aigc._internal`

## PR-08 Deliverables

- [x] ordered sequence, transition, role, participant, handoff, and protocol enforcement
- [x] `max_steps` and `max_total_tool_calls` enforcement
- [x] auditable approval checkpoints
- [x] restrictive workflow composition checks
- [x] internal validator-hook wiring through ordinary session creation
- [x] public re-exports for workflow-step exceptions raised by public methods
- [x] deterministic session token cleanup on failed Phase B attempts
