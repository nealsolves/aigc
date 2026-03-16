# Authoritative Source Index

This document maps external authoritative artifacts referenced during
milestone audits to their status and relationship with AIGC repository
documentation.

## Purpose

Milestone release-readiness audits may reference documents that originate
outside this SDK repository. This index provides traceability between
those external artifacts and the canonical AIGC documentation set.

## External Artifacts

| Artifact | Repo Path | Status | Canonical AIGC Equivalent |
|----------|-----------|--------|---------------------------|
| `TRACE_CLAUDE.md` | [docs/reference/external/TRACE_CLAUDE.md](external/TRACE_CLAUDE.md) | Reference stub — host-application traceability document maintained outside the SDK | [docs/architecture/AIGC_HIGH_LEVEL_DESIGN.md](../architecture/AIGC_HIGH_LEVEL_DESIGN.md), [docs/INTEGRATION_GUIDE.md](../INTEGRATION_GUIDE.md) |
| `Agentic App Kit Design.txt` | [docs/reference/external/Agentic_App_Kit_Design.txt](external/Agentic_App_Kit_Design.txt) | Reference stub — original design brief pre-dating the SDK | [PROJECT.md](../../PROJECT.md) |

## How to Use This Index

- **Auditors**: use this index to confirm that every requested
  authoritative artifact is either present in the repository or
  formally mapped to its canonical AIGC equivalent.
- **Contributors**: do not modify the external reference stubs
  without updating this index.

## Canonical AIGC Documentation

The following repository-native documents are the authoritative
implementation references for the AIGC SDK:

| Document | Purpose |
|----------|---------|
| [AIGC_HIGH_LEVEL_DESIGN.md](../architecture/AIGC_HIGH_LEVEL_DESIGN.md) | Architecture design and enforcement pipeline |
| [PROJECT.md](../../PROJECT.md) | Redesign decisions, roadmap, and issue tracker |
| [PROJECT.md](../../PROJECT.md) | Authoritative structural and implementation contract |
| [INTEGRATION_GUIDE.md](../INTEGRATION_GUIDE.md) | Host system integration patterns |
| [Policy DSL Spec](../../policies/policy_dsl_spec.md) | Policy YAML format specification |
