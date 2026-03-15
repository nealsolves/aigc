# Milestone 2 Release Readiness Review — AIGC (Rerun)

Date: 2026-03-07  
Scope: Milestone 2 (`v0.3.0`) release-readiness verification against current
workspace state

## 1. Executive Verdict

- Overall verdict: `NOT READY`
- Confidence level: High
- Rationale: The repository quality baseline improved materially since the prior
  pass (tests/lint/markdown/doc parity are now green), but Milestone 2
  capabilities from the roadmap are still not implemented in runtime, schema,
  or CLI surfaces.

## 2. Authority Stack Used

Applied authority order in this rerun:

1. `docs/architecture/AIGC_HIGH_LEVEL_DESIGN.md` (anchor)
2. `docs/architecture/AIGC_Architecture_Redesign_and_Roadmap.md`
   (M2 capability source)
3. `docs/architecture/ARCHITECTURAL_INVARIANTS.md`
4. `docs/architecture/ENFORCEMENT_PIPELINE.md`
5. `docs/architecture/AIGC_THREAT_MODEL.md`
6. `docs/releases/RELEASE_GATES.md`
7. `docs/decisions/*` (Accepted > Proposed)
8. `PROJECT.md`, `README.md`, `implementation_plan.md`,
   `docs/PUBLIC_INTEGRATION_CONTRACT.md`, `docs/INTEGRATION_GUIDE.md`,
   `docs/USAGE.md`, `docs/AIGC_FRAMEWORK.md`
9. Runtime code/tests/workflows under `aigc/`, `schemas/`, `tests/`,
   `.github/workflows/`, `scripts/`

Key doc conflicts still present:

- `CLAUDE.md` pipeline section remains stale (legacy order / D-04 note)
  relative to current runtime pipeline.
- Sink failure semantics remain inconsistent across threat model vs invariants
  and integration docs.
- Branch strategy docs (`develop`) remain inconsistent with CI targets
  (`dev`/`main` in sdk_ci, `develop` in doc_parity workflow).

## 3. Milestone 2 Capability Scorecard

| Capability | Expected by M2 | Implemented in code | Tested | Docs in parity | Release-ready |
| --- | --- | --- | --- | --- | --- |
| Risk scoring (`strict`, `risk_scored`, `warn_only`) | Yes | No | No | No | No |
| Audit artifact signing | Yes | No | No | No | No |
| Restriction composition (`intersect/union/replace`) | Yes | No | No | No | No |
| Pluggable `PolicyLoader` | Yes | No | No | No | No |
| Policy versioning (`effective_date`, `expiration_date`) | Yes | No | No | No | No |
| OpenTelemetry integration | Yes | No | No | No | No |
| Policy testing framework | Yes | No | No | No | No |
| Tamper-evident audit chain | Yes | No | No | No | No |
| Compliance export CLI | Yes | No | No | No | No |
| Custom `EnforcementGate` plugins | Yes | No | No | No | No |

Evidence highlights:

- M2 scope definition is explicit in roadmap section 6.3 (`v0.3.0`).
- `aigc/_internal/` has no `risk.py`, `signing.py`, `chain.py`, `loaders.py`,
  `versioning.py`, `otel.py`, `testing.py`, `export.py`, or `gates.py`.
- CLI still only supports `aigc policy lint|validate`.
- Policy and audit schemas still expose placeholders instead of M2 behavior
  contracts.

## 4. Architectural Conformance Review

Conforms (current v0.2 baseline):

- Gate order in runtime pipeline remains correct
  (guards -> role -> preconditions -> tools -> schema -> postconditions).
- `metadata.gates_evaluated` remains present and tested.
- PASS/FAIL audit emission and exception attachment are functioning.
- Sink restore and sink failure-mode restore defects identified previously are
  now fixed and covered by new tests.

Diverges from M2 architecture:

- No risk-scored enforcement path.
- No signing/chaining integrity mechanisms.
- No restriction semantics for composition.
- No loader/gate extension interfaces.
- No OTel integration or compliance export commands.

## 5. Code Review Findings

### Critical

#### M2-RR-01 — Milestone 2 capability set is still unimplemented

- Expected: M2 features from roadmap are production-path reachable.
- Actual: Runtime/schemas/CLI/tests remain at v0.2 capability set.
- Risk: `v0.3.0` release claim would be inaccurate.
- Stop-ship: Yes

### High

#### M2-RR-02 — Policy cache remains disconnected from real enforcement path

- Expected: `AIGC.enforce()` should leverage `PolicyCache`.
- Actual: Enforcement still calls `load_policy()` directly.
- Risk: Claimed caching/perf behavior not realized on hot path.
- Stop-ship: No for v0.2.x, Yes for M2 parity expectations

#### M2-RR-03 — `AIGC.redaction_patterns` still not wired into pipeline sanitize calls

- Expected: Per-instance custom patterns influence failure message sanitization.
- Actual: Pipeline uses `sanitize_failure_message(...)` without instance pattern
  injection.
- Risk: Security customization silently ineffective.
- Stop-ship: No for v0.2.x, Yes for stricter enterprise posture

#### M2-RR-04 — v0.3 release gates remain absent from CI automation

- Expected: CI enforces M2 gates (risk determinism, signature verification,
  restriction correctness, plugin isolation).
- Actual: workflows enforce tests/coverage/lint/markdown/schema checks only.
- Risk: M2 would ship without machine-enforced milestone guarantees.
- Stop-ship: Yes for M2

### Medium

#### M2-RR-05 — Documentation authority drift remains

- Pipeline and sink semantics remain inconsistent across authority docs.
- Risk: integrator confusion and governance ambiguity.
- Stop-ship: No

#### M2-RR-06 — Branch/workflow target mismatch remains

- Docs point to `develop`; SDK CI runs on `dev` and `main`.
- Risk: uneven gate execution across branch flows.
- Stop-ship: No

## 6. Security and Governance Review

- Fail-closed behavior: Improved from prior review in sink exception handling,
  but still lacks M2 security primitives (signing/chain/restriction semantics).
- Pre-action boundary proof: Pass for current pipeline.
- Determinism: Pass for existing checksum/enforcement behavior.
- Artifact integrity: Partial (checksums yes; signing/chaining no).
- Sink behavior: Prior critical defects fixed.
- Policy privilege escalation prevention: Not solved for M2
  (still additive merge behavior).
- Plugin safety: Not assessable for M2 because plugin framework is absent.
- Compliance evidence quality for M2: Not sufficient.

## 7. Test and CI Review

Rerun command results:

- `python -m pytest -q` -> 311 passed
- `python -m pytest --cov=aigc --cov-report=term-missing --cov-fail-under=90`
  -> 311 passed, 94.38% coverage
- `flake8 aigc` -> PASS
- `npx markdownlint-cli2 "**/*.md"` -> PASS
- `python scripts/check_doc_parity.py` -> PASS

Assessment:

- Current v0.2 quality gate health is good.
- M2-specific test families are still missing (risk/signing/chain/composition
  escalation/plugin isolation/OTel/export).

## 8. Documentation Parity Review

Rerun parity script passes. Remaining parity concerns are structural:

1. Authority docs still conflict on sink semantics and branch model.
2. `CLAUDE.md` pipeline narrative remains stale.
3. Parity manifest still excludes several architecture docs from active parity
   checks, so parity PASS is not equivalent to full authority consistency.

## 9. Release Gates

| Gate | Status | Evidence summary |
| --- | --- | --- |
| Determinism | Partial | Base determinism/tests pass; M2 risk determinism missing |
| Security invariants | Partial | Pipeline order proof passes; M2 hardening primitives missing |
| Milestone 2 features | Fail | M2 feature set absent |
| Schema parity | Fail | M2 schema fields/semantics absent |
| Golden replays | Partial | Strong v0.2 coverage; no M2 replay families |
| CI | Pass (v0.2 baseline) | tests/coverage/lint/markdown/doc-parity now green |
| Doc parity | Partial | checker passes; authority conflicts remain |
| Packaging/installability | Partial | not revalidated in a clean throwaway env in this rerun |
| Public API clarity | Partial | v0.2 clear; M2 APIs absent |
| Backward compatibility/migration | Partial | v0.2 migration posture present; no M2 migration story |

## 10. Ship Recommendation

Recommendation: **Do not ship Milestone 2 (`v0.3.0`) now**.

Blocking reasons:

1. M2 capabilities remain unimplemented.
2. M2 release-gate proof automation is absent.
3. M2 schema/API/test parity is not present.

## 11. Prioritized Remediation Plan

### P0 (before M2 release)

1. Implement M2 runtime modules and wire into production path:
   risk scoring, signing, chain, restriction composition, loaders, versioning,
   OTel, testing framework, export CLI, enforcement gate plugins.
2. Update schemas:
   policy DSL (`_merge`, versioning fields), audit artifact (sign/chain/risk
   semantics).
3. Add dedicated M2 tests and golden replays.
4. Add M2 release gates to CI as mandatory jobs.

### P1 (immediately after release)

1. Wire `PolicyCache` into enforcement hot path and benchmark.
2. Align branch model and workflow triggers.
3. Reconcile authority docs and extend parity checks to include architecture
   authority set.

### P2 (hardening follow-up)

1. Concurrency and adversarial stress suites for plugin and chain integrity.
2. Compliance evidence packaging and migration tooling hardening.

## 12. Suggested PR Breakdown

1. PR-A: M2 policy/risk core (risk modes + schema changes)
2. PR-B: Signing + chain integrity
3. PR-C: Composition restrictions + versioning
4. PR-D: Loader abstraction + custom gate interface
5. PR-E: OTel + policy testing framework + export CLI
6. PR-F: M2 CI gates + docs/ADR/parity synchronization

---

## Maintainer Action Summary

Top 10 findings:

1. M2 scope still not implemented
2. No M2 test/golden replay proof
3. No M2 CI gate enforcement
4. Composition remains additive only
5. Signing/chaining not implemented
6. Loader/gate plugin interfaces absent
7. OTel/export/testing framework absent
8. `PolicyCache` not used by enforcement runtime
9. `redaction_patterns` still not piped into enforcement sanitize flow
10. Authority docs remain inconsistent

Top 5 stop-ship blockers:

1. Missing M2 implementation set
2. Missing M2 test evidence
3. Missing M2 CI gates
4. Missing M2 schema/API parity
5. Missing M2 compliance primitives (sign/chain/export)

Exact next actions:

1. Implement and wire M2 features in production path.
2. Add M2 tests and golden fixtures.
3. Add M2 CI release gates.
4. Align docs/ADRs to resolved behavior.
5. Re-run full release audit before tagging.

Recommended release decision:

- **Do not ship Milestone 2 now.**
