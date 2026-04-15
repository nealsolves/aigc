# PR Context — `v0.9.0` PR-01 Source of Truth

Date: 2026-04-15
Status: Draft
Active branch: `feat/v0.9-01-source-of-truth`

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

This PR establishes the source of truth for the `v0.9.0` beta before runtime
implementation starts.

Theme:

- source-of-truth cleanup and canonical reset

PR type:

- docs-only groundwork plus CI truth enforcement

---

## Goal

Establish one active implementation plan, one active release context, one
active release-gate definition, and one active implementation tracker for the
`v0.9.0` train without changing runtime behavior in this PR.

---

## In Scope

- add the canonical `CLAUDE.md` collaborator contract to this branch
- add the canonical `docs/plans/AIGC V0.9.0 IMPLEMENTATION_PLAN.md`
- create `docs/plans/v0.9.0_DOCS_ONLY_PR_PLAN.md`
- replace stale `v0.3.3` planning context in `docs/dev/pr_context.md`
- replace stale release gates in `RELEASE_GATES.md`
- replace stale implementation tracking in `implementation_status.md`
- mark stale `v0.9.0` plan variants as superseded or historical input only
- add CI truth checks for plan uniqueness and release-doc agreement

---

## Out of Scope

- PR-02 through PR-11 runtime implementation
- workflow schemas
- public API additions or removals
- CLI behavior changes
- demo-app behavior changes
- Bedrock or A2A adapter runtime work
- package-version bumps
- `origin/develop` -> `origin/main` release promotion

---

## Binding Inputs

- `CLAUDE.md`
- `docs/plans/AIGC V0.9.0 IMPLEMENTATION_PLAN.md`
- `docs/plans/v0.9.0_DOCS_ONLY_PR_PLAN.md`

---

## Contract Notes

- Do NOT open or merge a PR from `origin/develop` -> `origin/main` until
  `v0.9.0` is formally declared a GO.
- PR-07 is the mandatory stop-ship checkpoint. If the golden path fails there,
  no further public-surface work proceeds until the default path is repaired.
- The default adopter path must succeed without Bedrock or A2A.
- `CLAUDE.md` is binding for the seven demo rules, workflow lifecycle
  semantics, adapter fail-closed constraints, the PR table, and the
  `origin/main` freeze.
- PR-01 is source-of-truth and CI enforcement only. Runtime implementation
  starts after this branch lands.

---

## Reviewer Focus

- confirm the PR is docs-only plus CI truth enforcement
- confirm there is exactly one active `v0.9.0` implementation plan
- confirm stale plan variants are visibly superseded
- confirm branch names and PR numbering match `CLAUDE.md`
- confirm `PR-07` stop-ship and the `origin/main` freeze are repeated exactly
- confirm there are no version bumps or runtime changes in this PR

---

## Exit Gate

- `docs/plans/v0.9.0_DOCS_ONLY_PR_PLAN.md` is present
- `RELEASE_GATES.md` is aligned to the `v0.9.0` PR train
- `implementation_status.md` is aligned to the `v0.9.0` PR train
- stale `v0.9.0` plan variants are marked as superseded or historical input
- doc truth checks fail closed on future plan drift
- no code yet
