# Release Gates

This file tracks release-entry and release-exit gates for planned work.

---

## `v0.3.3` Groundwork Gate — PR-01

Branch:

- `feat/v0.3.3-01-adr-release-contract`

Checklist:

- [x] `docs/decisions/ADR-0010-governed-agentic-workflows.md` accepted or ready
      for acceptance review
- [x] `docs/dev/pr_context.md` defines the active docs-only PR boundary
- [x] `docs/plans/v0.3.3_IMPLEMENTATION_PLAN.md` defines the dependency sequence
- [x] `docs/plans/v0.3.3_DOCS_ONLY_PR_PLAN.md` constrains PR-01 to groundwork
- [x] `implementation_status.md` includes `v0.3.3` planning entries
- [x] no runtime behavior changed in PR-01
- [x] no schema behavior changed in PR-01

---

## `v0.3.3` Capability Gates

### PR-02 — Audit Schema `v1.4` + Provenance Metadata

- [x] schema change is additive only
- [x] no new required fields are introduced
- [x] PASS artifacts remain valid
- [x] FAIL artifacts remain valid
- [x] provenance fields are optional
- [x] schema and artifact contract tests land with the change

### PR-03 — `AuditLineage`

- [x] lineage reconstruction works from JSONL audit trails
- [x] checksum-based DAG construction is covered by tests
- [x] traversal is covered by tests
- [x] orphan handling is covered by tests
- [x] cycle detection is covered by tests
- [x] no new dependencies are introduced

### PR-04 — CLI Lineage Mode

- [x] compliance export adds `--lineage`
- [x] CLI traversal uses `AuditLineage`
- [x] report output is covered by tests
- [x] examples/docs are updated with the new mode

### PR-05 — `ProvenanceGate`

- [x] built-in gate implementation lands
- [x] gate can be registered at the intended insertion point(s)
- [x] typed failures are covered by tests
- [x] "no output without sources" is enforceable

### PR-06 — `RiskHistory`

- [x] risk history can record scores over time
- [x] trajectory computation is covered for improving paths
- [x] trajectory computation is covered for stable paths
- [x] trajectory computation is covered for degrading paths

### PR-07 — Default Flip to Pre-Call Enforcement

- [x] `@governed` defaults to `pre_call_enforcement=True`
- [x] explicit `pre_call_enforcement=False` opt-out remains available
- [x] one artifact per invocation attempt is preserved
- [x] gate ordering is preserved
- [x] migration tests land with the change

---

## `v0.3.3` Final Release Gate

Workflow-aware SDK outcome:

- [x] provenance is tracked across invocations
- [x] lineage can be reconstructed across invocations
- [x] source-aware gating is available
- [x] graduated trust over time is available
- [x] pre-call governance is the default execution model

Documentation parity targets:

- [x] `README.md`
- [x] `PROJECT.md`
- [x] `CHANGELOG.md`
- [x] `docs/INTEGRATION_GUIDE.md`
- [x] `docs/PUBLIC_INTEGRATION_CONTRACT.md`
- [x] `docs/architecture/AIGC_HIGH_LEVEL_DESIGN.md`
- [x] `docs/architecture/ENFORCEMENT_PIPELINE.md`
- [x] `docs/architecture/ARCHITECTURAL_INVARIANTS.md`
- [x] `schemas/audit_artifact.schema.json`
- [x] public lineage module docs are updated
- [x] public risk-history module docs are updated

Release readiness:

- [x] release notes drafted
- [x] migration notes drafted
- [x] final changelog entry drafted
- [x] release checklist reviewed
