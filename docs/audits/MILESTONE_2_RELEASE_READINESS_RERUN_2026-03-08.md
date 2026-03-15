# Milestone 2 Release Readiness Review — AIGC

Date: 2026-03-08  
Scope: Milestone 2 (`v0.3.0`) release-readiness verification against current workspace state

## 1. Executive Verdict

- Overall verdict: `NOT READY`
- Confidence level: High
- Rationale: The repository remains a strong `v0.2.0` baseline
  (311 tests passing, 94.38% coverage, lint/markdown/doc-parity green), but the
  Milestone 2 capability set defined for `v0.3.0` is still largely absent from
  runtime code, schemas, and CI gates. In this rerun, additional integrity
  defects were confirmed in production paths: cross-instance sink-state leakage,
  sink mutation of in-memory audit artifacts, and no FAIL artifact emission for
  pre-pipeline failures (invocation/policy/strict-mode). Together these block a
  credible Milestone 2 ship decision.

## 2. Authority Stack Used

Applied authority order for this review:

1. `docs/architecture/AIGC_HIGH_LEVEL_DESIGN.md` (architectural anchor)
2. `docs/architecture/AIGC_Architecture_Redesign_and_Roadmap.md` (Milestone roadmap + v0.3.0 scope)
3. `docs/architecture/ARCHITECTURAL_INVARIANTS.md`
4. `docs/architecture/ENFORCEMENT_PIPELINE.md`
5. `docs/architecture/AIGC_THREAT_MODEL.md`
6. `docs/releases/RELEASE_GATES.md` (referenced by roadmap as canonical gates)
7. ADRs in `docs/decisions/*` (Accepted > Proposed; supersession resolved by roadmap where explicit)
8. `PROJECT.md`, `README.md`, `implementation_plan.md`, `CLAUDE.md`, `docs/PUBLIC_INTEGRATION_CONTRACT.md`, `docs/INTEGRATION_GUIDE.md`, `docs/USAGE.md`, `docs/AIGC_FRAMEWORK.md`, `policies/policy_dsl_spec.md`
9. Runtime implementation and tests: `aigc/`, `aigc/_internal/`, `schemas/`, `policies/`, `tests/`, `.github/workflows/`, `scripts/`

Document conflicts found:

- Pipeline order drift in docs: `CLAUDE.md` still documents schema-before-tools and a D-04 known issue, while runtime enforces tools-before-schema.
- Sink semantics drift: roadmap threat table claims `on_sink_failure="raise"` default and “sink receives copy”; runtime default is `log` and sink gets mutable artifact object.
- Fail-closed sink behavior inconsistency: `AIGC_THREAT_MODEL.md` says sink failure must fail-closed; `ARCHITECTURAL_INVARIANTS.md` says `log`/`raise` configurable; integration docs still state sink failures never block.
- Branch-gate drift: `sdk_ci.yml` targets `main`/`dev`; `doc_parity.yml` targets `develop`; docs/references mention `develop`.
- Requested filename mismatch: `IMPLEMENTATION_PLAN.md` (requested) is not present; repository has `implementation_plan.md`.

## 3. Milestone 2 Capability Scorecard

| Capability | Expected by Milestone 2? | Implemented in code? | Tested? | Docs in parity? | Release-ready? | Evidence | Notes / Gaps |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Risk scoring engine (`strict`, `risk_scored`, `warn_only`) | Yes | No | No | No | No | Roadmap v0.3.0 scope in `docs/architecture/AIGC_Architecture_Redesign_and_Roadmap.md:782-795`; no runtime symbols via repository search; `aigc/_internal/audit.py:166-167` keeps `risk_score=None` placeholder | No scoring path, no enforcement-mode semantics, no determinism tests for risk scoring |
| Audit artifact signing | Yes | No | No | No | No | Roadmap `:786`; schema placeholder `schemas/audit_artifact.schema.json:84-87`; runtime placeholder `aigc/_internal/audit.py:167` | No `AuditSigner`, verify path, or signature round-trip tests |
| Policy composition restriction semantics (`intersect / union / replace`) | Yes | No | No | No | No | Roadmap `:787`; current merge is append/recurse/replace in `aigc/_internal/policy_loader.py:95-127`; guard merge same pattern `aigc/_internal/guards.py:478-500` | Privilege-restrictive composition semantics absent |
| Pluggable `PolicyLoader` interface | Yes | No | No | No | No | Roadmap `:788`; runtime hard-calls `load_policy()` in `aigc/_internal/enforcement.py:312,443,477` | No loader abstraction/injection points in enforcement path |
| Policy versioning (`effective_date`, `expiration_date`) | Yes | No | No | No | No | Roadmap `:789`; absent from policy schema `schemas/policy_dsl.schema.json:6-135` and runtime validation | Date-bound policy activation not enforced |
| OpenTelemetry integration | Yes | No | No | No | No | Roadmap `:790`; no optional dependency in `pyproject.toml:52-58`; no OTel code paths found | No spans/metrics wiring in core pipeline |
| Policy testing framework (`aigc.testing.PolicyTestCase`) | Yes | No | No | No | No | Roadmap `:791`; no `aigc.testing` package/symbols | No SDK-level policy testing framework |
| Tamper-evident audit chain | Yes | No | No | No | No | Roadmap `:792`; ADR-0008 proposed in `docs/decisions/ADR-0008-governance-artifact-chain.md:4`; no chain fields in schema/runtime | No chain generation/verification APIs |
| Compliance export CLI (`aigc audit export`) | Yes | No | No | No | No | Roadmap `:793`; CLI only has `aigc policy lint or validate` in `aigc/_internal/cli.py:4-5,144-174` | No compliance export command path |
| Custom `EnforcementGate` plugin interface | Yes | No | No | No | No | Roadmap `:794`; plugin points marked planned only in `docs/architecture/ENFORCEMENT_PIPELINE.md:204-223`; no enforcement-gate interface in runtime | No constrained plugin insertion points |

## 4. Architectural Conformance Review

Conforms to current v0.2 architecture:

- Runtime gate order is correct and security-aligned: guards -> role -> preconditions -> tools -> schema -> postconditions in `aigc/_internal/enforcement.py:176-209`.
- Pre-action proof exists: `metadata.gates_evaluated` populated in PASS/FAIL metadata `aigc/_internal/enforcement.py:222,262`; validated by `tests/test_pre_action_boundary.py`.
- PASS/FAIL artifacts generated inside pipeline failure path and attached to raised governance exceptions in `aigc/_internal/enforcement.py:254-289`.

Non-conformance to stated invariants/roadmap:

- Milestone 2 architecture in roadmap section 6.3 is not implemented (`docs/architecture/AIGC_Architecture_Redesign_and_Roadmap.md:782-795`).
- “Every enforcement attempt emits artifact” invariant is violated for failures before `_run_pipeline()` (invocation validation/policy load/strict validation).
  - Entry points validate/load before pipeline: `aigc/_internal/enforcement.py:311-313,442-445,476-479`.
  - Reproduced: `InvocationValidationError` and `PolicyLoadError` carry `audit_artifact=None`.
- Instance-scoped isolation claim is violated by shared global sink/failure-mode mutation in `AIGC.enforce()`/`enforce_async()` (`aigc/_internal/enforcement.py:447-461,480-494`) backed by module globals `aigc/_internal/sinks.py:20-22`.

## 5. Code Review Findings

### Critical

#### M2-CR-01 — Milestone 2 capability set is unimplemented

- Severity: Critical
- Expected behavior: All v0.3.0 milestone capabilities are real, integrated, tested, and documented.
- Actual behavior: v0.3.0 capabilities remain mostly roadmap-only.
- Evidence:
  - `docs/architecture/AIGC_Architecture_Redesign_and_Roadmap.md:782-795`
  - Absence of runtime symbols/modules for risk/sign/chain/loader plugins/OTel/export/testing
  - `aigc/_internal/cli.py:144-174` only policy lint/validate
- Risk: Invalid release claim and missing compliance/security capabilities.
- Required fix: Implement full M2 runtime + schema + tests + CI gates before tagging v0.3.0.
- Stop-ship: Yes

#### M2-CR-02 — Cross-instance sink-state leakage breaks instance isolation

- Severity: Critical
- Expected behavior: One `AIGC` instance cannot affect sink behavior of another instance.
- Actual behavior: `AIGC.enforce()` mutates module-global sink and failure mode; concurrent instances cross-talk.
- Evidence:
  - Global state: `aigc/_internal/sinks.py:20-22`
  - Runtime mutation: `aigc/_internal/enforcement.py:447-461,480-494`
  - Reproduction (rerun): with `AIGC(sink=CollectSink)` and `AIGC(sink=None)` concurrently, sink captured both instance artifacts: `{'model-A': 500, 'model-B': 497}`.
- Risk: Audit artifacts written to wrong sink and wrong sink-failure policy, violating chain-of-custody.
- Required fix: Remove global sink mutation from instance path; pass sink/failure-mode as per-call immutable context (or guard with strict per-instance locking/context isolation).
- Stop-ship: Yes

#### M2-CR-03 — Sink can mutate audit artifact contents (integrity tampering)

- Severity: Critical
- Expected behavior: Sink receives immutable copy; sink cannot alter artifact returned to caller or attached to exception.
- Actual behavior: `emit_to_sink()` passes mutable artifact object directly.
- Evidence:
  - Pass-through emit: `aigc/_internal/sinks.py:97-102`
  - Reproduction (rerun): custom sink changed `enforcement_result` to `MUTATED`; caller observed mutated artifact.
- Risk: Tampering of governance evidence in-process; undermines forensic trust model.
- Required fix: Deep-copy or immutable-serialize artifact before sink emission; optionally verify post-emit artifact hash unchanged.
- Stop-ship: Yes

#### M2-CR-04 — FAIL artifact guarantee violated for pre-pipeline failures

- Severity: Critical
- Expected behavior: Every enforcement attempt (including invocation/policy/strict-mode failures) yields a FAIL artifact.
- Actual behavior: Failures raised before `_run_pipeline()` have `audit_artifact=None`.
- Evidence:
  - Pre-pipeline raises possible at `aigc/_internal/enforcement.py:311-313,442-445,476-479`
  - Rerun reproduction: `InvocationValidationError`/`PolicyLoadError` show `audit_artifact=None`
  - Invariant docs asserting full-attempt evidence: `docs/architecture/AIGC_HIGH_LEVEL_DESIGN.md:349-353,616-620`
- Risk: Missing forensic records on critical failure classes.
- Required fix: Wrap validation/policy-load/strict checks in an outer artifact-producing failure envelope.
- Stop-ship: Yes

### High

#### M2-CR-05 — Sink-failure FAIL artifact can violate audit schema (`failure_gate="unknown"`)

- Severity: High
- Expected behavior: All emitted/attached artifacts validate against `audit_artifact.schema.json`.
- Actual behavior: `AuditSinkError` maps to `unknown`, but schema enum excludes `unknown`.
- Evidence:
  - Mapping fallback: `aigc/_internal/enforcement.py:139`
  - Schema enum: `schemas/audit_artifact.schema.json:51-53`
  - Rerun reproduction: `AIGC(... on_sink_failure='raise')` produced `failure_gate='unknown'`; schema validation failed.
- Risk: Invalid evidence objects on sink failure path.
- Required fix: Add explicit sink-emission gate ID in schema + mapping, or map to existing allowed gate with documented semantics.
- Stop-ship: Yes (for governance artifact contract integrity)

#### M2-CR-06 — `PolicyCache` is implemented but not used in production enforcement path

- Severity: High
- Expected behavior: Instance path should use cache for repeated policy loads as documented.
- Actual behavior: Enforcement always calls `load_policy()` directly.
- Evidence:
  - Cache class exists: `aigc/_internal/policy_loader.py:268-337`
  - Not used in enforcement: `aigc/_internal/enforcement.py:312,443,477`
- Risk: Performance claims and stale-cache threat mitigations are not realized in runtime path.
- Required fix: Inject per-instance cache and route policy loading through it; add integration tests on cache hits/invalidation.
- Stop-ship: No (M2 parity blocker, not immediate safety blocker)

#### M2-CR-07 — `AIGC.redaction_patterns` is never applied

- Severity: High
- Expected behavior: Instance-provided redaction patterns control sanitization.
- Actual behavior: pipeline calls `sanitize_failure_message(...)` without passing instance patterns.
- Evidence:
  - Instance stores patterns: `aigc/_internal/enforcement.py:412-415`
  - Sanitization calls ignore instance patterns: `aigc/_internal/enforcement.py:237,242`
- Risk: Security customization silently ineffective.
- Required fix: Thread instance patterns into failure sanitization calls in both sync and async paths.
- Stop-ship: No (but high for enterprise security posture)

#### M2-CR-08 — v0.3 release gates are not CI-enforced

- Severity: High
- Expected behavior: Milestone 2 gates (risk determinism, signing verification, restriction correctness, plugin isolation) run in CI.
- Actual behavior: CI covers tests/coverage/lint/markdown/schema validation only.
- Evidence:
  - M2 gates defined: `docs/releases/RELEASE_GATES.md:122-154`
  - CI workflows: `.github/workflows/sdk_ci.yml`, `.github/workflows/release.yml`
- Risk: v0.3 can be tagged without milestone-critical proofs.
- Required fix: Add dedicated M2 gate jobs and make release job depend on them.
- Stop-ship: Yes for v0.3.0

### Medium

#### M2-CR-09 — Authority documentation drift remains unresolved

- Severity: Medium
- Expected behavior: authoritative docs agree on current runtime behavior.
- Actual behavior: stale/contradictory statements for pipeline order, sink defaults, sink immutability, and branch gate model.
- Evidence:
  - `CLAUDE.md:244-252,294-302`
  - `docs/architecture/AIGC_THREAT_MODEL.md:267-274`
  - `docs/PUBLIC_INTEGRATION_CONTRACT.md:122-123,223`
  - `docs/INTEGRATION_GUIDE.md:188`
  - `.github/workflows/sdk_ci.yml:5-7` vs `.github/workflows/doc_parity.yml:4-8`
- Risk: wrong integration assumptions and inconsistent governance posture.
- Required fix: reconcile docs and add parity checks for authority set.
- Stop-ship: No

#### M2-CR-10 — `queue` sink failure mode is exposed but not implemented

- Severity: Medium
- Expected behavior: advertised modes are implemented or removed.
- Actual behavior: `queue` accepted but treated as logging fallback.
- Evidence:
  - Mode accepted: `aigc/_internal/sinks.py:75-77`
  - Comment indicates not implemented: `aigc/_internal/sinks.py:95`
- Risk: integrators may assume durable queueing behavior that does not exist.
- Required fix: either implement queue semantics or deprecate/remove mode.
- Stop-ship: No

### Low

#### M2-CR-11 — Proposed ADR status not aligned with implemented behavior

- Severity: Low
- Expected behavior: implemented architecture decisions are reflected with accepted ADR status or supersession notes.
- Actual behavior: ADR-0007 remains `Proposed` though pipeline evidence is implemented and tested.
- Evidence: `docs/decisions/ADR-0007-pre-action-enforcement-boundary-proof.md:4`; runtime/test evidence in enforcement + `tests/test_pre_action_boundary.py`.
- Risk: process ambiguity during audits.
- Required fix: mark accepted/superseded status explicitly.
- Stop-ship: No

## 6. Security and Governance Review

- Fail-closed behavior:
  - Core gate failures are fail-closed.
  - Sink behavior is configurable (`log` default), not universally fail-closed.
  - Critical gap: pre-pipeline failures do not emit FAIL artifacts.
- Pre-action boundary proof:
  - Present via `metadata.gates_evaluated`; ordering is correctly enforced for current pipeline.
- Determinism:
  - Current checksum and gate-order behavior is deterministic for existing features.
  - M2 determinism (risk scoring/signature/chain) not applicable because features are absent.
- Artifact integrity:
  - Checksums exist, but in-process sink can mutate artifact object (integrity breach).
  - Signing/chaining absent.
- Sink behavior:
  - FAIL-path governance exception preservation is now improved.
  - Cross-instance race and mutability defects remain high risk.
- Policy privilege escalation risk:
  - Restrictive composition semantics are absent; current merge remains additive/replace.
- Plugin safety:
  - Custom gate framework absent, so no runtime proof of M2 plugin-safety guarantees.
- Compliance evidence quality:
  - Adequate for current v0.2 baseline in many flows, but not sufficient for v0.3 compliance claims.

## 7. Test and CI Review

Rerun results on current working tree:

- `python -m pytest -q` -> **311 passed**
- `python -m pytest --cov=aigc --cov-report=term-missing --cov-fail-under=90` -> **311 passed, 94.38% coverage**
- `flake8 aigc` -> **PASS**
- `npx markdownlint-cli2 "**/*.md"` -> **PASS**
- `python scripts/check_doc_parity.py` -> **PASS**

Assessment:

- v0.2 baseline quality gates are healthy.
- M2-proof suites are missing: risk determinism, signature verification, chain verification, composition anti-escalation fuzzing, custom-gate isolation, policy-loader plugin safety, OTel behavior, compliance export correctness.
- Existing concurrency tests do not cover multi-instance sink/failure-mode isolation (`tests/test_enforcement_pipeline.py:296-311` validates only shared single instance).

## 8. Documentation Parity Review

Drift issues requiring coordinated update:

1. `CLAUDE.md` pipeline ordering and D-04 known-issue section vs runtime order.
2. Sink default/failure semantics and mutability claims across:
   - `docs/architecture/AIGC_THREAT_MODEL.md`
   - `docs/PUBLIC_INTEGRATION_CONTRACT.md`
   - `docs/INTEGRATION_GUIDE.md`
   - `docs/architecture/AIGC_Architecture_Redesign_and_Roadmap.md`
3. Branch targeting consistency across workflows/docs (`main`/`dev`/`develop`).
4. Milestone framing consistency: public docs correctly show `v0.2.0`, but roadmap and release-gate docs define unmet `v0.3.0` obligations that CI does not currently enforce.

## 9. Release Gates

| Gate | Pass / Fail / Partial | Evidence | Notes |
| --- | --- | --- | --- |
| Determinism | Partial | Base determinism tests exist (`tests/test_checksum_determinism.py`) | v0.3 risk-score determinism gate absent |
| Security invariants | Partial | Pipeline order + pre-action proof tests pass (`tests/test_pre_action_boundary.py`) | Sink isolation/mutability and pre-pipeline fail-audit gaps violate stronger invariants |
| Milestone 2 features | Fail | Roadmap scope (`docs/architecture/AIGC_Architecture_Redesign_and_Roadmap.md:782-795`) vs runtime absence | Core M2 capability gap |
| Schema parity | Fail | M2 fields/semantics absent in policy/audit schemas | Placeholder-only for risk/signature |
| Golden replays | Partial | Strong v0.2 replay coverage | No M2 replay families for risk/sign/chain/plugins |
| CI | Partial | CI green for baseline in `.github/workflows/sdk_ci.yml`/`release.yml` | M2 gates not automated |
| Doc parity | Partial | `scripts/check_doc_parity.py` passes | Authority docs still conflict on critical behaviors |
| Packaging / installability | Partial | Existing project install path works in current env | Clean-room install and M2 extras (`aigc[opentelemetry]`) not validated |
| Public API clarity | Partial | `README.md` and `aigc/__init__.py` clear for v0.2 | No v0.3 public API for M2 capabilities |
| Backward compatibility / migration | Partial | v0.2 docs and deprecations present | No migration guide for M2 behavior changes (risk modes, composition restrictions, signing, loaders) |

## 10. Ship Recommendation

- Decision: **Do not ship**

Exact blockers:

1. M2 capability set is not implemented in runtime paths.
2. Instance isolation is broken by global sink/failure-mode mutation (cross-instance leakage).
3. Sink can tamper artifact object (integrity violation).
4. FAIL artifact guarantee does not hold for pre-pipeline failures.
5. Sink-failure FAIL artifact can violate schema (`failure_gate='unknown'`).
6. M2 release gates are not CI-enforced.

## 11. Prioritized Remediation Plan

### P0 before release

1. Implement Milestone 2 core capabilities and wire into enforcement path.
   - Files likely affected: `aigc/_internal/enforcement.py`, `aigc/_internal/policy_loader.py`, new M2 modules (`risk`, `signing`, `chain`, `gates`, `loaders`, `observability`, `testing`, `export`), `schemas/*.json`, `aigc/__init__.py`, CLI modules.
   - Tests required: new M2 e2e + unit + golden replays for each capability.
   - Docs to update: roadmap parity docs, API docs, integration docs, release gates.
   - ADR required: Yes (new runtime semantics and extension interfaces).

2. Remove global sink-state mutation from instance enforcement and enforce per-instance sink isolation.
   - Files likely affected: `aigc/_internal/enforcement.py`, `aigc/_internal/sinks.py`.
   - Tests required: multi-instance concurrent isolation tests (`sink=None` vs sinked instance, mixed failure modes).
   - Docs to update: `PROJECT.md`, `README.md`, integration docs, threat model.
   - ADR required: Yes (state/isolation model change).

3. Make artifacts immutable across sink boundary.
   - Files likely affected: `aigc/_internal/sinks.py`, `aigc/_internal/enforcement.py`.
   - Tests required: sink mutation attempt cannot alter returned/attached artifact.
   - Docs to update: threat model and sink contract docs.
   - ADR required: No (if contract clarified as bug fix), Yes if contract redefined.

4. Guarantee FAIL artifact generation for all enforcement failures (including pre-pipeline).
   - Files likely affected: `aigc/_internal/enforcement.py`.
   - Tests required: invocation validation, policy load error, strict-mode error all attach schema-valid FAIL artifacts.
   - Docs to update: high-level design + invariants + ADR alignment.
   - ADR required: Probably No (restoring documented invariant), unless gate taxonomy changes.

5. Add schema-valid sink-failure gate mapping.
   - Files likely affected: `aigc/_internal/enforcement.py`, `schemas/audit_artifact.schema.json`.
   - Tests required: sink failure artifacts validate schema in both log and raise modes.
   - Docs to update: audit artifact contract docs.
   - ADR required: Yes if adding new gate enum value.

### P1 immediately after release

1. Wire `PolicyCache` into `AIGC` hot path with correctness tests and benchmark evidence.
2. Resolve documentation conflicts and tighten parity checker scope to include architecture authority docs.
3. Align workflow branch triggers and release branch policy.

### P2 follow-up hardening

1. Adversarial/fuzz testing for composition escalation prevention and plugin isolation once M2 framework exists.
2. Concurrency stress for chain/signing state correctness.
3. Compliance artifact packaging and export conformance suite.

## 12. Suggested PR Breakdown

1. PR-A: Enforcement-state isolation + immutable sink boundary + universal FAIL artifact envelope
2. PR-B: Risk scoring engine + enforcement modes + audit schema updates
3. PR-C: Signing + chain fields + verification API + CLI verify/export skeleton
4. PR-D: Composition restriction semantics + policy version dates + migration docs
5. PR-E: `PolicyLoader` and `EnforcementGate` interfaces with safety constraints
6. PR-F: OpenTelemetry integration + optional extras + observability tests
7. PR-G: M2 release-gate CI jobs + parity/docs reconciliation + ADR status cleanup

---

## Maintainer Action Summary

Top 10 findings:

1. M2 feature set for `v0.3.0` is not implemented.
2. Cross-instance sink/failure-mode leakage breaks instance isolation.
3. Sink can mutate returned/attached audit artifacts.
4. Pre-pipeline failures do not generate FAIL artifacts.
5. Sink-failure artifacts can violate audit schema (`failure_gate='unknown'`).
6. `PolicyCache` exists but is disconnected from enforcement runtime.
7. `redaction_patterns` config is not wired into sanitization.
8. M2 release gates are not automated in CI.
9. Authority docs conflict on sink behavior, pipeline state, and branch gating.
10. `queue` sink mode is exposed but non-functional.

Top 5 stop-ship blockers:

1. Missing M2 runtime implementation and parity.
2. Broken sink isolation under concurrency (artifact routing leakage).
3. Mutable sink boundary (artifact tampering risk).
4. Missing FAIL artifacts on pre-pipeline failures.
5. Missing M2 CI release-gate enforcement.

Exact next actions:

1. Fix sink isolation and artifact immutability first; add regression tests for concurrent multi-instance paths.
2. Wrap all enforcement-entry failures in schema-valid FAIL artifacts.
3. Implement M2 capabilities (risk/sign/chain/restriction/loaders/gates/OTel/testing/export) in production path.
4. Add M2 golden replay and adversarial suites, then enforce them in CI/release workflows.
5. Reconcile authority docs and ADR statuses in the same release train.

Recommended release decision:

- **Do not ship Milestone 2 (`v0.3.0`) now.**
