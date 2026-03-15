# Milestone 2 Release Readiness Review — AIGC

Date: 2026-03-07  
Scope: Milestone 2 (`v0.3.0`) release-readiness verification

## 1. Executive Verdict

- Overall verdict: `NOT READY`
- Confidence level: High
- Rationale: Milestone 2 capabilities defined in the roadmap are largely not
  implemented in runtime code paths, schemas, CLI, or tests. The repository is
  still positioned as `v0.2.0`. There are also release-blocking correctness and
  security issues in sink/config behavior, plus current CI gate failures on
  linting.

## 2. Authority Stack Used

Applied authority order for this review:

1. Milestone target in roadmap:
   `docs/architecture/AIGC_Architecture_Redesign_and_Roadmap.md`
2. Architectural anchor:
   `docs/architecture/AIGC_HIGH_LEVEL_DESIGN.md`
3. Binding invariants/pipeline/release gates:
   `docs/architecture/ARCHITECTURAL_INVARIANTS.md`,
   `docs/architecture/ENFORCEMENT_PIPELINE.md`,
   `docs/releases/RELEASE_GATES.md`
4. ADRs (`Accepted` prioritized over `Proposed`):
   `docs/decisions/ADR-0001...ADR-0008`
5. Implementation/public contracts:
   `PROJECT.md`, `README.md`, `docs/PUBLIC_INTEGRATION_CONTRACT.md`,
   `docs/INTEGRATION_GUIDE.md`, `docs/USAGE.md`, `docs/AIGC_FRAMEWORK.md`

Conflicts identified:

- `CLAUDE.md` pipeline order and D-04 known-issue text are stale relative to
  actual code and tests.
- Sink failure semantics conflict across threat model, invariants, and
  integration docs.
- Branching and workflow targets conflict (`develop` vs `dev`/`main`).

## 3. Milestone 2 Capability Scorecard

| Capability | Expected by M2 | Implemented | Tested | Docs in parity | Release-ready | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| Risk scoring engine (`strict`, `risk_scored`, `warn_only`) | Yes | No | No | No | No | Only `risk_score: null` placeholder exists |
| Audit artifact signing | Yes | No | No | No | No | `signature` placeholder only |
| Restriction composition (`intersect/union/replace`) | Yes | No | No | No | No | Current merge is append/recurse/scalar replace |
| Pluggable `PolicyLoader` | Yes | No | No | No | No | Runtime still hard-calls `load_policy()` |
| Policy versioning (`effective_date`, `expiration_date`) | Yes | No | No | No | No | Fields absent in schema/runtime |
| OpenTelemetry integration | Yes | No | No | No | No | No OTel module or optional dependency |
| Policy testing framework | Yes | No | No | No | No | No `aigc.testing` surface |
| Tamper-evident audit chain | Yes | No | No | No | No | ADR proposed, no runtime support |
| Compliance export CLI | Yes | No | No | No | No | CLI only supports `policy lint/validate` |
| Custom `EnforcementGate` plugins | Yes | No | No | No | No | Extension points are documented as planned only |

## 4. Architectural Conformance Review

Conforms:

- Runtime gate ordering is correct:
  guards -> role -> preconditions -> tools -> schema -> postconditions
- `metadata.gates_evaluated` is emitted and validated by sentinel tests.
- PASS/FAIL artifact emission exists on main pipeline paths.

Diverges:

- Milestone 2 architecture is not present in implementation.
- Instance-scoped sink behavior is not truly isolated due to global sink
  mutation in `AIGC.enforce()` / `AIGC.enforce_async()`.
- Security contract is ambiguous due to conflicting sink-failure docs.

## 5. Code Review Findings

### Critical

#### M2-CR-01 — Milestone 2 capability set is not implemented

- Expected: M2 `v0.3.0` capabilities are shipped.
- Actual: Repo remains `v0.2.0`; core M2 features absent.
- Risk: False release-readiness claim.
- Stop-ship: Yes

#### M2-CR-02 — `AIGC` instance sink isolation is broken

- Expected: Instance enforcement does not leak global sink state.
- Actual: Previous sink is only restored when non-null; instance sink can remain
  globally registered.
- Risk: Cross-instance sink contamination and unintended artifact routing.
- Stop-ship: Yes

#### M2-CR-03 — `AIGC.on_sink_failure` is effectively ignored

- Expected: Instance-level `on_sink_failure` controls sink failure behavior.
- Actual: Mode is stored but not wired into runtime emission path.
- Risk: Security/operational mismatch vs documented contract.
- Stop-ship: Yes

#### M2-CR-04 — FAIL artifact attachment can be lost when sink mode is `raise`

- Expected: FAIL paths preserve governance evidence even if sink emit fails.
- Actual: Secondary sink error can replace original governance exception without
  attached artifact.
- Risk: Compliance evidence loss on failure paths.
- Stop-ship: Yes

### High

#### M2-CR-05 — Release CI is currently red (lint + markdown)

- `flake8 aigc` fails:
  - `aigc/_internal/audit.py:21:1 E402`
  - `aigc/_internal/cli.py:17:1 F401`
- Markdown lint fails on long lines in
  `docs/demo_app/design/AIGC_STREAMLIT_DESIGN_SPEC.md`.
- Stop-ship: Yes

#### M2-CR-06 — Policy cache is not wired into real enforcement path

- Expected: runtime uses `PolicyCache`.
- Actual: enforcement directly calls `load_policy()`.
- Risk: Documented performance claims exceed actual runtime behavior.
- Stop-ship: No for v0.2.x, Yes for M2 claim parity

#### M2-CR-07 — `AIGC.redaction_patterns` not used in sanitize path

- Expected: per-instance custom redaction patterns are applied.
- Actual: sanitize calls use defaults only.
- Risk: Security customization silently ineffective.
- Stop-ship: No for v0.2.x, Yes for stricter security posture

### Medium

#### M2-CR-08 — M2 release gates are not enforced in CI

- Expected: CI verifies M2 determinism/signing/restriction/plugin isolation.
- Actual: workflows cover tests, coverage, lint, markdown, schema checks only.
- Stop-ship: Yes for M2

#### M2-CR-09 — Documentation authority drift

- Pipeline and sink semantics are inconsistent across authoritative docs.
- Stop-ship: No, but high governance risk

#### M2-CR-10 — Branch/workflow targeting mismatch

- `develop` in docs vs `dev`/`main` in CI and `develop` only in doc parity.
- Stop-ship: No

## 6. Security and Governance Review

- Fail-closed behavior: Partial
- Pre-action boundary proof: Pass (current pipeline)
- Determinism: Pass (current checksum logic)
- Artifact integrity: Partial (checksums yes, M2 signing/chaining no)
- Sink behavior safety: Fail (instance config not reliably enforced)
- Policy privilege escalation prevention: Fail for M2
- Plugin safety: Not verifiable (plugin framework not implemented)
- Compliance evidence quality for M2: Not sufficient

## 7. Test and CI Review

Local verification results:

- `python -m pytest -q`: 304 passed
- `python -m pytest --cov=aigc --cov-fail-under=90`: 304 passed, 93.99%
- `python scripts/check_doc_parity.py`: PASS
- `flake8 aigc`: FAIL
- `npx markdownlint-cli2 "**/*.md"`: FAIL

Coverage and replay baseline are strong for v0.2.x behavior, but M2-specific
proof suites are absent (risk, signing, chain, loader/gate isolation, OTel,
compliance export).

## 8. Documentation Parity Review

Drift items:

1. `CLAUDE.md` stale pipeline ordering and D-04 status
2. Sink-failure behavior contradictions across docs
3. `PROJECT.md` claims cache behavior not present on runtime path
4. Parity checker scope excludes many authority docs, so pass is incomplete
5. Streamlit design spec currently fails markdown lint

Files requiring synchronized updates:

- `CLAUDE.md`
- `docs/architecture/ARCHITECTURAL_INVARIANTS.md`
- `docs/architecture/AIGC_THREAT_MODEL.md`
- `docs/INTEGRATION_GUIDE.md`
- `PROJECT.md`
- `docs/releases/RELEASE_GATES.md`

## 9. Release Gates

| Gate | Status | Notes |
| --- | --- | --- |
| Determinism | Partial | Base determinism passes; no M2 risk determinism |
| Security invariants | Partial | Pipeline order good; sink/config issues remain |
| M2 feature completion | Fail | Core capabilities not implemented |
| Schema parity for M2 | Fail | Missing M2 DSL/artifact fields |
| Golden replays | Partial | Strong v0.2 replay coverage only |
| CI | Fail | Lint and markdown failures |
| Doc parity | Partial | Checker passes but scope is narrow |
| Packaging/installability | Partial | Not re-audited in fresh clean env this pass |
| Public API clarity | Partial | v0.2 API clear; M2 API absent |
| Backward compatibility/migration | Partial | v0.2 documented; M2 migration undefined |

## 10. Ship Recommendation

Recommendation: **Do not ship Milestone 2 now**.

Named blockers:

1. M2 capabilities not implemented
2. Critical sink/config correctness defects
3. FAIL-path evidence loss risk with sink raise mode
4. CI release gates currently failing
5. M2 release-gate proofs absent from CI/test suite

## 11. Prioritized Remediation Plan

### P0 — Before Release

1. Fix sink isolation and per-instance failure-mode wiring
2. Ensure FAIL artifacts are preserved on sink error paths
3. Resolve flake8 and markdownlint failures
4. Implement full M2 capability set with runtime integration
5. Add explicit M2 gates to CI

### P1 — Immediately After Release

1. Wire cache into runtime and benchmark
2. Align branch model and workflow triggers
3. Expand doc parity checks to include architecture authority docs

### P2 — Follow-up Hardening

1. Add long-run concurrency stress suites
2. Formalize M2 migration compatibility documentation
3. Automate compliance evidence packaging

## 12. Suggested PR Breakdown

1. Sink/config correctness hotfixes
2. CI/lint green baseline
3. Risk scoring + modes + schema updates
4. Signing + verification + chain integrity
5. Restriction composition + policy versioning
6. Loader abstraction + enforcement gate plugins
7. OTel + policy testing framework + compliance export CLI
8. CI M2 gates + full authority-doc reconciliation

---

## Maintainer Action Summary

Top 10 findings:

1. M2 feature set is not implemented
2. `AIGC` sink leaks into global state
3. `AIGC.on_sink_failure` is ignored in runtime behavior
4. FAIL artifact can be dropped when sink emits fail in raise mode
5. CI currently fails lint and markdown gates
6. Policy cache is not used in enforcement path
7. Custom redaction patterns are not applied in pipeline
8. No M2 release-gate automation in CI
9. Authority docs conflict on sink semantics
10. Branch/workflow strategy is inconsistent

Top 5 stop-ship blockers:

1. Missing M2 implementations
2. Sink isolation/mode correctness defects
3. Evidence loss risk in failure paths
4. CI gate failures
5. Missing M2 proof tests/gates

Exact next actions:

1. Patch sink/config/evidence path defects
2. Restore CI green status
3. Choose explicit release target (`v0.2.x` patch vs true `v0.3.0`)
4. If `v0.3.0`, implement all M2 capabilities with tests and schema parity
5. Add M2-specific CI gates and reconcile authority docs

Recommended release decision:

- **Do not ship Milestone 2 (`v0.3.0`) now.**
