export interface LabStep {
  title: string
  instruction: string
  tip?: string
}

export interface LabHelp {
  title: string
  overview: string
  steps: LabStep[]
  glossary?: { term: string; definition: string }[]
}

export const helpContent: Record<number, LabHelp> = {
  1: {
    title: 'Risk Scoring Guide',
    overview:
      'Explore how the aigc SDK scores invocation risk across five signal dimensions. ' +
      'Each factor contributes a weighted score. The total is compared against a configurable ' +
      'threshold — and the enforcement mode determines whether a breach blocks the call or just annotates it.',
    steps: [
      {
        title: 'Choose a preset scenario',
        instruction:
          'Select Low Risk, Medium Risk, or High Risk: Drug Interaction from the scenario panel. ' +
          'Each preset loads a different prompt and policy configuration.',
        tip: 'Start with Low Risk to see a clean baseline score of 0.00, then escalate.',
      },
      {
        title: 'Select a risk mode',
        instruction:
          'Choose strict, risk_scored, or warn_only. This controls what happens when the ' +
          'computed score exceeds the 0.70 threshold.',
        tip: 'Try the same High Risk scenario in strict mode then risk_scored — the score stays 1.00 but the result changes.',
      },
      {
        title: 'Run Enforcement',
        instruction:
          'Click Run Enforcement to evaluate the invocation. The SDK computes a score ' +
          'from five signal dimensions and compares it to the threshold.',
      },
      {
        title: 'Read the signal breakdown',
        instruction:
          'Each signal bar shows which factors fired (+contribution) and how much each added to the total. ' +
          'The result badge and message reflect the mode and whether the threshold was breached.',
        tip: 'In risk_scored mode a score above 0.70 still shows Pass — the score is recorded in the audit artifact but does not block the call.',
      },
    ],
    glossary: [
      { term: 'Risk Mode', definition: 'Controls enforcement when score exceeds threshold. strict blocks; risk_scored annotates; warn_only logs.' },
      { term: 'Risk Factor', definition: 'A named signal (e.g. no_output_schema) with a weight 0.0–1.0. When triggered, its weight adds to the total score.' },
      { term: 'Threshold', definition: 'The score ceiling. Default is 0.70. Configurable per policy.' },
      { term: 'Breach', definition: 'When the computed score exceeds the threshold. What happens next depends on the mode.' },
    ],
  },

  2: {
    title: 'Signing & Verification Guide',
    overview:
      'Learn how the aigc SDK signs and verifies audit artifacts using HMAC-SHA256. ' +
      'A valid signature proves the audit record has not been modified since it was generated. ' +
      'Use the tamper toggle to see how even a single changed byte invalidates the signature.',
    steps: [
      {
        title: 'Sign an artifact',
        instruction:
          'Click Sign Artifact. The SDK computes an HMAC-SHA256 digest of the payload ' +
          'using a secret key and attaches the hex signature.',
      },
      {
        title: 'Inspect the signed payload',
        instruction:
          'The CodeBlock shows the artifact JSON with a signature field appended. ' +
          'Copy it — this is the evidence bundle you would store for compliance.',
      },
      {
        title: 'Verify the signature',
        instruction:
          'Click Verify. The SDK recomputes the HMAC from the payload and compares it ' +
          'to the stored signature using constant-time comparison. A match produces Pass.',
      },
      {
        title: 'Test tamper detection',
        instruction:
          'Toggle Tamper to flip one byte in the payload, then click Verify again. ' +
          'The signature no longer matches — the result flips to Fail.',
        tip: 'Constant-time comparison prevents timing attacks even when the signatures differ.',
      },
    ],
    glossary: [
      { term: 'HMAC-SHA256', definition: 'A keyed hash algorithm that produces a fixed-length digest. Used here to sign audit artifacts.' },
      { term: 'Constant-time comparison', definition: 'Compares two values byte-by-byte in fixed time so attackers cannot infer information from timing differences.' },
      { term: 'Tamper detection', definition: 'Any modification to the artifact payload will cause the recomputed HMAC to differ from the stored signature.' },
    ],
  },

  3: {
    title: 'Audit Chain Guide',
    overview:
      'Discover how the SDK builds hash-linked audit chains. Each new artifact records the ' +
      'SHA-256 checksum of the previous artifact, forming a tamper-evident chain. ' +
      'Altering any past record would break every subsequent link.',
    steps: [
      {
        title: 'Link your first artifact',
        instruction:
          'Click Link Artifact to add the first record to the chain. It has no previous checksum — ' +
          'this is the genesis block.',
      },
      {
        title: 'Grow the chain',
        instruction:
          'Click Link Artifact again. Each new artifact shows its own checksum and the ' +
          "previous artifact's checksum in the prev_checksum field.",
        tip: 'Verify by eye: the prev_checksum on block N+1 matches the checksum on block N.',
      },
      {
        title: 'Inspect the chain visualization',
        instruction:
          'Each block in the chain explorer shows its index, timestamp, and first 12 characters ' +
          'of its checksum. The link arrow represents the hash pointer.',
      },
      {
        title: 'Understand the integrity guarantee',
        instruction:
          'Try modifying block 1 in your mind. Its checksum would change, which would invalidate ' +
          "block 2's prev_checksum, which invalidates block 3, and so on. " +
          'An auditor can detect tampering by recomputing any link.',
      },
    ],
    glossary: [
      { term: 'Hash pointer', definition: 'The prev_checksum field stores the SHA-256 digest of the previous artifact, linking the blocks.' },
      { term: 'Genesis block', definition: 'The first artifact in the chain, which has no previous checksum.' },
      { term: 'Tamper-evident', definition: 'Modifying any past artifact breaks all subsequent checksums, making alterations detectable.' },
    ],
  },

  4: {
    title: 'Policy Composition Guide',
    overview:
      'See how the aigc SDK merges multiple policies using composition strategies. ' +
      'A child policy can extend a base policy, inheriting and overriding fields. ' +
      'This allows shared governance baselines with per-team customisation.',
    steps: [
      {
        title: 'Review the base policy',
        instruction:
          'The left editor shows the base policy. It defines the shared governance baseline: ' +
          'roles, pre-conditions, output schema, and risk configuration.',
      },
      {
        title: 'Edit the overlay policy',
        instruction:
          'The right editor shows the child policy. It uses extends: <base> and can add, ' +
          'override, or append fields. Try changing a pre-condition or adding a role.',
      },
      {
        title: 'Choose a composition strategy',
        instruction:
          'Select merge (union of fields), override (child wins on conflict), or strict ' +
          '(child must not conflict with base). Each produces a different merged policy.',
        tip: 'strict is useful for compliance-critical policies where overrides should be rejected.',
      },
      {
        title: 'Compose and inspect the result',
        instruction:
          'Click Compose. The merged policy appears below. Each field shows whether it came ' +
          'from the base, the child, or was merged from both.',
      },
    ],
    glossary: [
      { term: 'extends', definition: 'A policy field that names the base policy to inherit from.' },
      { term: 'merge strategy', definition: 'Combines fields from base and child, concatenating lists and shallow-merging maps.' },
      { term: 'override strategy', definition: 'Child fields take precedence over base fields on any conflict.' },
      { term: 'strict strategy', definition: 'Raises an error if the child attempts to override any field already set in the base.' },
    ],
  },

  5: {
    title: 'Loaders & Versioning Guide',
    overview:
      'Explore how the aigc SDK discovers and loads policy files. Different loader strategies ' +
      'control whether policies are read from disk, environment variables, or a registry. ' +
      'The version timeline lets you trace how a policy evolved over time.',
    steps: [
      {
        title: 'Select a loader type',
        instruction:
          'Choose from the available loader types: FileLoader (reads from disk path), ' +
          'EnvLoader (reads from environment variable), or RegistryLoader (fetches from a registry URL).',
      },
      {
        title: 'Browse the version timeline',
        instruction:
          'The version timeline shows when each policy version was published. ' +
          'Select a version to preview its content.',
        tip: 'Earlier versions may be missing fields added in later schema revisions — the SDK falls back gracefully.',
      },
      {
        title: 'Load the policy',
        instruction:
          'Click Load to fetch and parse the selected version. The SDK validates it against ' +
          'the policy DSL JSON Schema and reports any validation errors.',
      },
      {
        title: 'Compare versions',
        instruction:
          'Load two different versions in sequence and observe which fields changed. ' +
          'Version diffs help auditors trace policy evolution.',
      },
    ],
    glossary: [
      { term: 'FileLoader', definition: 'Reads a YAML policy from a file path on disk. Used in local development and CI.' },
      { term: 'EnvLoader', definition: 'Reads a YAML policy from an environment variable. Used in containerised deployments.' },
      { term: 'RegistryLoader', definition: 'Fetches a policy from a remote registry URL. Used for centralised policy management.' },
      { term: 'Schema validation', definition: 'After loading, the policy is validated against policy_dsl.schema.json. Invalid policies are rejected.' },
    ],
  },

  6: {
    title: 'Custom Gates Guide',
    overview:
      'Add custom enforcement logic at four insertion points in the governance pipeline: ' +
      'pre_authorization, post_authorization, pre_output, and post_output. ' +
      'Gates can block, warn, or annotate an invocation without modifying the core SDK.',
    steps: [
      {
        title: 'Choose a gate scenario',
        instruction:
          'Select one of the pre-built gate scenarios. Each scenario loads a different ' +
          'set of custom gates targeting different pipeline phases.',
      },
      {
        title: 'Review the gate configuration',
        instruction:
          'The code panel shows the gate implementation. Each gate receives the invocation ' +
          'and context, and returns a GateResult with status and optional message.',
        tip: 'Gates run in insertion-point order: pre_authorization → post_authorization → pre_output → post_output.',
      },
      {
        title: 'Run Gates',
        instruction:
          'Click Run Gates to execute the full pipeline with the loaded gate configuration. ' +
          "Each gate's result is shown with its phase, status, and any message.",
      },
      {
        title: 'Inspect the gate results',
        instruction:
          'Each result card shows the gate name, phase, and outcome (pass/block/warn). ' +
          'A block result from any gate halts the pipeline at that point.',
      },
    ],
    glossary: [
      { term: 'EnforcementGate', definition: 'A plugin that inserts custom logic at a specific pipeline phase. Implements the GatePlugin interface.' },
      { term: 'Gate phase', definition: 'One of four pipeline insertion points: pre_authorization, post_authorization, pre_output, post_output.' },
      { term: 'GateResult', definition: 'The object returned by a gate. Contains status (pass/block/warn) and an optional message.' },
    ],
  },

  7: {
    title: 'Compliance Dashboard Guide',
    overview:
      'Browse a live audit log with filtering and export capabilities. Every aigc invocation ' +
      'produces an audit artifact — this dashboard lets you review, filter, and export ' +
      'compliance evidence for auditors and regulators.',
    steps: [
      {
        title: 'Filter the audit records',
        instruction:
          'Use the ALL, PASS, and FAIL filter buttons to narrow the visible records. ' +
          'PASS records are governance-clean invocations; FAIL records indicate a violation.',
      },
      {
        title: 'Review individual records',
        instruction:
          'Each row shows: artifact ID, timestamp, policy file, role, model provider, ' +
          'enforcement result, risk score, and signing status. ' +
          'Risk scores above 0.70 are highlighted in magenta.',
      },
      {
        title: 'Export for compliance',
        instruction:
          'Click JSON to download all visible records as a structured JSON file, ' +
          'or CSV for spreadsheet-compatible format. The export respects the active filter.',
        tip: 'Export FAIL records only to produce a targeted incident report.',
      },
      {
        title: 'Verify signing status',
        instruction:
          'The Signed column shows ✓ for artifacts that carry a valid HMAC signature. ' +
          'Unsigned artifacts (—) were produced without the signing gate enabled.',
      },
    ],
    glossary: [
      { term: 'Audit artifact', definition: 'The immutable record produced by each enforce_invocation() call. Contains input/output checksums, risk score, policy metadata, and optional signature.' },
      { term: 'Enforcement result', definition: 'The final governance decision: Pass (allowed), Fail (blocked), or Warn (allowed with warning).' },
      { term: 'Compliance evidence', definition: 'The audit log exported for external auditors. Contains the full chain of governance decisions.' },
    ],
  },
}
