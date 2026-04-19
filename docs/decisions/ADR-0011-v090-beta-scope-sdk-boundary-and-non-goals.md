# ADR-0011: `v0.9.0` Beta Scope, SDK Boundary, and Non-Goals

Date: 2026-04-15
Status: Accepted
Owners: Neal

---

## Context

AIGC `v0.3.3` is the shipped runtime baseline. It governs individual
invocations, supports split enforcement, and includes workflow-aware provenance
groundwork.

`v0.9.0` is the next release target. The release is not a general rewrite and
not a hosted platform pivot. The primary product story is a Python application
team that already owns a real host application and wants to add workflow
governance without surrendering orchestration or provider ownership.

The implementation plan locks the following pressures in tension:

- workflow governance must become real enough for an app team to drop into a
  local workflow quickly
- adoption improvements must not weaken fail-closed governance behavior
- optional Bedrock and A2A integrations must not redefine the default path
- invocation-only users must remain supported during the beta transition

PR-01 needs an ADR that names the beta scope explicitly so later PRs do not
quietly renegotiate what AIGC is.

## Decision

Adopt `v0.9.0` as a feature-complete beta for workflow governance with a strict
SDK boundary.

### AIGC owns

- policy loading and composition
- ordered governance checks
- workflow constraints and step-bound authorization
- evidence correlation and audit artifacts
- optional adapter normalization at validated boundaries
- fail-closed diagnostics for the supported governance surface

### The host owns

- orchestration and control flow
- model and tool execution
- transport, retries, and credentials
- business state and persistence decisions outside AIGC artifacts
- provider SDK usage and remote session management
- external protocol clients, sockets, queues, and auth flows

### `v0.9.0` beta scope

- `AIGC.open_session(...)` as the workflow entrypoint
- `GovernanceSession` and `SessionPreCallResult`
- workflow evidence separate from invocation evidence
- starter scaffolds, thin presets, migration helpers, and workflow CLI
- approval checkpoints, validator hooks, and deterministic workflow diagnostics
- optional Bedrock and A2A adapters that normalize host-supplied evidence only

### Non-goals for `v0.9.0`

- a hosted orchestrator or remote workflow runtime
- a transport layer, queue runner, or credential broker
- a model-serving platform
- hidden orchestration behind presets or starter scaffolds
- mandatory Bedrock or A2A dependencies for first success
- replacement of invocation artifacts with workflow artifacts
- persistence of raw external payloads by default
- a `1.x` stability promise before `1.0.0`

## Consequences

- The golden path is local workflow adoption first.
- Public examples, quickstarts, starters, presets, and recipes must use only
  public imports.
- Invocation-only integrations remain supported and can adopt workflow
  governance additively rather than by rewrite.
- Optional adapters remain advanced tracks. They can expand integration
  coverage, but they cannot become the default dependency chain.
- Security gates remain fail-closed when identity, transition, protocol,
  approval, budget, or evidence requirements are not met.

## Validation

- [x] `IMPLEMENTATION_PLAN.md` is the canonical `v0.9.0` plan
- [x] `docs/dev/pr_context.md` reflects the `v0.9.0` release train
- [x] `RELEASE_GATES.md` defines beta and `1.0.0` promotion gates
- [x] PR-01 source-of-truth checks enforce one active `v0.9.0` plan
- [ ] PR-02 freezes the workflow contract in tests and docs
- [ ] PR-07 proves the default adopter path from clean environment
- [ ] PR-11 freezes the public beta surface

## References

- `IMPLEMENTATION_PLAN.md`
- `IMPLEMENTATION_STATUS.md`
- `RELEASE_GATES.md`
- `docs/dev/pr_context.md`
- `docs/architecture/ARCHITECTURAL_INVARIANTS.md`
- `docs/decisions/ADR-0009-split-enforcement-model.md`
