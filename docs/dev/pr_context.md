# PR Context — `v0.9.0` PR-03 Golden-Path Contract Freeze

Date: 2026-04-16
Status: Draft
Active branch: `feat/v0.9-03-golden-path-contract`

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

This PR freezes the default first-adopter contract for the `v0.9.0` beta
before workflow runtime implementation starts.

Theme:

- golden-path contract and public-import guardrails

PR type:

- docs, CI, sentinel tests, and public-import hygiene only

---

## Goal

Freeze the CLI command inventory, scaffold profiles, starter coverage,
public-import-only rules, first-adopter docs order, and minimum diagnostic
reason-code coverage without adding workflow runtime or workflow CLI behavior
in this PR.

---

## In Scope

- update the release packet for the PR-03 branch, scope, and exit criteria
- freeze the golden-path command inventory, starter profiles, starter coverage,
  docs order, and reason-code minimums in the canonical plan and HLD
- keep `README.md` and `docs/PUBLIC_INTEGRATION_CONTRACT.md` aligned to the
  shipped `v0.3.3` surface while naming `aigc policy init` and
  `aigc workflow ...` commands as planned-only
- extend CI truth checks for PR-03 contract drift
- add staged CLI-shape, docs-order, and public-import boundary sentinel tests
- remove `_internal` imports from maintained onboarding examples or demo code
  where the public API already covers the same behavior

---

## Out of Scope

- workflow or session runtime implementation
- public export stubs or placeholder workflow classes
- executable workflow CLI behavior or newly shipped workflow CLI commands
- executable `aigc policy init` behavior
- starter asset generation
- workflow schemas
- demo-app behavior changes
- Bedrock or A2A adapter runtime work
- package-version bumps
- `origin/develop` -> `origin/main` release promotion

---

## Binding Inputs

- `CLAUDE.md`
- `docs/plans/AIGC V0.9.0 IMPLEMENTATION_PLAN.md`
- `docs/architecture/AIGC_HIGH_LEVEL_DESIGN.md`
- `docs/decisions/ADR-0011-v090-beta-scope-sdk-boundary-and-non-goals.md`

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
- `GovernanceSession`, `SessionPreCallResult`, and `AIGC.open_session(...)`
  remain planned-only contract surfaces in PR-03. No placeholder runtime
  exports ship in this branch.
- The frozen golden-path CLI inventory is `aigc policy init`,
  `aigc workflow init`, `aigc workflow lint`, `aigc workflow doctor`,
  `aigc workflow trace`, and `aigc workflow export`, but those commands are
  still absent from the shipped `v0.3.3` CLI in PR-03.
- The frozen scaffold profiles are `minimal`, `standard`, and
  `regulated-high-assurance`.
- Hand-authored workflow DSL remains advanced mode and is not required for the
  default path.
- Public quickstarts, starter packs, presets, demo code, and docs snippets
  must use public `aigc` imports only and must not depend on `aigc._internal`.
- PR-03 is docs, CI, sentinel tests, and public-import hygiene only. Workflow
  runtime implementation still starts in PR-04.

---

## Reviewer Focus

- confirm the PR is docs, CI, sentinel tests, and import-hygiene only
- confirm the canonical plan, HLD, `README.md`, and
  `docs/PUBLIC_INTEGRATION_CONTRACT.md` agree on the planned command names,
  scaffold profiles, starter coverage, docs order, and reason-code minimums
- confirm the current public surface remains invocation-only and the shipped
  CLI still exposes no `workflow` or `policy init` commands
- confirm maintained onboarding examples and demo code use only public `aigc`
  imports
- confirm there are no runtime, schema, starter-generation, shipped CLI,
  adapter, or package-version changes

---

## Exit Gate

- `docs/dev/pr_context.md`, `RELEASE_GATES.md`, and `implementation_status.md`
  are aligned to the PR-03 branch and scope
- the canonical plan and HLD freeze the golden-path command inventory,
  scaffold profiles, starter coverage, docs order, and reason-code minimums
- `README.md` and `docs/PUBLIC_INTEGRATION_CONTRACT.md` keep the shipped
  `v0.3.3` surface honest while naming `aigc policy init` and
  `aigc workflow ...` commands as planned-only
- doc truth checks fail closed on PR-03 contract drift
- staged CLI-shape sentinel tests freeze future command names while proving the
  current shipped CLI still has no `workflow` or `policy init` commands
- public-import boundary tests prove maintained onboarding examples and demo
  code do not depend on `aigc._internal`
- no workflow runtime, schema, starter-generation, shipped CLI, demo behavior,
  or package changes land in PR-03
