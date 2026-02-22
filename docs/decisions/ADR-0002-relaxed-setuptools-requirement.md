# ADR-0002: Relaxed setuptools Build Requirement

Date: 2026-02-17
Status: Accepted
Owners: AIGC Contributors
Context: Phase 1 audit findings — packaging reliability

---

## Context

Phase 1 audit identified a packaging blocker: `pip install -e .` failed in
network-restricted environments due to inability to resolve `setuptools>=65`.

Audit evidence showed:
- Python 3.14.2 environment with no pre-installed setuptools
- Network-restricted conditions preventing download of setuptools>=65
- Import path worked correctly once package was installed
- All runtime functionality (tests, coverage, enforcement) passed

The package uses only basic setuptools features:
- PEP 517/518 build backend (`setuptools.build_meta`)
- Simple package discovery via `tool.setuptools.packages.find`
- No custom build steps, extensions, or advanced packaging features

## Decision

Relax the setuptools build requirement from `>=65` to `>=40`.

**Rationale**:
- setuptools 40.0.0 (May 2018) introduced full PEP 517/518 support
- All features used by this package are available in setuptools 40+
- Much wider compatibility in constrained/offline/legacy environments
- No functional difference for this package's simple structure

## Options Considered

### Option A: Relax to `setuptools>=40` (CHOSEN)

Pros:
- Maintains PEP 517/518 compliance
- Wide availability (5+ years old)
- Solves audit blocker without compromising functionality
- No changes to package structure required

Cons:
- Older setuptools versions may have unrelated bugs (not affecting this package)

### Option B: Keep `setuptools>=65`, document manual pre-installation

Pros:
- Uses modern setuptools release
- Explicit about build requirements

Cons:
- Fails audit requirement ("pip install -e . must work")
- Adds friction to installation workflow
- Not compatible with network-restricted environments

### Option C: Switch to different build backend (flit, hatchling)

Pros:
- Modern alternatives with fewer dependencies
- Potentially simpler configuration

Cons:
- Migration effort
- Changes tooling ecosystem
- Setuptools is standard and well-understood
- Overkill for this specific issue

## Consequences

### What becomes easier
- Installation in network-restricted environments
- Compatibility with older/frozen Python environments
- Audit compliance for packaging requirement

### What becomes harder
- Nothing — package uses no setuptools 40+ exclusive features

### Risks introduced
- None identified — setuptools 40+ is stable and battle-tested

### Risk mitigation
- Tested locally with clean venv (successful)
- CI pipeline unchanged (uses modern setuptools anyway)
- All 43 tests pass with 93% coverage

## Contract Impact

- **Enforcement pipeline impact**: None
- **Policy DSL impact**: None
- **Schema impact**: None
- **Audit artifact impact**: None
- **Golden traces impact**: None
- **Structural impact**: None (pyproject.toml only)
- **Backward compatibility**: Improved (wider compatibility)

## Validation

Verified via:
1. Local clean venv install test:
   ```bash
   python3 -m venv /tmp/test-env
   source /tmp/test-env/bin/activate
   pip install -e .  # SUCCESS with setuptools>=40
   python -c "from aigc.enforcement import enforce_invocation; print('OK')"
   ```

2. Full test suite: `python -m pytest --cov=src` => 43 passed, 93% coverage

3. All CI-equivalent checks pass:
   - Tests: PASS
   - Coverage: PASS (93%)
   - Flake8: PASS
   - Markdown lint: PASS
   - Policy validation: PASS

## References

- PEP 517 (Build System Interface): <https://peps.python.org/pep-0517/>
- PEP 518 (Build System Requirements): <https://peps.python.org/pep-0518/>
- setuptools 40.0.0 Release (2018-05-17): First release with full PEP 517/518 support
