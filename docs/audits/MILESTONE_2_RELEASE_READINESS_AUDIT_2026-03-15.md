# AIGC Milestone 2 / Release 0.3.0 Readiness Audit

Date: 2026-03-15  
Auditor: Codex (Principal Software Architect / Release Readiness Auditor)  
Repository: `/Users/neal/Documents/_Shenanigans/_myProjects/aigc`

## 1. Executive Summary

**FAIL**

The branch is not release-ready for Milestone 2 / v0.3.0 merge into `develop`.  
Core health is strong (`464` tests passing, `93.71%` coverage, `flake8` pass, doc parity pass),
but merge-blocking issues remain: custom gate mutability allows policy tampering and authorization bypass,
pre-pipeline FAIL artifacts are schema-invalid, advertised pluggable `policy_loader` is not wired in runtime enforcement,
and markdown-lint CI currently fails on repository contents.

## 2. Review Scope

- Repository path reviewed: `/Users/neal/Documents/_Shenanigans/_myProjects/aigc`
- Branch reviewed: `docs/milestone1-parity-fixes`
- Git status: branch tracks `origin/docs/milestone1-parity-fixes`; uncommitted `demo-app/` present
- `develop` comparison: available locally and reviewed (`git diff develop...HEAD`)
- Branch delta reviewed: `123 files changed, 15136 insertions(+), 400 deletions(-)`
- Requested docs unavailable: `TRACE_CLAUDE.md`, `Agentic App Kit Design.txt`

Commands run successfully:

```bash
pwd
git status --short --branch
git branch --show-current
git branch
git diff --stat develop...HEAD
git diff --name-status develop...HEAD
python scripts/check_doc_parity.py
python -m pytest --cov=aigc --cov-report=term-missing --cov-fail-under=90
flake8 aigc
python <policy/audit schema + policy validation snippet>
```

Commands that failed:

```bash
npx markdownlint-cli2 "**/*.md"   # 157 errors
```

## 3. Architecture Compliance Matrix

| Area | Expected | Observed | Status | Notes |
|---|---|---|---|---|
| Public API boundary | Public API in `aigc/`, implementation in `aigc/_internal/` | Thin public wrappers, core logic in `_internal` | Pass | Boundary structure preserved |
| Enforcement centralization | Governance routed through enforcement entrypoints | Centralized, but mutable custom gates can alter policy pre-authorization | Fail | Boundary bypass risk |
| Pipeline ordering | Guard → role → preconditions → tools → schema → postconditions | Implemented in expected order | Pass | Tool-before-schema preserved |
| Fail artifact contract | Every failure emits schema-valid FAIL artifact | Pre-pipeline FAIL artifact has `policy_version: null` | Fail | Contract violation |
| Deterministic behavior | Deterministic decisions for same policy/invocation/context | Core decisions deterministic; timestamp remains volatile by design | Partial | Docs overstate full artifact identity in some places |
| Policy-driven governance | Rules originate from policy and controlled pipeline | Core is policy-driven; plugin mutability can rewrite policy at runtime | Partial | Security invariant weakened |
| Pluggable policy loader | `AIGC(policy_loader=...)` functional in runtime path | Parameter accepted but unused in `enforce()`/`enforce_async()` | Fail | Feature incomplete |
| CI readiness | pytest/coverage/flake8/markdown/schema gates pass | pytest/coverage/flake8/schema pass; markdown fails | Fail | Merge-gate risk |
| Docs parity | Authoritative docs match runtime behavior | Multiple architecture docs stale vs M2 implementation | Partial | Documentation drift |

## 4. Findings by Severity

### Critical

1. Custom gate can mutate policy and bypass role enforcement  
Severity: Critical  
Affected files: `aigc/_internal/gates.py`, `aigc/_internal/enforcement.py`  
Exact issue: Plugin contract says invocation/policy are read-only, but mutable objects are passed directly to `gate.evaluate()`. A pre-authorization gate can modify `policy["roles"]` before role validation.  
Why it matters: This creates a direct governance bypass path and violates invocation boundary/threat model assumptions.  
Recommended fix: Pass immutable views (or deep-copied read-only structures) to gates and add regression tests proving mutation attempts cannot alter authorization outcomes.  
Blocks merge: Yes

2. Pre-pipeline FAIL artifacts are schema-invalid  
Severity: Critical  
Affected files: `schemas/audit_artifact.schema.json`, `aigc/_internal/audit.py`, `aigc/_internal/enforcement.py`  
Exact issue: Schema requires `policy_version` as string; pre-pipeline path generates artifact with empty policy dict, producing `policy_version = null`.  
Why it matters: Violates audit artifact contract and “every enforcement attempt produces valid artifact” invariant on early failures.  
Recommended fix: Emit schema-valid placeholder `policy_version` for pre-pipeline artifacts (or formally update schema + ADR), and add tests validating pre-pipeline artifacts against schema.  
Blocks merge: Yes

### High

1. Pluggable `PolicyLoader` is not wired into `AIGC` runtime  
Severity: High  
Affected files: `aigc/_internal/enforcement.py`, `tests/test_pluggable_loader.py`  
Exact issue: `AIGC.__init__` accepts `policy_loader`, but enforcement uses `PolicyCache.get_or_load()` with filesystem loader path; tests only assert parameter acceptance.  
Why it matters: Advertised M2 capability does not function for real enforcement.  
Recommended fix: Wire custom loader through runtime load/cache path and add end-to-end tests using non-filesystem refs.  
Blocks merge: Yes

2. Custom gate metadata is dropped  
Severity: High  
Affected files: `aigc/_internal/gates.py`, `aigc/_internal/enforcement.py`  
Exact issue: `run_gates()` returns metadata, `_run_pipeline()` captures `custom_meta` but never merges it into artifact metadata.  
Why it matters: Plugin contract and forensic metadata guarantees are incomplete.  
Recommended fix: Deterministically merge namespaced custom metadata and add assertions in custom-gate integration tests.  
Blocks merge: Yes

3. Custom gate failures are misclassified as `postcondition_validation`  
Severity: High  
Affected files: `aigc/_internal/enforcement.py`  
Exact issue: Custom gate failures raise `GovernanceViolationError`; mapper falls back to role/postcondition inference by string check.  
Why it matters: Audit failure gate becomes inaccurate, degrading forensic and compliance reporting.  
Recommended fix: Introduce explicit custom-gate failure mapping (new exception type or explicit gate IDs) and align schema/docs/tests.  
Blocks merge: Yes

4. Markdown lint release gate currently fails  
Severity: High  
Affected files: `.github/workflows/sdk_ci.yml`, `.markdownlint-cli2.yaml`  
Exact issue: CI lints `**/*.md` but ignore list does not exclude `.claude/skills/**`; current run reports `157` errors.  
Why it matters: CI release gate reliability is broken on current branch contents.  
Recommended fix: Scope markdown lint to project docs or expand ignore rules for non-release skill content.  
Blocks merge: Yes

### Medium

1. Documentation drift in architecture/threat/invariant docs  
Severity: Medium  
Affected files: `docs/architecture/ARCHITECTURAL_INVARIANTS.md`, `docs/architecture/ENFORCEMENT_PIPELINE.md`, `docs/architecture/AIGC_THREAT_MODEL.md`  
Exact issue: Docs still describe several M2 capabilities as planned/placeholders despite runtime/schema implementation (risk/signing/chaining/composition/custom gates).  
Why it matters: Conflicting “authoritative” guidance increases integration/audit risk.  
Recommended fix: Reconcile these docs to v0.3.0 behavior and clearly label roadmap/proposed content.  
Blocks merge: No

2. Changelog parity gap for v0.3.0  
Severity: Medium  
Affected files: `pyproject.toml`, `CHANGELOG.md`  
Exact issue: Package version is `0.3.0`, but latest changelog section is `0.2.0`.  
Why it matters: Release traceability and consumer communication are incomplete.  
Recommended fix: Add complete `0.3.0` changelog section before release.  
Blocks merge: No (release blocker)

3. Missing requested audit source docs  
Severity: Medium  
Affected files: Missing (`TRACE_CLAUDE.md`, `Agentic App Kit Design.txt`)  
Exact issue: Requested authoritative references were not present in repo.  
Why it matters: Full requested source-of-truth validation could not be completed.  
Recommended fix: Add missing docs or update canonical reference list to current files.  
Blocks merge: No

### Low

1. Dirty working tree at audit time  
Severity: Low  
Affected files: Untracked `demo-app/`  
Exact issue: Working tree is not clean during readiness evaluation.  
Why it matters: Can create ambiguity in release gating and diffs.  
Recommended fix: Commit/stash/ignore before merge-gate execution.  
Blocks merge: No

## 5. Invariant Compliance

- Invocation Boundary: **Fail**  
Custom gate mutability allows pre-authorization policy tampering.

- Fail-Closed Governance: **Partial**  
Core fail-closed behavior works, but plugin mutability creates bypass risk.

- Deterministic Governance: **Partial**  
Core decisions deterministic; volatile timestamp expected; docs need precision.

- Audit Artifact Guarantee: **Fail**  
Artifacts are produced on all paths, but pre-pipeline artifacts are not schema-valid.

- Policy-Driven Governance: **Partial**  
Core path is policy-driven; mutable plugin hook can alter effective policy.

- Golden Replay Contract: **Partial**  
Strong replay coverage exists, but key regressions (plugin immutability, pre-pipeline schema validity, loader wiring) are not covered.

## 6. Documentation Parity Findings

- Runtime vs docs drift:
  - Custom gates listed as planned in some architecture docs but implemented.
  - Risk/signature/chaining/composition listed as planned/placeholders in some docs but implemented in schema/runtime.
- Terminology drift:
  - `metadata.gates_evaluated` uses `tool_constraint_validation` while several docs show `tool_validation`.
- Release docs drift:
  - `CHANGELOG.md` missing `0.3.0` section.
- Requested-doc availability drift:
  - `TRACE_CLAUDE.md` and `Agentic App Kit Design.txt` missing.

## 7. Test and CI Assessment

- Test status: **PASS** (`464 passed`)
- Coverage status: **PASS** (`93.71%`, threshold `>=90%`)
- Lint status:
  - `flake8`: **PASS**
  - `check_doc_parity.py`: **PASS**
  - `markdownlint-cli2`: **FAIL** (`157` errors)
- Schema validation status: **PASS** (policy + audit schema checks and policy file validation)
- CI risk status: **High**

Missing/weak release gates:

1. No CI test proving custom gates cannot mutate invocation/policy.  
2. No CI test validating pre-pipeline FAIL artifacts against audit schema.  
3. No CI test proving `AIGC(policy_loader=...)` is used at runtime.

## 8. Release Decision

**BLOCKED — MAJOR ISSUES**

## 9. Required Fixes Before Merge

1. Enforce immutability for custom gate inputs and add anti-bypass regression tests.  
2. Make pre-pipeline FAIL artifacts schema-valid and test them against `schemas/audit_artifact.schema.json`.  
3. Wire custom `policy_loader` into `AIGC.enforce()` / `AIGC.enforce_async()` runtime path and strengthen tests.  
4. Preserve custom gate metadata in audit artifacts and correct custom gate failure-gate mapping.  
5. Fix markdown lint gate scope/config so CI is green on intended content.  
6. Update authoritative architecture/threat/invariant docs to reflect actual v0.3.0 implementation; add `CHANGELOG` entry for `0.3.0`.
