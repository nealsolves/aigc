# Pull Request Template — AIGC Governance SDK

## Summary

Describe the change clearly and concretely.

## Why

What problem does this solve? What governance or architectural risk does it address?

## Scope

- [ ] Code change
- [ ] Policy DSL semantics change
- [ ] Schema change
- [ ] Audit artifact contract change
- [ ] Golden replays change
- [ ] Documentation change
- [ ] Directory structure change

## Structural Parity (Required for Directory Changes)

If this PR creates, removes, or reorganizes directories:

- [ ] `PROJECT.md` updated first (authoritative structural contract)
- [ ] Decision record added in `docs/decisions/`
- [ ] Imports and tests updated

## Governance Hard Gates

- [ ] All enforcement flows through `enforce_invocation()`
- [ ] Policy validation fails closed
- [ ] Determinism preserved or explicitly normalized
- [ ] Typed error taxonomy preserved

## Golden Replays

- [ ] `python -m pytest` passes
- [ ] Success and failure replays updated if behavior changed
- [ ] Stable audit fields asserted
- [ ] Rationale documented if expected outputs changed

## Documentation and Schema Parity

- [ ] `PROJECT.md` updated if architecture changed
- [ ] Policy DSL spec updated if semantics changed
- [ ] JSON schemas updated if structure changed
- [ ] Tests updated to reflect contract changes

## Decision Record (Required When Applicable)

If this PR changes:

- Enforcement order
- Policy semantics
- Determinism rules
- Error taxonomy
- Structural architecture
- Golden replay meaning

Then include:

Decision record file: `docs/decisions/ADR-XXXX-<slug>.md`

## Reviewer Notes

Call out edge cases, compatibility risks, or migration considerations.
