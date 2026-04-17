# PR Context — `v0.9.0` PR-05 Starters and Migration

Date: 2026-04-16
Status: In Progress
Active branch: `feat/v0.9-05-starters-and-migration`

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
| PR-11 | `feat/v0.9-11-beta-freeze` -> `release/v0.9.0` | Freeze the beta and open the final release sequence only after all gates pass |

---

## PR Summary

This PR ships the first-adopter entry point: workflow and policy scaffold
commands, starter content for all three profiles, thin preset builders, and
migration helpers from invocation-only governance.

Theme:

- starters, presets, and invocation-only → workflow migration

PR type:

- new CLI commands, new Python modules, new tests, new docs

---

## Goal

Make the first-adopter journey copy-pasteable before engine work dominates
the release. Ship `aigc workflow init`, `aigc policy init`, starter scaffolds
for all three profiles, thin preset builders, and migration examples and guide.

---

## In Scope

- `WorkflowStarterIntegrityError` error class
- `aigc._internal.presets` with `MinimalPreset`, `StandardPreset`, `RegulatedHighAssurancePreset`
- `aigc.presets` public re-export module
- `aigc._internal.starter_templates` with `render_minimal_starter`, `render_standard_starter`, `render_regulated_starter`
- `aigc policy init` CLI command
- `aigc workflow init` CLI command
- `examples/migration/invocation_only.py` and `workflow_adoption.py`
- `docs/migration.md`
- doc-parity updates: active branch, implementation status, contract, README, HLD

---

## Out of Scope

- `aigc workflow lint`, `aigc workflow doctor`, `aigc workflow trace`, `aigc workflow export` (PR-06+)
- `ValidatorHook`, `BedrockTraceAdapter`, `A2AAdapter` (PR-08+, PR-10a/b)
- workflow runtime engine hardening (PR-08)
- demo-app behavior changes
- package-version bumps
- `origin/develop` -> `origin/main` release promotion

---

## Binding Inputs

- `CLAUDE.md`
- `docs/plans/AIGC V0.9.0 IMPLEMENTATION_PLAN.md`
- `docs/architecture/AIGC_HIGH_LEVEL_DESIGN.md`

---

## Contract Notes

- Do NOT open or merge a PR from `origin/develop` -> `origin/main` until
  `v0.9.0` is formally declared a GO.
- PR-07 is the mandatory stop-ship checkpoint.
- The default adopter path must succeed without Bedrock or A2A.
- All generated content and examples must use public `aigc` imports only.
- `aigc workflow lint`, `aigc workflow doctor`, `aigc workflow trace`, and
  `aigc workflow export` remain unshipped until PR-06 and PR-09.

---

## Exit Gate

- `docs/dev/pr_context.md`, and `implementation_status.md` are aligned to PR-05
- `WorkflowStarterIntegrityError` importable from `aigc`
- `aigc.presets.MinimalPreset`, `StandardPreset`, `RegulatedHighAssurancePreset` importable
- `aigc workflow init --profile minimal` writes three files and runs successfully
- `aigc policy init --profile regulated-high-assurance` writes valid policy YAML
- Migration examples run end-to-end with a local policy file
- `docs/migration.md` exists and covers `open_session` and `enforce_step_pre_call`
- Full test suite passes: `python -m pytest -v`
- `flake8 aigc` passes
- `python scripts/check_doc_parity.py` passes
