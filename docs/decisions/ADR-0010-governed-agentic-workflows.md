# ADR-0010: Governed Agentic Workflows

Date: 2026-04-08
Status: Proposed
Owners: Neal

---

## Context

AIGC `v0.3.2` governs individual invocations.

The supplied post-`v0.3.2` planning materials define `v0.3.3` as the first
release that makes the SDK workflow-aware:

- provenance metadata
- `AuditLineage`
- `ProvenanceGate`
- `RiskHistory`
- default split enforcement via `pre_call_enforcement=True`

The release intent is to move from:

- "govern each LLM call"

to:

- "govern chains of calls (agentic workflows)"

The planning note also states that this is an additive evolution of AIGC, not a
rewrite and not a fork.

### Constraints

- carry forward the `v0.3.2` architecture, invariants, and split enforcement
  model
- limit `v0.3.3` scope to the workflow-aware capabilities named above
- keep audit schema evolution additive only
- preserve exactly one audit artifact per invocation attempt
- retain an explicit legacy opt-out path for
  `pre_call_enforcement=False`
- avoid adding behavior that is not grounded in the supplied planning docs

---

## Decision

Adopt `v0.3.3` as an additive workflow-aware SDK release centered on governed
agentic workflows.

The release contract is:

- provenance becomes part of the audit artifact contract
- lineage can be reconstructed across multiple invocations
- source presence can be enforced through a built-in provenance gate
- trust can be tracked over time via risk history
- pre-call governance becomes the default execution model

### Implementation

1. Add audit schema `v1.4` provenance metadata as an optional artifact field.
2. Add `AuditLineage` for checksum-based lineage reconstruction across JSONL
   audit trails.
3. Add `ProvenanceGate` as the first built-in workflow-aware gate.
4. Add `RiskHistory` as an advisory utility for graduated trust over time.
5. Flip `@governed` to `pre_call_enforcement=True` by default while retaining
   explicit `pre_call_enforcement=False` as the legacy opt-out path.
6. Keep CLI lineage, demo labs, and the final release PR as downstream work in
   the release sequence rather than expanding this ADR beyond the named SDK
   shift.

---

## Options Considered

### Option A: additive workflow-aware release in `v0.3.3` (chosen)

Pros:

- preserves the current architecture and release continuity
- lands workflow awareness without a rewrite
- keeps compatibility constraints explicit from the start

Cons:

- requires careful schema, docs, and migration discipline
- adds cross-PR dependency management around provenance-first sequencing

### Option B: defer workflow-aware SDK work to a later release

Pros:

- lowers short-term implementation pressure
- avoids a near-term default-behavior migration

Cons:

- leaves AIGC centered on invocation-only governance
- delays lineage and provenance enforcement despite being the named `v0.3.3`
  theme

### Option C: restart in a rewritten architecture

Pros:

- allows a completely fresh design surface

Cons:

- contradicts the supplied planning constraint that the new product is AIGC
  evolved, not a rewrite and not a fork
- breaks release continuity from `v0.3.2`

---

## Consequences

- What becomes easier:
  - trace outputs back to source inputs
  - reconstruct multi-invocation lineage from audit trails
  - enforce "no output without sources"
  - reason about trust as a trajectory rather than as a single score
  - make pre-call governance the expected integration path

- What becomes harder:
  - maintain doc and schema parity across a broader release surface
  - preserve backward compatibility while changing the decorator default

- Risks introduced:
  - **Risk:** provenance schema drift across runtime, schema, and docs.
    **Mitigation:** keep `v1.4` additive and gate release on doc parity and
    contract tests.
  - **Risk:** legacy hosts may rely on implicit unified decorator behavior.
    **Mitigation:** retain explicit `pre_call_enforcement=False` and document
    migration expectations.
  - **Risk:** lineage features could grow beyond the supplied release scope.
    **Mitigation:** keep this ADR limited to the named `v0.3.3` capabilities and
    sequence follow-on work through explicit PR gates.

---

## Contract Impact

- Enforcement pipeline impact: split enforcement becomes the default execution
  model; gate ordering remains unchanged.
- Policy DSL impact: none specified in the supplied planning docs for PR-01.
- Schema impact: audit artifact schema moves from `v1.3` to additive `v1.4`
  with optional provenance metadata.
- Audit artifact impact: artifacts can carry provenance needed for lineage
  reconstruction and provenance-aware enforcement.
- Golden replays impact: new lineage and default-flip fixtures are expected in
  implementation PRs.
- Structural impact: new public utilities are planned for lineage and risk
  history.
- Backward compatibility: no new required artifact fields; explicit legacy
  decorator opt-out is retained.

---

## Validation

- [ ] ADR accepted
- [ ] schema `v1.4` remains additive only
- [ ] lineage reconstruction traces artifacts by checksum
- [ ] `ProvenanceGate` enforces source presence at the chosen insertion point
- [ ] `RiskHistory` supports trust-over-time trajectories
- [ ] `@governed` default flip preserves one artifact per invocation and
      explicit opt-out

---

## References

- `docs/plans/v0.3.3_IMPLEMENTATION_PLAN.md`
- `docs/plans/v0.3.3_DOCS_ONLY_PR_PLAN.md`
- `docs/decisions/ADR-0009-split-enforcement-model.md`
- `docs/architecture/ARCHITECTURAL_INVARIANTS.md`
- supplied post-`v0.3.2` evolution planning note
