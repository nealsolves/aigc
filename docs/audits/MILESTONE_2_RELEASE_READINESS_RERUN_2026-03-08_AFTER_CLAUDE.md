# Milestone 2 Release Readiness Review — AIGC

Date: 2026-03-08  
Scope: Milestone 2 (`v0.3.0`) release-readiness rerun after remediation updates

## 1. Executive Verdict

- Overall verdict: `NOT READY`
- Confidence level: High
- Rationale: The repository has materially improved and most previously
  reported runtime integrity defects are now fixed and verified
  (sink isolation, artifact immutability, pre-pipeline FAIL artifacts,
  schema-valid sink gate mapping, cache wiring, redaction wiring,
  ADR status alignment). However, Milestone 2 (`v0.3.0`) capabilities and
  their CI release gates are still unimplemented. This remains a no-ship for
  Milestone 2, while the current codebase appears substantially healthier for
  a `v0.2.x` line.

## 2. Authority Stack Used

Applied authority order in this rerun:

1. `docs/architecture/AIGC_HIGH_LEVEL_DESIGN.md`
2. `docs/architecture/AIGC_Architecture_Redesign_and_Roadmap.md`
3. `docs/architecture/ARCHITECTURAL_INVARIANTS.md`
4. `docs/architecture/ENFORCEMENT_PIPELINE.md`
5. `docs/architecture/AIGC_THREAT_MODEL.md`
6. `docs/releases/RELEASE_GATES.md`
7. `docs/decisions/*`
8. `PROJECT.md`, `README.md`, `CLAUDE.md`, `docs/PUBLIC_INTEGRATION_CONTRACT.md`, `docs/INTEGRATION_GUIDE.md`, `docs/USAGE.md`, `docs/AIGC_FRAMEWORK.md`, `policies/policy_dsl_spec.md`
9. Runtime/tests/CI in `aigc/`, `schemas/`, `tests/`, `.github/workflows/`, `scripts/`

Conflicts still present:

- `CLAUDE.md` still contains stale D-04 text and outdated gate-order narrative.
- `AIGC_THREAT_MODEL.md` still states sink failures must fail-closed unconditionally, while runtime and invariants support configurable `log`/`raise`.
- Roadmap threat table still references `on_sink_failure="raise"` default and “sink receives copy” as if already baseline behavior.
- Branch target drift remains between workflows (`main`/`dev` vs `develop`).

## 3. Milestone 2 Capability Scorecard

| Capability | Expected by Milestone 2? | Implemented in code? | Tested? | Docs in parity? | Release-ready? | Evidence | Notes / Gaps |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Risk scoring engine (`strict`, `risk_scored`, `warn_only`) | Yes | No | No | No | No | Roadmap `docs/architecture/AIGC_Architecture_Redesign_and_Roadmap.md:782-795`; repo search found no runtime symbols | Placeholder `risk_score` remains `None` |
| Audit artifact signing | Yes | No | No | No | No | Roadmap `:786`; schema/runtime placeholders only | No signer/verify implementation |
| Composition restriction semantics (`intersect/union/replace`) | Yes | No | No | No | No | Roadmap `:787`; merge remains append/recurse/scalar replace | `_merge` semantics absent in policy schema/runtime |
| Pluggable `PolicyLoader` interface | Yes | No | No | No | No | Roadmap `:788`; enforcement uses direct load/cache calls | No loader abstraction for runtime injection |
| Policy version dates (`effective_date`/`expiration_date`) | Yes | No | No | No | No | Roadmap `:789`; absent in policy schema/runtime | No date activation/expiry enforcement |
| OpenTelemetry integration | Yes | No | No | No | No | Roadmap `:790`; no OTel package/runtime hooks | No spans/metrics in enforcement flow |
| Policy testing framework | Yes | No | No | No | No | Roadmap `:791`; no `aigc.testing` implementation | Missing framework/API |
| Tamper-evident audit chain | Yes | No | No | No | No | Roadmap `:792`; ADR-0008 still planned scope | No chain fields/verify path runtime |
| Compliance export CLI | Yes | No | No | No | No | Roadmap `:793`; CLI still `aigc policy lint or validate` | Export command absent |
| Custom `EnforcementGate` plugin interface | Yes | No | No | No | No | Roadmap `:794`; plugin points still planned-only | No custom gate insertion model |

## 4. Architectural Conformance Review

Conforms (current baseline):

- Gate order remains correct (guards -> role -> preconditions -> tools -> schema -> postconditions).
- `metadata.gates_evaluated` remains present and tested.
- PASS/FAIL artifacts now also cover pre-pipeline failures (invocation/policy/strict-mode).
- Instance path now uses per-instance sink/failure mode injection and policy cache.

Divergence from M2 architecture remains:

- No M2 core capabilities in runtime path.
- No M2 gates in CI.
- No M2 schema/API/test parity.

## 5. Code Review Findings

### Critical

#### M2-RR-01 — Milestone 2 feature set still missing

- Severity: Critical
- Expected behavior: Milestone 2 roadmap capabilities implemented and wired.
- Actual behavior: Capability set remains absent.
- Evidence: roadmap scope (`docs/architecture/AIGC_Architecture_Redesign_and_Roadmap.md:782-795`), no matching runtime symbols, no matching CLI commands.
- Risk: `v0.3.0` release claim would be false.
- Required fix: Implement M2 capability set with tests/schemas/docs.
- Stop-ship: Yes

### High

#### M2-RR-02 — Milestone 2 release gates still not CI-enforced

- Severity: High
- Expected behavior: CI enforces v0.3 additional gates.
- Actual behavior: CI still only enforces baseline tests/coverage/lint/markdown/schema.
- Evidence: `.github/workflows/sdk_ci.yml`; required gates in `docs/releases/RELEASE_GATES.md:122-154`.
- Risk: v0.3 regressions can ship undetected.
- Required fix: Add M2-specific CI jobs and release dependencies.
- Stop-ship: Yes

### Medium

#### M2-RR-03 — Claimed “all verification gates pass” is not fully accurate for current repo command set

- Severity: Medium
- Expected behavior: markdown gate passes for `npx markdownlint-cli2 "**/*.md"`.
- Actual behavior: markdown gate currently fails on `docs/audits/m2_remediation_plan.md` (ordered-list prefix).
- Evidence: rerun command output shows MD029 errors at lines 72, 76, 77.
- Risk: CI/local gate mismatch and misleading readiness signal.
- Required fix: normalize ordered-list numbering in that file.
- Stop-ship: No

#### M2-RR-04 — Authority-doc drift remains partially unresolved

- Severity: Medium
- Expected behavior: authority docs align with code.
- Actual behavior: public sink docs were corrected, but core authority docs still conflict on sink behavior and historical pipeline notes.
- Evidence: `CLAUDE.md`, `docs/architecture/AIGC_THREAT_MODEL.md`, roadmap threat table.
- Risk: governance ambiguity for maintainers/reviewers.
- Required fix: reconcile remaining authority docs and extend parity checks if needed.
- Stop-ship: No

### Low

#### M2-RR-05 — `queue` remains exposed in module-global sink API without distinct implementation

- Severity: Low
- Expected behavior: exposed modes have concrete semantics or explicit deprecation.
- Actual behavior: `set_sink_failure_mode()` still accepts `queue`; behavior remains effectively log-style fallback.
- Evidence: `aigc/_internal/sinks.py:76-79,111-121`.
- Risk: minor integrator expectation confusion.
- Required fix: deprecate/remove or implement queue semantics.
- Stop-ship: No

## 6. Security and Governance Review

- Fail-closed behavior: improved and consistent on core gate failures; sink failures configurable as designed.
- Pre-action boundary proof: intact (`metadata.gates_evaluated` and ordering tests).
- Determinism: baseline deterministic behavior preserved.
- Artifact integrity: sink-side mutation issue is fixed via deep-copy emission.
- Sink behavior: cross-instance leakage issue appears fixed in code/tests and direct repro.
- Policy escalation risk: M2 restriction semantics not implemented yet.
- Plugin safety: not assessable for M2 custom gates because framework still absent.
- Compliance evidence quality: improved for baseline; still below v0.3 scope due missing signing/chaining/export/risk features.

## 7. Test and CI Review

Rerun results:

- `python -m pytest -q` -> **322 passed**
- `python -m pytest --cov=aigc --cov-report=term-missing --cov-fail-under=90` -> **322 passed, 93.58%**
- `flake8 aigc` -> **PASS**
- `python scripts/check_doc_parity.py` -> **PASS**
- Schema validation script -> **PASS**
- `npx markdownlint-cli2 "**/*.md"` -> **FAIL** (3 MD029 errors in `docs/audits/m2_remediation_plan.md`)

Assessment:

- Claimed test/coverage/flake8/schema/doc-parity metrics are confirmed.
- Claimed markdown-clean status is not confirmed with the full wildcard command.
- M2-proof suites remain absent by design (capability gap).

## 8. Documentation Parity Review

Resolved since last audit:

- Sink behavior wording updated in:
  - `docs/PUBLIC_INTEGRATION_CONTRACT.md`
  - `docs/INTEGRATION_GUIDE.md`

Still drifting:

- `CLAUDE.md` pipeline section stale.
- `docs/architecture/AIGC_THREAT_MODEL.md` sink-failure statement conflicts with runtime configurability.
- Roadmap threat table still reflects a stronger sink-default claim than code baseline.

## 9. Release Gates

| Gate | Pass / Fail / Partial | Evidence | Notes |
| --- | --- | --- | --- |
| Determinism | Partial | Base determinism checks pass | M2 risk determinism gate not applicable yet (feature missing) |
| Security invariants | Partial | Core boundary/integrity defects fixed | M2 hardening primitives still missing |
| Milestone 2 features | Fail | Capability set absent | Primary stop-ship |
| Schema parity | Fail | M2 schema semantics absent | Placeholders only |
| Golden replays | Partial | Strong baseline replay suite | No M2 replay families |
| CI | Partial | Baseline CI healthy | M2 gates absent |
| Doc parity | Partial | Parity checker passes | authority-doc conflicts remain |
| Packaging / installability | Partial | not fully rerun in clean env this pass | baseline unchanged |
| Public API clarity | Partial | clear for v0.2 line | no v0.3 API surface |
| Backward compatibility / migration | Partial | v0.2 posture intact | no v0.3 migration material |

## 10. Ship Recommendation

- Recommendation: **Do not ship Milestone 2 (`v0.3.0`) now**.

Exact blockers:

1. M2 capability set not implemented.
2. M2 release gates not enforced in CI.
3. M2 schema/API/test parity absent.

## 11. Prioritized Remediation Plan

### P0 before Milestone 2 release

1. Implement M2 capabilities (risk modes, signing, chain, composition restrictions, loader/gate interfaces, policy dates, OTel, policy-testing framework, export CLI).
2. Add M2 schema updates (`policy_dsl`, `audit_artifact`) and compatibility tests.
3. Add M2 release-gate CI jobs aligned to `docs/releases/RELEASE_GATES.md`.

### P1 immediately after release

1. Resolve remaining authority-doc drift (`CLAUDE.md`, threat/roadmap sink statements).
2. Fix markdown lint issues in `docs/audits/m2_remediation_plan.md`.

### P2 hardening

1. Adversarial/fuzz suites for composition and custom-gate safety once features land.
2. Chain/signing concurrency stress tests.

## 12. Suggested PR Breakdown

1. PR-A: M2 risk + schema groundwork
2. PR-B: signing + chain + verify APIs
3. PR-C: composition restriction semantics + policy version dates
4. PR-D: loader and custom-gate interfaces
5. PR-E: OTel + policy testing framework + compliance export CLI
6. PR-F: CI release gates + authority-doc reconciliation

---

## Maintainer Action Summary

Top 10 findings:

1. Most prior runtime integrity defects are fixed and verified.
2. M2 feature set remains unimplemented.
3. M2 CI release gates remain absent.
4. Public sink docs were corrected.
5. Authority docs still have sink/pipeline drift.
6. Baseline gates mostly pass.
7. Markdown gate currently fails on `m2_remediation_plan.md` numbering.
8. Policy cache now wired per instance.
9. Pre-pipeline failures now emit FAIL artifacts.
10. Sink mutation and cross-instance leakage issues appear fixed.

Top 5 stop-ship blockers:

1. Missing M2 runtime capabilities.
2. Missing M2 CI gates.
3. Missing M2 schema parity.
4. Missing M2 golden replay/test families.
5. Missing M2 public API/migration contract.

Exact next actions:

1. Keep current fixes and branch from this baseline.
2. Decide release intent explicitly: `v0.2.x` hardening vs true `v0.3.0`.
3. If `v0.3.0`, implement full M2 scope before tagging.
4. Add M2 gate jobs to CI/release workflows.
5. Re-run this audit after M2 implementation lands.

Recommended release decision:

- **For Milestone 2 (`v0.3.0`): Do not ship yet.**
- **For `v0.2.x` hardening line: close to ready once markdown/doc drift cleanup is done.**
