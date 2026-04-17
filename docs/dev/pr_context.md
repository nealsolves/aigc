# PR Context — `v0.9.0` PR-07 Quickstart, Demo, and Beta Proof

Date: 2026-04-17
Status: In Progress
Active branch: `feat/v0.9-07-beta-proof`

---

## Branch Sequence

One branch per PR. All remote merges during active `v0.9.0` work target
`origin/develop` only.

| PR | Branch | Goal |
|----|--------|------|
| PR-01 | `feat/v0.9-01-source-of-truth` | Canonical plan, release packet, and CI truth checks |
| PR-02 | `feat/v0.9-02-contract-freeze` | Freeze session lifecycle, `SessionPreCallResult`, and artifact separation |
| PR-03 | `feat/v0.9-03-golden-path-contract` | Freeze CLI shape, starter profiles, public-import rules, and docs order |
| PR-04 | `feat/v0.9-04-minimal-session-flow` | Land the smallest real governed local workflow path |
| PR-05 | `feat/v0.9-05-starters-and-migration` | Ship starters, thin presets, and migration helpers |
| PR-06 | `feat/v0.9-06-doctor-and-lint` | Ship `workflow doctor`, `workflow lint`, and stable reason codes |
| PR-07 | `feat/v0.9-07-beta-proof` | Mandatory stop-ship checkpoint for quickstart, demo, and failure-and-fix proof |
| PR-08 | `feat/v0.9-08-engine-hardening` | Harden workflow sequencing, approvals, budgets, and validator hooks |
| PR-09 | `feat/v0.9-09-exports-and-ops` | Ship trace, export, and operator polish |
| PR-10a | `feat/v0.9-10-bedrock-adapter` | Add optional Bedrock adapter with alias-backed identity binding |
| PR-10b | `feat/v0.9-10-a2a-adapter` | Add optional A2A adapter with strict wire-contract validation |
| PR-11 | `feat/v0.9-11-beta-freeze` -> `release/v0.9.0` | Freeze the beta and start the final release sequence only after all gates pass |

---

## PR Summary

This PR is the mandatory stop-ship checkpoint. It proves that the default
`v0.9.0` adopter journey is real from a clean environment, not just
architecturally planned.

Theme:

- quickstart, demo, and failure-and-fix proof

PR type:

- new docs, new proof tests, new demo route, new demo component, new harness script

---

## Goal

Prove that a first adopter can, starting from a clean environment:

1. install the base package
2. run `aigc workflow init`
3. reach a first PASS on a local host-owned workflow
4. hit one intentional, understandable failure
5. diagnose that failure with `aigc workflow doctor` or `aigc workflow lint`
6. apply the documented fix and return to PASS

All of that must happen through public docs, public APIs, starter assets,
examples, and the maintained demo only.

---

## In Scope

- `docs/dev/pr_context.md` and `implementation_status.md` realignment to PR-07
- `RELEASE_GATES.md` PR-07 gate section
- `docs/reference/WORKFLOW_QUICKSTART.md`
- `docs/migration.md` refinement (verification and common-mistakes sections)
- `docs/reference/TROUBLESHOOTING.md`
- `docs/reference/STARTER_INDEX.md`
- `docs/reference/STARTER_RECIPES.md`
- `docs/reference/WORKFLOW_CLI.md`
- `docs/PUBLIC_INTEGRATION_CONTRACT.md` — v0.9.0 section updated from planned-only to beta
- `docs/reference/SUPPORTED_ENVIRONMENTS.md`
- `docs/reference/OPERATIONS_RUNBOOK.md`
- `README.md` — workflow beta section and link to first-adopter docs
- `PROJECT.md` — repo map update
- `tests/test_pr07_beta_proof.py` — mandatory stop-ship proof tests
- `scripts/validate_v090_beta_proof.py` — clean-environment proof harness
- `demo-app-api/workflow_routes.py` — v0.9.0 workflow governance demo routes
- `demo-app-api/tests/test_workflow_routes.py`
- `demo-app-react/src/WorkflowLab/WorkflowLab.tsx`
- `demo-app-react/src/WorkflowLab/WorkflowLab.test.tsx`
- `scripts/check_doc_parity.py` — checks M and N
- `doc_parity_manifest.yaml` — new reference docs added

---

## Out of Scope

- `aigc workflow trace`, `aigc workflow export` — reserved for PR-09
- `ValidatorHook`, `BedrockTraceAdapter`, `A2AAdapter` — reserved for PR-08, PR-10a/b
- workflow runtime engine hardening — reserved for PR-08
- package-version bumps
- `origin/develop` -> `origin/main` release promotion

---

## Binding Inputs

- `CLAUDE.md`
- `docs/plans/AIGC V0.9.0 IMPLEMENTATION_PLAN.md`
- `docs/plans/v0.9.0_PR-07_BETA_PROOF_PLAN.md`
- `docs/architecture/AIGC_HIGH_LEVEL_DESIGN.md`

---

## Contract Notes

- Do NOT open or merge a PR from `origin/develop` -> `origin/main` until
  `v0.9.0` is formally declared a GO.
- PR-07 is the mandatory stop-ship checkpoint.
- The default adopter path must succeed without Bedrock or A2A.
- All generated content and examples must use public `aigc` imports only.
- `aigc workflow trace` and `aigc workflow export` remain unshipped until PR-09.

---

## Exit Gate

- `docs/dev/pr_context.md` and `implementation_status.md` are aligned to PR-07
- `docs/reference/WORKFLOW_QUICKSTART.md` exists and covers minimal starter to COMPLETED
- `docs/reference/TROUBLESHOOTING.md` exists and covers doctor/lint guidance
- `docs/reference/STARTER_INDEX.md` and `docs/reference/STARTER_RECIPES.md` exist
- `docs/reference/WORKFLOW_CLI.md` exists and covers policy init, workflow init, workflow lint, workflow doctor only (not trace/export)
- `docs/PUBLIC_INTEGRATION_CONTRACT.md` v0.9.0 section updated from planned-only to beta
- `docs/reference/SUPPORTED_ENVIRONMENTS.md` exists
- `docs/reference/OPERATIONS_RUNBOOK.md` exists
- `tests/test_pr07_beta_proof.py` passes: minimal → COMPLETED, standard → COMPLETED, regulated failure path
- `scripts/validate_v090_beta_proof.py` runs end-to-end in a clean venv within 15 minutes
- `demo-app-api/workflow_routes.py` router imported in `demo-app-api/main.py`
- `demo-app-react/src/WorkflowLab/WorkflowLab.tsx` exists with 4 tabs
- no `aigc._internal` imports in any doc, example, demo, or starter
- Full test suite passes: `python -m pytest -v`, `flake8 aigc`, `python scripts/check_doc_parity.py`, `pytest demo-app-api/tests -q`, `npm --prefix demo-app-react test`, `npm --prefix demo-app-react run build`
