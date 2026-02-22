# ADR-0004: Phase 3 Production Readiness Architecture

Date: 2026-02-16
Status: Accepted
Owners: AIGC Contributors

---

## Context

Phase 2 delivered full DSL enforcement. Phase 3 makes the SDK production-ready
for integration with async Python systems and general use.

Four features are added:

1. **Async enforcement** — async host applications (FastAPI, agentic frameworks)
   need non-blocking enforcement; synchronous `enforce_invocation()` blocks the
   event loop during policy file I/O
2. **Pluggable audit sinks** — the SDK returns audit dicts in-memory; host
   applications need persistence without writing their own plumbing
3. **Structured logging** — governance failures are silent except for
   exceptions; operators need observability
4. **Decorator pattern** — wrapping every LLM call in `enforce_invocation()`
   is verbose; a typical host application has dozens of model invocations

---

## Decision

### 3.1 Async Enforcement

Use `asyncio.to_thread()` to run `load_policy()` off the event loop.
The remaining enforcement pipeline (schema validation, dict operations)
is CPU-bound and fast; it runs synchronously within `enforce_invocation_async`.

Shared enforcement logic is extracted into `_run_pipeline(policy, invocation)`
— the async entry point calls it after awaiting policy I/O, and the sync
entry point calls it directly. No code duplication.

`enforce_invocation_async` is an `async def` in `src/enforcement.py`.
A `load_policy_async` convenience function is added to `src/policy_loader.py`.

### 3.2 Pluggable Audit Sinks

An `AuditSink` abstract base class (ABC) is defined in `src/sinks.py`.
Built-in implementations:

- `JsonFileAuditSink(path)` — appends one JSON line per audit artifact
- `CallbackAuditSink(fn)` — calls a user-provided function with the artifact

Sinks are registered via `set_audit_sink(sink)` (module-level global in
`src/sinks.py`). `emit_to_sink(artifact)` is called after generating every
audit artifact (both PASS and FAIL). Sink failures log a `WARNING` and do
not propagate — enforcement result is never affected by sink state.

**Constraint:** Sinks are synchronous. Async sink support is a future
enhancement. `CallbackAuditSink` allows callers to bridge to async
systems (e.g., enqueue to a non-blocking queue in the callback).

**Thread safety:** The module-level `_registered_sink` is not protected by
a lock. Concurrent sink registration is not a supported use case in Phase 3.
Adding a lock is a future enhancement if concurrent environments require it.

### 3.3 Structured Logging

The `aigc` package root registers `logging.NullHandler()` to suppress
"No handlers found" warnings in library use. Host applications configure
log levels and handlers.

Logger namespace: `aigc.enforcement`, `aigc.policy_loader`, `aigc.sinks`.

Log levels:
- `DEBUG`: each gate passed, policy loaded
- `INFO`: enforcement complete (PASS or FAIL summary)
- `WARNING`: sink emit failure, legacy schema fallback
- `ERROR`: enforcement exception with gate and reason

### 3.4 Decorator Pattern

`@governed(policy_file, role, model_provider, model_identifier)` wraps a
function and enforces governance around its call:

1. The decorated function is called with the original arguments
2. The enforcement invocation is assembled:
   - `input`: first positional argument
   - `context`: second positional argument or `context` keyword argument
     (defaults to `{}`)
   - `output`: function return value
3. `enforce_invocation()` (sync) or `enforce_invocation_async()` (async)
   is called based on whether the wrapped function is a coroutine
4. The original return value is returned on PASS; governance exceptions
   propagate unchanged on FAIL

Convention: the decorated function must receive its primary input dict as
the first positional argument. The `context` dict is optional (second arg
or `context` kwarg).

---

## Options Considered

### 3.1 Async: aiofiles vs asyncio.to_thread

**Option A (chosen): `asyncio.to_thread(load_policy, ...)`**
Pros: no new dependency; reuses tested sync `load_policy` exactly
Cons: policy file read runs in a thread pool (not true async I/O)

**Option B: aiofiles**
Pros: true async file I/O
Cons: adds a dependency; policy loading logic would need duplication
or awkward split (async open, sync YAML parse, sync schema validate)

Decision: Option A. The bottleneck is blocking the event loop, not raw
throughput. Thread-pool offload solves the blocking concern with no added
dependency.

### 3.2 Sinks: module-global vs instance-on-enforcer

**Option A (chosen): module-level `set_audit_sink()`**
Pros: simple; consistent with how loggers work; no refactor of existing call sites
Cons: not compatible with multiple concurrent enforcer instances

**Option B: sink as parameter to `enforce_invocation()`**
Pros: explicit; testable in isolation
Cons: breaks existing call sites; verbose; most callers use one sink

Decision: Option A. Most integrations use a single global sink. An explicit
parameter can be added later without breaking the module-level API.

### 3.4 Decorator: input/context extraction strategy

**Option A (chosen): first positional arg = input, second positional or `context` kwarg = context**
Pros: matches the common host application usage pattern; no introspection needed
Cons: implicit; breaks if function signature differs from convention

**Option B: explicit `input_key`, `context_key` decorator params**
Pros: flexible
Cons: verbose; adds complexity for a simple use case

Decision: Option A with clear documentation. The convention is stated in
the decorator's docstring. Users who need flexibility use `enforce_invocation`
directly.

---

## Consequences

- What becomes easier:
  - Async hosts can `await enforce_invocation_async(...)` without blocking the event loop
  - Audit artifacts are automatically persisted without per-call boilerplate
  - Failures are observable via standard Python logging
  - LLM call sites can use `@governed(...)` instead of inline enforcement
- What becomes harder:
  - Module-level sink state may surprise users in testing
    (mitigated: tests should call `set_audit_sink(None)` in teardown)
- Risks introduced:
  - Sink failures are silently swallowed (only logged); audit gaps possible
    if sink is broken (mitigated: WARNING log)
  - `asyncio.to_thread` adds overhead for policy loading
    (mitigated: policy loading is infrequent relative to model invocations)

---

## Contract Impact

- Enforcement pipeline impact: `_run_pipeline` extracted; async path added
- Policy DSL impact: none
- Schema impact: none
- Audit artifact impact: none (same artifact schema)
- Golden traces impact: new async golden traces use same artifact format
- Structural impact: new `src/sinks.py`, `src/decorators.py`,
  `aigc/sinks.py`, `aigc/decorators.py`
- Backward compatibility: all existing sync call sites unchanged;
  `enforce_invocation()` signature unchanged

---

## Validation

- `test_async_enforcement.py`: async PASS/FAIL paths; stable fields match sync
- `test_audit_sinks.py`: both sink types; sink failure isolation; no-sink default
- `test_decorators.py`: sync and async decorated functions; exception propagation
- All existing 107 tests continue to pass (no regressions)
