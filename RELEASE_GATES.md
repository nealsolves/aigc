# Release Gates

This file tracks release-entry and release-exit gates for planned work.

---

## `v0.3.3` Groundwork Gate — PR-01

Branch:

- `feat/v0.3.3-01-adr-release-contract`

Checklist:

- [x] `docs/decisions/ADR-0010-governed-agentic-workflows.md` accepted or ready
      for acceptance review
- [ ] `docs/dev/pr_context.md` defines the active docs-only PR boundary
- [ ] `docs/plans/v0.3.3_IMPLEMENTATION_PLAN.md` defines the dependency sequence
- [ ] `docs/plans/v0.3.3_DOCS_ONLY_PR_PLAN.md` constrains PR-01 to groundwork
- [ ] `implementation_status.md` includes `v0.3.3` planning entries
- [x] no runtime behavior changed in PR-01
- [x] no schema behavior changed in PR-01

---

## `v0.3.3` Capability Gates

### PR-02 — Audit Schema `v1.4` + Provenance Metadata

- [ ] schema change is additive only
- [ ] no new required fields are introduced
- [ ] PASS artifacts remain valid
- [ ] FAIL artifacts remain valid
- [ ] provenance fields are optional
- [ ] schema and artifact contract tests land with the change

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

- [ ] built-in gate implementation lands
- [ ] gate can be registered at the intended insertion point(s)
- [ ] typed failures are covered by tests
- [ ] "no output without sources" is enforceable

### PR-06 — `RiskHistory`

- [ ] risk history can record scores over time
- [ ] trajectory computation is covered for improving paths
- [ ] trajectory computation is covered for stable paths
- [ ] trajectory computation is covered for degrading paths

### PR-07 — Default Flip to Pre-Call Enforcement

- [ ] `@governed` defaults to `pre_call_enforcement=True`
- [ ] explicit `pre_call_enforcement=False` opt-out remains available
- [ ] one artifact per invocation attempt is preserved
- [ ] gate ordering is preserved
- [ ] migration tests land with the change

---

## `v0.3.3` Final Release Gate

Workflow-aware SDK outcome:

- [ ] provenance is tracked across invocations
- [ ] lineage can be reconstructed across invocations
- [ ] source-aware gating is available
- [ ] graduated trust over time is available
- [ ] pre-call governance is the default execution model

Documentation parity targets:

- [ ] `README.md`
- [ ] `PROJECT.md`
- [ ] `CHANGELOG.md`
- [ ] `docs/INTEGRATION_GUIDE.md`
- [ ] `docs/PUBLIC_INTEGRATION_CONTRACT.md`
- [ ] `docs/architecture/AIGC_HIGH_LEVEL_DESIGN.md`
- [ ] `docs/architecture/ENFORCEMENT_PIPELINE.md`
- [ ] `docs/architecture/ARCHITECTURAL_INVARIANTS.md`
- [ ] `schemas/audit_artifact.schema.json`
- [ ] public lineage module docs are updated
- [ ] public risk-history module docs are updated

Release readiness:

- [ ] release notes drafted
- [ ] migration notes drafted
- [ ] final changelog entry drafted
- [ ] release checklist reviewed
