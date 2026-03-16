# AIGC Release 0.3.0 Readiness Audit

## 1. Executive Summary
The rerun audit on 2026-03-16 shows core release gates are now passing locally:
documentation parity, tests, coverage threshold, flake8, markdown lint, and
schema/policy validation. Based on current evidence, release status is
**CONDITIONAL GO**: no hard technical gate is failing, but one material
documentation-contract inconsistency and two governance-document fidelity issues
should be resolved (or explicitly waived) before tagging.

**Recommended status:** **CONDITIONAL GO**

**Findings count:**
- H1: 0
- M1: 1
- M2: 2
- L1: 1
- INFO: 2

## 2. Scope and Method
### Files reviewed
Required contract set:
- `CLAUDE.md`
- `README.md`
- `PROJECT.md`
- `ARCHITECTURAL_INVARIANTS.md`
- `docs/architecture/AIGC_HIGH_LEVEL_DESIGN.md`
- `docs/architecture/AIGC_Architecture_Redesign_and_Roadmap.md`
- `docs/INTEGRATION_GUIDE.md`
- `docs/USAGE.md`
- `docs/PUBLIC_INTEGRATION_CONTRACT.md`
- `doc_parity_manifest.yaml`
- `.github/workflows/sdk_ci.yml`
- `.github/workflows/doc_parity.yml`
- `.github/pull_request_template.md`

Additional release-relevant files:
- `.github/workflows/release.yml`
- `docs/releases/RELEASE_GATES.md`
- `SECURITY.md`
- `pyproject.toml`
- `aigc/__init__.py`
- `aigc/_internal/enforcement.py`
- `aigc/_internal/policy_loader.py`
- `aigc/_internal/sinks.py`
- `aigc/_internal/signing.py`
- `aigc/_internal/audit_chain.py`
- `aigc/_internal/decorators.py`
- `aigc/_internal/cli.py`
- `schemas/audit_artifact.schema.json`
- `schemas/policy_dsl.schema.json`
- `tests/test_pre_action_boundary.py`
- `tests/test_audit_artifact_contract.py`
- `tests/test_golden_replay_risk_scoring.py`
- `tests/test_signing.py`
- `tests/test_composition_semantics.py`
- `tests/test_custom_gates.py`

### Commands executed
- `git branch --show-current`
- `git status --short --branch`
- `python scripts/check_doc_parity.py`
- `flake8 aigc`
- `npx markdownlint-cli2 "**/*.md"`
- `python -m pytest --cov=aigc --cov-report=term-missing --cov-fail-under=90`
- schema/policy validation snippet (`Draft7Validator.check_schema` + policy validation)
- `python -m pytest --collect-only -q | tail -n 1`
- `python -m coverage report | tail -n 2`
- `python -m build --sdist --wheel --outdir /tmp/aigc-build-rerun2`
- `python -m build --sdist --wheel --outdir /tmp/aigc-build-rerun2 --no-isolation`

### Environment notes
- Date: 2026-03-16
- Platform: Darwin, Python 3.12.9
- Branch: `docs/milestone1-parity-fixes`
- Working tree during audit: **clean**

### Limitations
- GitHub-hosted CI jobs were not executed in this rerun; readiness is based on local replication plus workflow inspection.
- Isolated package build cannot fetch dependencies in this network-restricted environment.

## 3. Release Criteria
Release criteria were derived from repository-native contracts (README, CLAUDE, workflows, release gates):
- doc parity hard gate
- pytest + coverage gate (>= 90)
- flake8 gate
- markdown lint gate
- policy/schema validation
- architecture invariants (including tool-before-schema ordering)
- golden replay readiness and deterministic contract
- release workflow gating before publish

## 4. Results by Audit Dimension

| Dimension | Result | Classification | Evidence |
|---|---|---|---|
| A. Metadata/version consistency | Pass | Verified pass | Version `0.3.0` aligned in `pyproject.toml`, `aigc.__version__`, README, CLAUDE, PROJECT, manifest. |
| B. Packaging/public API readiness | Mostly pass | Partial evidence only | Public exports align; local isolated build failed for network reasons; `--no-isolation` build succeeded. |
| C. Test suite health and coverage | Pass | Verified pass | `560 passed`; total coverage `94.35%` with `--cov-fail-under=90`. |
| D. Linting/markdown quality | Pass | Verified pass | `flake8` pass; markdownlint summary `0 error(s)`. |
| E. Policy/schema validation health | Pass | Verified pass | `Draft7Validator.check_schema` for both schemas and all policy YAML files validated. |
| F. Documentation parity/internal consistency | Partial | Partial evidence only | `check_doc_parity.py` pass, but one public doc still contradicts shipped warn/log semantics. |
| G. Architecture-to-implementation parity | Mostly pass | Partial evidence only | Pipeline ordering and gate constants align and are sentinel-tested. |
| H. Golden replay/determinism/audit integrity | Pass | Verified pass | Golden replay suites pass under full pytest; signing/risk/custom-gate tests pass. |
| I. Failure-gate taxonomy/audit schema stability | Pass | Verified pass | Failure-gate mapping, schema enum, and artifact contract tests align (`audit_schema_version` 1.2). |
| J. Release pipeline/workflow readiness | Partial | Partial evidence only | Required gates largely present; release workflow policy/schema step does not explicitly check audit schema via `check_schema`. |
| K. Security/compliance posture (stated scope) | Pass | Verified pass | `SECURITY.md` now includes `0.3.x`; sanitization/signing controls tested. |
| L. Roadmap/release-boundary honesty | Partial | Partial evidence only | Roadmap file includes mixed proposed/historical semantics that diverge from shipped runtime behavior. |
| M. Missing artifacts/stale docs/dead links/blockers | Pass | Verified pass | No markdown/link/doc-parity blockers found in rerun. |
| N. Risk assessment and recommendation | CONDITIONAL GO | Evidence-backed | No hard gate failures; remaining issues are doc/governance fidelity risks. |

### Feature Truth Table (Requested Planned-vs-Shipped Check)

| Feature | Status | Evidence |
|---|---|---|
| hash chaining / governance artifact chain | IMPLEMENTED (opt-in) + TESTED | `aigc/_internal/audit_chain.py`; `tests/test_audit_chain.py`; README calls out opt-in chain. |
| signing | IMPLEMENTED + TESTED | `aigc/_internal/signing.py`; `tests/test_signing.py`; golden signing tests. |
| instance-scoped AIGC API as default | PARTIALLY IMPLEMENTED | `AIGC` exists and is recommended, but global `set_audit_sink()`/`enforce_invocation()` remain for compatibility. |
| risk-scored / warn_only semantics | IMPLEMENTED + TESTED | schema risk modes + `tests/test_golden_replay_risk_scoring.py`; runtime supports strict/risk_scored/warn_only. |
| custom gates | IMPLEMENTED + TESTED | `aigc/_internal/gates.py`; `tests/test_custom_gates.py`. |
| async behavior | IMPLEMENTED + TESTED | `enforce_invocation_async` and `AIGC.enforce_async`; async tests passing. |
| decorator behavior | IMPLEMENTED + TESTED | `inspect.signature()` binding in decorators; `tests/test_decorators.py`. |
| sink behavior | IMPLEMENTED + TESTED | sink modes `raise/log` (+ deprecated queue mapping); sink tests pass. |
| strict mode | IMPLEMENTED + TESTED | strict policy validation in `AIGC`; `tests/test_strict_mode.py`. |
| policy composition semantics | IMPLEMENTED + TESTED | `composition_strategy` (`intersect/union/replace`) + composition tests. |
| typed precondition support | IMPLEMENTED + TESTED | schema supports typed preconditions + strict-mode/adversarial tests. |

## 5. Detailed Findings
### [M1-01] Public Governance Statement Conflicts with Shipped Warn/Log Semantics
**Severity rationale:** Significant contract clarity risk in public docs.

**Evidence:**
- `docs/AIGC_FRAMEWORK.md:47-48` states there is no "warn and continue" and no "log and proceed".
- Runtime supports `warn_only` risk mode and non-blocking sink mode:
  - `schemas/policy_dsl.schema.json:78-81` (`warn_only`)
  - `aigc/_internal/enforcement.py:704, 722-726` (`on_sink_failure` with `log`)
  - `aigc/_internal/sinks.py:87-105` and warning behavior.

**Impact on v0.3.0:** Integrators can be misled about actual enforcement semantics and failure handling guarantees.

**Recommended action:** Update `docs/AIGC_FRAMEWORK.md` wording to scope fail-closed claims to core governance gates and explicitly describe configured exceptions (`warn_only`, sink `log`).

**Pre-release required?:** Yes (or explicit waiver)

### [M2-01] Release Workflow Does Not Explicitly `check_schema()` Audit Schema
**Severity rationale:** Non-blocking but meaningful release-governance gap.

**Evidence:**
- `docs/releases/RELEASE_GATES.md:27-33` states both policy and audit schemas must pass `Draft7Validator.check_schema()`.
- `.github/workflows/release.yml` validates policy schema/policies but does not explicitly run audit schema `check_schema()`.
- `sdk_ci.yml` does include explicit check for both schemas.

**Impact on v0.3.0:** Tag-triggered release workflow relies on indirect coverage from tests rather than explicit parity with the stated schema gate.

**Recommended action:** Add explicit audit schema `Draft7Validator.check_schema()` to `release.yml` schema step or narrow docs to describe where each schema check is enforced.

**Pre-release required?:** No

### [M2-02] Roadmap Document Still Mixes Proposed-State and Shipped-State Semantics
**Severity rationale:** Important documentation-fidelity risk, especially because roadmap is listed as architectural authority.

**Evidence:**
- `docs/architecture/AIGC_Architecture_Redesign_and_Roadmap.md` header: `SDK Version Under Review: 0.1.3`, `Status: Proposed`.
- Same file contains historical/proposed semantics that differ from shipped runtime, including references like `enforcement_result: "WARN"`, `queue` mode as a config mode, and `_merge` semantics in ADR discussion sections.

**Impact on v0.3.0:** Readers can conflate proposal-history text with current release contract.

**Recommended action:** Add an explicit "historical/proposed sections" banner and a concise "Current v0.3.0 contract" summary section at top with pointers to canonical current-state docs.

**Pre-release required?:** No

### [L1-01] CLAUDE.md DSL Spec Path Uses Outdated Location
**Severity rationale:** Low-risk doc hygiene issue.

**Evidence:**
- `CLAUDE.md:389` references `docs/policy_dsl_spec.md`.
- Canonical spec is in `policies/policy_dsl_spec.md`.

**Impact on v0.3.0:** Contributor confusion during policy-spec updates.

**Recommended action:** Update path reference in CLAUDE.

**Pre-release required?:** No

### [INFO-01] All Required Local Release Gates Passed in Rerun
**Severity rationale:** Not a defect; notable readiness signal.

**Evidence:**
- doc parity PASS
- flake8 PASS
- markdownlint PASS
- pytest + coverage PASS
- schema/policy validation PASS

**Impact on v0.3.0:** Confirms hard technical gate posture is currently healthy in local replication.

**Recommended action:** Preserve this state when preparing the tag commit.

**Pre-release required?:** No

### [INFO-02] Isolated Build Failure Is Environmental, Not Repository Defect
**Severity rationale:** Informational reproducibility note.

**Evidence:**
- `python -m build` failed while fetching `setuptools` (DNS/network restricted).
- `python -m build --no-isolation` succeeded and produced wheel+sdist.

**Impact on v0.3.0:** No hosted-CI blocker implied; relevant for offline/local release rehearsals.

**Recommended action:** Keep release docs explicit about restricted-network install/build behavior.

**Pre-release required?:** No

## 6. Drift Matrix

| Topic | Code | Docs | Tests | CI | Status | Notes |
|---|---|---|---|---|---|---|
| pipeline ordering | Tools before schema implemented | Invariants + pipeline docs align | Sentinel tests enforce | Full pytest in CI | Aligned | Security-critical ordering evidence present. |
| failure_gate taxonomy | Enum + mapping implemented | Docs aligned | Contract/mapping tests pass | CI runs tests | Aligned | `tool_validation` vs `tool_constraint_validation` distinction remains intentional. |
| audit schema version | `1.2` in schema/code | docs/manifests match | Contract tests assert | CI validates artifact contract | Aligned | No version drift detected. |
| risk scoring modes | strict/risk_scored/warn_only in code | Most docs aligned | risk tests + golden replay | CI runs tests | Aligned | Determinism verified by repeated-risk tests. |
| signing/chaining | signing integrated; chain utility opt-in | docs now call chain opt-in | signing/chain tests pass | CI runs tests | Aligned | Not default-auto chain in pipeline. |
| custom gates | ABC + insertion points implemented | documented | custom-gate suites pass | CI runs tests | Aligned | Includes immutability/failure-mapping checks. |
| async enforcement | sync/async parity implemented | documented | async tests pass | CI runs tests | Aligned | Uses `asyncio.to_thread`. |
| decorator API | signature-bound extraction implemented | contract docs updated | decorator tests pass | CI runs tests | Aligned | Reordered named args supported. |
| sink behavior | raise/log, queue deprecated | docs mostly aligned | sink tests pass | CI runs tests | Partial drift | `AIGC_FRAMEWORK` absolute fail-closed text conflicts with current configurable behavior. |
| typed preconditions | typed + legacy-deprecated support | documented | strict/adversarial tests pass | CI runs tests | Aligned | Strict mode enforces typed requirements. |
| doc parity rules | manifest-based checker | docs reflect checker scope | checker passes | doc_parity workflow | Aligned | Parity checks consistency set, not complete semantic truth across all docs. |
| version/test/coverage claims | runtime 560/94.35 | docs/manifests now 560/94 | verified by rerun | CI threshold 90 | Aligned | Previous stale-count drift is resolved in current working tree. |

## 7. Command Output Summary
- **Doc parity:** `python scripts/check_doc_parity.py` => PASS (`PASSED: all documentation parity checks OK`).
- **flake8:** `flake8 aigc` => PASS (no output).
- **markdownlint:** `npx markdownlint-cli2 "**/*.md"` => PASS (`Summary: 0 error(s)`).
- **pytest + coverage:** `python -m pytest --cov=aigc --cov-fail-under=90` => PASS (`560 passed`, `Total coverage: 94.35%`).
- **schema validation snippet:** PASS (both schemas check; all policies validated).
- **packaging sanity:** isolated build failed due environment DNS restriction; `--no-isolation` build succeeded.

## 8. Go / No-Go Recommendation
**CONDITIONAL GO**

### Why
- No hard release gate is failing in this rerun.
- Remaining risk is documentation-contract fidelity, not runtime correctness or CI hard-gate failure.

### Exact blocking items
- None at H1 level.

### Must fix before tag (recommended)
- Resolve M1-01 doc contradiction (`docs/AIGC_FRAMEWORK.md`) or explicitly waive.

### Can wait until after release
- M2-01 release workflow explicit audit-schema check parity.
- M2-02 roadmap proposal/shipped boundary clarity.
- L1-01 CLAUDE path hygiene.

## 9. Suggested Remediation Sequence
1. Update `docs/AIGC_FRAMEWORK.md` to align fail-closed claims with shipped warn/log semantics.
2. Decide whether to harden `release.yml` with explicit audit schema `check_schema()` or adjust release-gates wording.
3. Add a concise "current-state" banner to the roadmap doc to separate proposal/historical sections.
4. Fix the `CLAUDE.md` policy DSL spec path reference.

## Appendix A — Files Reviewed
- `CLAUDE.md`
- `README.md`
- `PROJECT.md`
- `ARCHITECTURAL_INVARIANTS.md`
- `docs/architecture/ARCHITECTURAL_INVARIANTS.md`
- `docs/architecture/AIGC_HIGH_LEVEL_DESIGN.md`
- `docs/architecture/AIGC_Architecture_Redesign_and_Roadmap.md`
- `docs/INTEGRATION_GUIDE.md`
- `docs/USAGE.md`
- `docs/PUBLIC_INTEGRATION_CONTRACT.md`
- `docs/AIGC_FRAMEWORK.md`
- `docs/architecture/ENFORCEMENT_PIPELINE.md`
- `docs/releases/RELEASE_GATES.md`
- `doc_parity_manifest.yaml`
- `.github/workflows/sdk_ci.yml`
- `.github/workflows/doc_parity.yml`
- `.github/workflows/release.yml`
- `.github/pull_request_template.md`
- `pyproject.toml`
- `SECURITY.md`
- `aigc/__init__.py`
- `aigc/_internal/enforcement.py`
- `aigc/_internal/policy_loader.py`
- `aigc/_internal/sinks.py`
- `aigc/_internal/signing.py`
- `aigc/_internal/audit_chain.py`
- `aigc/_internal/decorators.py`
- `aigc/_internal/cli.py`
- `schemas/audit_artifact.schema.json`
- `schemas/policy_dsl.schema.json`
- selected tests listed in Section 2

## Appendix B — Commands Executed
- `git branch --show-current`
- `git status --short --branch`
- `python scripts/check_doc_parity.py`
- `flake8 aigc`
- `npx markdownlint-cli2 "**/*.md"`
- `python -m pytest --cov=aigc --cov-report=term-missing --cov-fail-under=90`
- `python - <<'PY' ... Draft7Validator/check_schema + policy validation ... PY`
- `python -m pytest --collect-only -q | tail -n 1`
- `python -m coverage report | tail -n 2`
- `python -m build --sdist --wheel --outdir /tmp/aigc-build-rerun2`
- `python -m build --sdist --wheel --outdir /tmp/aigc-build-rerun2 --no-isolation`
- targeted `rg`, `nl`, and `sed` evidence extraction commands

## Appendix C — Open Questions / Unverified Areas
1. Should `release.yml` explicitly run audit schema `Draft7Validator.check_schema()` for exact parity with `sdk_ci.yml`?
2. Should roadmap sections that are proposal-history be moved to an archive to reduce release-contract ambiguity?
3. Should the release decision be anchored to a clean, specific commit SHA after documentation updates are finalized?
