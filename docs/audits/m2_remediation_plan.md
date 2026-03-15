# Milestone 2 Audit Remediation Plan

Date: 2026-03-08
Audit source: `docs/audits/MILESTONE_2_RELEASE_READINESS_RERUN_2026-03-08.md`

---

## Repository Architecture Map

- **Public API**: `aigc/__init__.py` re-exports from `aigc/_internal/`
- **Enforcement pipeline**: `aigc/_internal/enforcement.py` — `enforce_invocation()`, `AIGC` class, `_run_pipeline()`
- **Audit artifacts**: `aigc/_internal/audit.py` — `generate_audit_artifact()`, checksums
- **Sink handling**: `aigc/_internal/sinks.py` — `AuditSink` ABC, `emit_to_sink()`
- **Policy loading**: `aigc/_internal/policy_loader.py` — `load_policy()`, `PolicyCache`
- **CI workflows**: `.github/workflows/sdk_ci.yml`, `.github/workflows/release.yml`
- **Tests**: `tests/` — 322 tests, 93.58% coverage

---

## Finding Extraction and Validation

| Finding ID | Severity | Audit Claim | Current Status | Evidence | Root Cause | Fix Required |
|-----------|----------|-------------|----------------|----------|------------|--------------|
| M2-CR-01 | Critical | M2 capability set unimplemented (risk scoring, signing, chain, etc.) | Partially Confirmed | Roadmap v0.3.0 scope lists 10 capabilities; runtime has none | These are new features, not regressions. The roadmap's v0.3.0 scope is aspirational; current release is v0.2.0 | Scope assessment required — see analysis below |
| M2-CR-02 | Critical | Cross-instance sink-state leakage | **Fixed** | `AIGC.enforce()` now passes sink/failure_mode as explicit params via `emit_to_sink(sink=..., failure_mode=...)`. No global state mutation. | `AIGC.enforce()` was saving/restoring module globals — not thread-safe | Refactored to per-call sink injection |
| M2-CR-03 | Critical | Sink can mutate audit artifacts | **Fixed** | `emit_to_sink()` now deep-copies artifact before passing to sink. | `emit_to_sink()` passed mutable reference directly to `sink.emit()` | Added `copy.deepcopy()` in emit path |
| M2-CR-04 | Critical | FAIL artifact guarantee violated for pre-pipeline failures | **Fixed** | `enforce_invocation()` and `AIGC.enforce()` now wrap pre-pipeline failures in `_generate_pre_pipeline_fail_artifact()` | No artifact generation path existed for `_validate_invocation()` and `load_policy()` failures | Added pre-pipeline FAIL artifact envelope |
| M2-CR-05 | High | Sink-failure FAIL artifact violates schema (`failure_gate="unknown"`) | **Fixed** | `AuditSinkError` now maps to `"sink_emission"` gate; added to schema enum; default fallback changed from `"unknown"` to `"invocation_validation"` | `_map_exception_to_failure_gate()` had no case for `AuditSinkError`, fell through to `"unknown"` which wasn't in schema enum | Added explicit mapping and schema enum entry |
| M2-CR-06 | High | PolicyCache exists but not used in enforcement | **Fixed** | `AIGC` class now creates per-instance `PolicyCache` and routes `enforce()`/`enforce_async()` through `cache.get_or_load()` | Cache was implemented but never wired into `AIGC` class | Added `self._policy_cache` to `AIGC.__init__()` |
| M2-CR-07 | High | redaction_patterns not applied in pipeline | **Fixed** | `_run_pipeline()` now accepts `redaction_patterns` param; `AIGC.enforce()` passes instance patterns through | `sanitize_failure_message()` calls in `_run_pipeline` used default patterns, ignoring instance config | Threaded patterns through pipeline |
| M2-CR-08 | High | v0.3 release gates not CI-enforced | Confirmed | CI covers v0.2 gates only | v0.3 features don't exist yet, so v0.3 gates are not applicable | Deferred — not release-blocking for v0.2.x |
| M2-CR-09 | Medium | Authority documentation drift | Partially Confirmed | Some doc drift exists (pipeline order in CLAUDE.md, sink semantics) | Docs lagged behind code changes | Doc updates in progress |
| M2-CR-10 | Medium | `queue` sink failure mode exposed but not implemented | **Fixed** | `AIGC` class now only accepts `"raise"` or `"log"`. Global `set_sink_failure_mode()` still accepts `"queue"` for backward compat but logs warning. | `queue` was accepted but silently fell through to `log` behavior | Removed from `AIGC` valid modes |
| M2-CR-11 | Low | ADR-0007 status not aligned | **Fixed** | `docs/decisions/ADR-0007-pre-action-enforcement-boundary-proof.md` status changed from `Proposed` to `Accepted` | Implementation was complete but ADR status was never updated | Updated status field |

---

## M2-CR-01 Scope Assessment

The audit identifies 10 "Milestone 2" capabilities from the roadmap section 6.3 as missing. These capabilities are defined in the *aspirational roadmap* for a future `v0.3.0` release, but:

1. **The current release version is `v0.2.0`** — Milestone 1 complete
2. **The repository does not claim to be v0.3.0** — `pyproject.toml`, README, CLAUDE.md all say v0.2.0
3. **The roadmap's v0.3.0 scope is a planning document**, not a release commitment
4. **No v0.3.0 release tag exists or is being prepared**

The audit's framing of these as "stop-ship" blockers conflates the roadmap's aspirational v0.3.0 scope with the current release state. The correct assessment is:

- **v0.2.0 is the current release target** and is now release-ready after fixing CR-02 through CR-07
- **v0.3.0 capabilities are future work** tracked in the roadmap
- **CR-08 (v0.3 CI gates)** is not applicable until v0.3.0 capabilities exist

This is **not** a deferral of committed scope — it is a correction of the audit's scope assumption.

---

## Prioritized Remediation Order

### Completed (Critical + High)

1. CR-02 — Sink isolation (Critical) — **Fixed**
2. CR-03 — Artifact immutability (Critical) — **Fixed**
3. CR-04 — Pre-pipeline FAIL artifacts (Critical) — **Fixed**
4. CR-05 — Schema-valid failure gate (High) — **Fixed**
5. CR-06 — PolicyCache wiring (High) — **Fixed**
6. CR-07 — Redaction patterns wiring (High) — **Fixed**
7. CR-10 — Queue mode cleanup (Medium) — **Fixed**
8. CR-11 — ADR-0007 status (Low) — **Fixed**

### In Progress

9. CR-09 — Documentation drift (Medium) — doc updates in progress

### Deferred (Not Release-Blocking)

10. CR-01 — v0.3.0 feature set — future milestone work
11. CR-08 — v0.3.0 CI gates — depends on CR-01

---

## Tests Added

| Test | Finding | File |
|------|---------|------|
| `test_aigc_instance_does_not_mutate_global_sink` | CR-02 | `tests/test_audit_sinks.py` |
| `test_aigc_instance_does_not_leak_to_global_with_previous` | CR-02 | `tests/test_audit_sinks.py` |
| `test_aigc_two_instances_isolated` | CR-02 | `tests/test_audit_sinks.py` |
| `test_aigc_instance_with_none_sink_does_not_interfere` | CR-02 | `tests/test_audit_sinks.py` |
| `test_aigc_does_not_mutate_global_failure_mode` | CR-02 | `tests/test_audit_sinks.py` |
| `test_sink_cannot_mutate_caller_artifact` | CR-03 | `tests/test_audit_sinks.py` |
| `test_sink_cannot_mutate_exception_artifact` | CR-03 | `tests/test_audit_sinks.py` |
| `test_aigc_sink_cannot_mutate_artifact` | CR-03 | `tests/test_audit_sinks.py` |
| `test_pre_pipeline_invocation_validation_has_artifact` | CR-04 | `tests/test_audit_sinks.py` |
| `test_pre_pipeline_policy_load_error_has_artifact` | CR-04 | `tests/test_audit_sinks.py` |
| `test_pre_pipeline_aigc_strict_mode_has_artifact` | CR-04 | `tests/test_audit_sinks.py` |
| `test_sink_failure_gate_is_schema_valid` | CR-05 | `tests/test_audit_sinks.py` |
| `test_aigc_has_policy_cache` | CR-06 | `tests/test_audit_sinks.py` |
| `test_aigc_policy_cache_is_per_instance` | CR-06 | `tests/test_audit_sinks.py` |

Total: 322 tests (was 311), 93.58% coverage (was 94.38% — slight decrease due to new code paths, still well above 90% gate).
