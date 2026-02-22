# ADR-0005: Allow Absolute Policy Paths in _resolve_policy_path

Date: 2026-02-17
Status: Accepted
Owners: Neal

---

## Context

`_resolve_policy_path` in `src/policy_loader.py` resolves all policy file paths
relative to `REPO_ROOT` (the AIGC SDK directory) and rejects any path — including
absolute paths — that does not reside within that directory.

This was appropriate when AIGC was used exclusively within its own repository.
However, AIGC is now installed as a library by consumer projects that
maintain their own policy files in their own repository directories.  Passing an
absolute path to a consumer-owned policy file raised `PolicyLoadError: Policy path
escapes repository root`, making cross-repo integration impossible without copying
policies into the SDK.

---

## Decision

When `policy_file` is an **absolute path**, skip the `REPO_ROOT` containment check.
The caller is explicitly providing a fully-qualified path and is responsible for its
correctness and trustworthiness.

When `policy_file` is a **relative path**, the existing REPO_ROOT containment check
is preserved: the path is resolved against `REPO_ROOT` and must remain within it.
This prevents path-traversal attacks (`../../../etc/passwd`) for relative inputs.

All other validations (file must exist, must be a file, must have `.yaml`/`.yml`
extension) apply to both absolute and relative paths.

---

## Options Considered

### Option A: Allow absolute paths (chosen)

Pros:
- Minimal change, backward compatible
- Preserves relative-path security check
- Enables legitimate consumer-project use without SDK changes to policies dir

Cons:
- Shifts responsibility for absolute-path trustworthiness to the caller

### Option B: AIGC_POLICY_ROOT environment variable

Pros:
- Security check remains in place for all paths
- Configurable without code changes

Cons:
- More invasive (env var must be set before module import)
- Couples consumer project startup sequence to AIGC internals

### Option C: Copy consumer policies into AIGC SDK policies/ directory

Pros:
- No SDK changes required

Cons:
- Couples two separate repositories
- Consumer policy files must be manually synced

---

## Consequences

- Consumer projects can pass absolute paths to their own policy files.
- The relative-path REPO_ROOT guard is unchanged.
- Existing tests (`test_load_policy_path_escape_is_blocked`) remain valid because
  they test a relative path (`../outside-policy.yaml`), which still triggers the
  containment check.
- The `test_load_policy_directory_path` test uses `patch("src.policy_loader.REPO_ROOT")`
  and passes an absolute path; it continues to work because the absolute-path branch
  still validates that the path references a file (not a directory).

---

## Contract Impact

- Enforcement pipeline impact: None (enforcement still calls `load_policy`)
- Policy DSL impact: None
- Schema impact: None
- Audit artifact impact: None
- Golden traces impact: None (golden traces use relative paths)
- Structural impact: Minimal — one conditional in `_resolve_policy_path`
- Backward compatibility: Fully backward compatible

---

## Validation

- Existing AIGC test suite (`python -m pytest`) must pass unchanged.
- Host application integration tests pass with consumer-owned absolute
  policy paths.
