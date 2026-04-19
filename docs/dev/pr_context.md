# PR Context — `v0.9.0` Between PR-08 And PR-09

Date: 2026-04-18
Status: `develop` contains PR-01 through PR-08; PR-09 has not started
Active branch: `develop`

---

## Branch Sequence

Do NOT open or merge a PR from `origin/develop` -> `origin/main` until
`v0.9.0` is formally declared a GO.

PR-07 is the mandatory stop-ship checkpoint. If the golden path fails there,
no further public-surface work proceeds until the default path is repaired.

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

## Current State

- PR-01 through PR-08 are complete on local `develop`.
- The source-only `v0.9.0` beta path currently ships:
  - `AIGC.open_session(...)`
  - `GovernanceSession`
  - `SessionPreCallResult`
  - `aigc workflow init`
  - `aigc policy init`
  - `aigc workflow lint`
  - `aigc workflow doctor`
- The default adopter path succeeds without Bedrock or A2A.
- `ValidatorHook` is implemented as an internal engine capability in PR-08. It
  is not a public beta surface.

## Beta Contract Notes

- Workflow adoption is always instance-scoped through `AIGC.open_session(...)`.
- Invocation artifacts remain separate from workflow/session artifacts.
- Public examples, docs, starters, presets, and demo code must use public
  `aigc` imports only and must not import from `aigc._internal`.
- `aigc workflow trace` and `aigc workflow export` remain unshipped until PR-09.
- `AgentIdentity`, `AgentCapabilityManifest`, `BedrockTraceAdapter`, and
  `A2AAdapter` remain later-track surfaces.

## Verified PR-07 / PR-08 Outcomes

- The regulated failure-and-fix proof now breaks the generated
  `workflow_example.py`, runs that same broken starter, diagnoses that same
  directory with `aigc workflow doctor`, restores the same file, and reruns the
  same starter to `COMPLETED`.
- Demo failure diagnosis now uses a real generated starter directory instead of
  fabricating a diagnostic-only directory.
- Workflow-step exceptions raised from public session methods are re-exported
  from `aigc` and `aigc.errors`.
- Session post-call attempts now clean up session tokens deterministically on
  failure instead of leaving dead pending tokens behind.

## Next PR

PR-09 remains the next branch:

- `aigc workflow trace`
- `aigc workflow export`
- operator-facing visibility and portability polish
