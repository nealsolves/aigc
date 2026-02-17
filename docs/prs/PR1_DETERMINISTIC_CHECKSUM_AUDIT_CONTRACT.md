# PR1: Deterministic Checksums + Audit Artifact Contract

## Summary
PR1 hardened determinism and auditability by introducing canonical JSON
serialization for checksums and formalizing the audit artifact shape with a
JSON Schema contract.

## Why This Change
- `str(sorted(obj.items()))` was not robust for nested structures.
- Audit artifacts did not have an explicit machine-validatable contract.
- Tests did not prove checksum stability across equivalent payload ordering.

## What Was Implemented

### 1) Canonical serialization utility
- Added `src/utils.py` with:
  - `canonical_json_bytes(obj) -> bytes`
  - `json.dumps(..., sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)`
  - UTF-8 encoding

### 2) Deterministic checksum implementation
- Updated `src/audit.py`:
  - `checksum()` now hashes canonical JSON bytes via SHA-256.
  - Removed stringified dict-item sorting approach.

### 3) Formal audit artifact contract
- Added `schemas/audit_artifact.schema.json` (Draft-07).
- Updated audit artifact payload in `src/audit.py` to include:
  - `audit_schema_version`
  - `policy_file`
  - `policy_schema_version`
  - `policy_version`
  - `model_provider`
  - `model_identifier`
  - `role`
  - `enforcement_result`
  - `failures` (structured list)
  - `input_checksum`
  - `output_checksum`
  - `timestamp`
  - `metadata`

### 4) Deterministic failure normalization
- Added `_normalize_failures()` in `src/audit.py`.
- Ensures consistent ordering of failure entries for deterministic artifacts.

## Test Coverage Added/Updated
- Added `tests/test_checksum_determinism.py`:
  - stable bytes for different dict insertion orders
  - nested structure checksum stability
  - SHA-256 consistency check
- Updated `tests/test_audit_artifact_contract.py`:
  - validates audit artifacts against `schemas/audit_artifact.schema.json`
  - verifies stable contract fields and deterministic failure normalization
- Updated `tests/golden_traces/golden_expected_audit.json`:
  - added stable contract fields used in golden assertions

## Files Changed (PR1 scope)
- `src/utils.py` (new)
- `src/audit.py`
- `schemas/audit_artifact.schema.json` (new)
- `tests/test_checksum_determinism.py` (new)
- `tests/test_audit_artifact_contract.py`
- `tests/golden_traces/golden_expected_audit.json`

## Behavior Impact
- Checksum output is now deterministic for semantically equivalent JSON
  mappings, including nested objects.
- Audit artifacts now conform to an explicit schema contract.
- Failure information is structured and order-stable.

## Validation Commands
```bash
python -m pytest tests/test_checksum_determinism.py tests/test_audit_artifact_contract.py
python -m pytest tests/test_golden_trace_success.py tests/test_golden_trace_failure.py
```

## Validation Status in Current Environment
- `pytest` execution may fail in constrained/offline environments where
  `pytest` is unavailable.
- Static compilation and schema checks were used as supplemental validation
  where runtime tooling was missing.
