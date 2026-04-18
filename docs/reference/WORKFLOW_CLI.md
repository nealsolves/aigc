# AIGC Workflow CLI Guide (v0.9.0 Beta)

> Note: `aigc workflow trace` and `aigc workflow export` are coming in a later
> release and are not yet available.

This guide covers the four CLI commands available in v0.9.0-beta:

- [`aigc policy init`](#aigc-policy-init)
- [`aigc workflow init`](#aigc-workflow-init)
- [`aigc workflow lint`](#aigc-workflow-lint)
- [`aigc workflow doctor`](#aigc-workflow-doctor)

Exit codes: `0` = success or advisory-only (no hard errors); `1` = hard errors
found (for `aigc workflow doctor` and `aigc workflow lint` only).

---

## `aigc policy init`

**Synopsis:**

```
aigc policy init [--output <path>] [--role <role>]
```

**Description:**

Generates a minimal policy YAML file at the specified path. The generated
policy is valid against the policy DSL schema and ready to use with
`enforce_invocation` or `GovernanceSession`. Use this command to bootstrap a
new standalone policy without a full workflow starter.

**Flags:**

| Flag | Default | Description |
|------|---------|-------------|
| `--output <path>` | `policy.yaml` | Output path for the generated policy file |
| `--role <role>` | `assistant` | Role to include in the policy's `roles` list |

**Examples:**

```bash
# Generate a policy file in the current directory
aigc policy init

# Generate a policy for a specific role at a custom path
aigc policy init --role analyst --output policies/analyst_policy.yaml
```

---

## `aigc workflow init`

**Synopsis:**

```
aigc workflow init --profile <profile> [--output <dir>] [--role <role>]
```

**Description:**

Generates a complete workflow starter scaffold from one of the built-in
profiles. The scaffold includes a policy file, a runnable example script, and a
README. See [STARTER_INDEX.md](STARTER_INDEX.md) for a comparison of all
profiles and [STARTER_RECIPES.md](STARTER_RECIPES.md) for per-profile recipes.

**Flags:**

| Flag | Default | Description |
|------|---------|-------------|
| `--profile <profile>` | (required) | Starter profile: `minimal`, `standard`, or `regulated-high-assurance` |
| `--output <dir>` | profile-derived name | Output directory for the generated starter |
| `--role <role>` | `assistant` | Role to use in generated policy and example code |

**Examples:**

```bash
# Generate the minimal starter (fastest path)
aigc workflow init --profile minimal

# Generate the standard starter with a custom role
aigc workflow init --profile standard --role reviewer

# Generate the regulated starter into a custom directory
aigc workflow init --profile regulated-high-assurance --output my-governed-workflow
```

---

## `aigc workflow lint`

**Synopsis:**

```
aigc workflow lint <path>
```

**Description:**

Validates a policy file or starter directory against the policy DSL schema and
known structural rules. Reports violations with their line numbers and reason
codes. Lint is non-destructive and does not modify any files.

Exit code `0` means the policy is schema-valid (advisories may still be
present). Exit code `1` means hard schema or structural errors were found that
would cause a runtime failure.

**Flags:**

| Flag | Default | Description |
|------|---------|-------------|
| `<path>` | (required) | Policy file path or starter directory to lint |

**Examples:**

```bash
# Lint a single policy file
aigc workflow lint policies/my_policy.yaml

# Lint an entire starter directory
aigc workflow lint governance/
```

---

## `aigc workflow doctor`

**Synopsis:**

```
aigc workflow doctor <starter-dir>
```

**Description:**

Inspects a generated starter directory and reports structured advisories about
policy correctness, manifest integrity, and common misconfiguration patterns.
Each advisory carries a reason code and a `next_action` message that tells you
exactly what to fix.

Exit code `0` means only advisories were found (no hard errors). Exit code `1`
means one or more hard errors were found that must be resolved before the
starter will run.

Run `doctor` after generating a starter, after editing `policy.yaml`, or any
time workflow governance raises an unexpected error.

**Flags:**

| Flag | Default | Description |
|------|---------|-------------|
| `<starter-dir>` | (required) | Path to the generated starter directory to inspect |

**Examples:**

```bash
# Run doctor on a generated starter directory
aigc workflow doctor governance/

# Run doctor after editing the regulated profile
aigc workflow doctor regulated-starter/
```

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for a full list of reason codes
and the failure-and-fix walkthrough.
