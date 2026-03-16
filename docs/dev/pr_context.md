# PR Context: v0.3.0 Safe Remediation Pass After Audit Rerun

## Summary

Normalize authoritative documentation and demo-app boundaries to match
shipped v0.3.0 (M2) runtime behavior. No governance runtime changes.

## Why

The M2 release readiness audit rerun (2026-03-15) found that core runtime
enforcement is healthy, but several authoritative docs still describe
shipped features as "planned" or "placeholder." Demo labs imported private
`_internal` modules. These issues reduce audit trace completeness and
teach incorrect integration patterns.

## Scope

- [x] Documentation change
- [x] Code change (demo lab imports, public re-export additions, docstrings)

## Governance Hard Gates

- [x] All enforcement flows through `enforce_invocation()`
- [x] Policy validation fails closed
- [x] Determinism preserved or explicitly normalized
- [x] Typed error taxonomy preserved

## Golden Replays

- [x] `python -m pytest` passes (542 tests, 94.28% coverage)
- [x] No behavior change; golden replays unchanged

## Documentation and Schema Parity

- [x] `PROJECT.md` updated (stale placeholder text, missing-doc traceability)
- [x] Architecture docs normalized to v0.3.0
- [x] Doc parity checker passes
- [x] Markdown lint passes

## Decision Record

Not required. No enforcement order, policy semantics, determinism rules,
error taxonomy, or structural architecture changes were made.
