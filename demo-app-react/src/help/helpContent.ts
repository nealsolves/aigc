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
  0: {
    title: 'Architecture Guide',
    overview:
      'The AIGC SDK sits between your app and any AI model call. Every time your code invokes a model, ' +
      'the SDK checks the invocation against a policy — before the output reaches your app — and produces ' +
      'an audit artifact regardless of outcome. Signing and chaining are opt-in utilities; they are not default behavior.',
    steps: [
      {
        title: 'Component View — what connects to what',
        instruction:
          'Your app (or an agent) calls a model through the SDK. The SDK loads your policy file, ' +
          'runs it through the enforcement core, then hands the result back to your app along with ' +
          'an audit artifact. The model provider (OpenAI, Anthropic, etc.) is called in the middle — ' +
          'the SDK wraps it, it does not replace it.',
        tip: 'The @governed decorator is post-call: the model runs first, then the SDK checks the output.',
      },
      {
        title: 'Enforcement Pipeline — the gate sequence',
        instruction:
          'Every invocation passes through a fixed sequence of gates, left to right: ' +
          'pre_authorization gates → guard evaluation → role check → precondition check → tool constraints → ' +
          'post_authorization gates → pre_output gates → schema validation → postcondition check → post_output gates → risk scoring → audit artifact. ' +
          'The gates are fail-closed — any failure stops the pipeline and produces a FAIL artifact.',
      },
      {
        title: 'Risk scoring is the last gate',
        instruction:
          'Risk scoring runs after all structural checks pass. Depending on the mode, a high score ' +
          'either blocks the call (strict), annotates the artifact (risk_scored), or just logs a warning (warn_only). ' +
          'The audit artifact is always produced — pass or fail.',
        tip: 'See Lab 1 to explore how the five risk factors combine into a score.',
      },
      {
        title: 'Key Boundaries — what is not in the pipeline',
        instruction:
          'AuditChain, the compliance export CLI, and artifact signing are all opt-in utilities ' +
          'that operate on artifacts after enforcement. They are not gates — they do not block calls. ' +
          'See the Key Boundaries section below the diagrams for the full list.',
      },
    ],
    glossary: [
      { term: 'enforce_invocation()', definition: 'The SDK entry point. Accepts a dict with policy_file, input, output, context, model_provider, model_identifier, and role.' },
      { term: 'Audit artifact', definition: 'The immutable record produced after each enforcement run. Contains checksums, risk score, policy metadata, and a PASS or FAIL result.' },
      { term: '@governed', definition: 'A decorator that wraps a function call. The model runs first; then the SDK assembles the invocation from the inputs and outputs and runs enforcement.' },
      { term: 'Fail-closed', definition: 'If any gate fails, the pipeline stops and returns FAIL. No gate is skipped on error.' },
    ],
  },

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
          'The context panel below shows the prompt, policy, model, and role that will be used — ' +
          'inspect these before running enforcement to understand why the score changes.',
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
        title: 'Generate a key and sign an artifact',
        instruction:
          'Click Generate to create a random 32-byte hex key, then click Sign Artifact. ' +
          'The SDK computes an HMAC-SHA256 digest of the artifact payload using the key and attaches the hex signature.',
      },
      {
        title: 'Inspect the signed artifact',
        instruction:
          'The signed_artifact.json CodeBlock shows the full artifact JSON with the signature field included. ' +
          'This is the evidence bundle you would store or transmit for compliance — the signature covers the entire payload.',
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
        title: 'Add your first artifact',
        instruction:
          'Click + Entry 1, + Entry 2, or + Entry 3 to add the first record to the chain. ' +
          'It has no previous checksum — this is the genesis entry, marked with a genesis badge.',
      },
      {
        title: 'Grow the chain',
        instruction:
          'Click any entry button again. Each new artifact shows its own checksum and the ' +
          "previous artifact's checksum in the previous_audit_checksum field (shown as `prev:` in the chain view).",
        tip: 'Verify by eye: the prev: on block N+1 matches the checksum on block N.',
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
          'Select intersect (only fields present in both policies), union (all fields from both, ' +
          'child wins on conflict), or replace (child policy replaces the base entirely). ' +
          'Each produces a different merged policy.',
        tip: 'intersect is useful for compliance-critical policies where only shared, agreed-upon fields should survive.',
      },
      {
        title: 'Merge and inspect the result',
        instruction:
          'Click Merge. The merged policy YAML appears below. The roles diff shows which roles ' +
          'were kept, removed, or added by the merge. The escalation panel flags any new tools ' +
          'or removed postconditions that represent a privilege escalation from base to merged policy.',
        tip: 'intersect with medical_ai_child.yaml restricts roles — no escalation. Try union to see additive behavior.',
      },
    ],
    glossary: [
      { term: 'extends', definition: 'A policy field that names the base policy to inherit from.' },
      { term: 'intersect', definition: 'Keeps only fields present in both base and child. Most restrictive — useful for compliance-critical policies.' },
      { term: 'union', definition: 'Combines all fields from base and child; child wins on conflict. Most permissive.' },
      { term: 'replace', definition: 'Child policy replaces the base entirely. Base fields not present in child are dropped.' },
    ],
  },

  5: {
    title: 'Loaders & Versioning Guide',
    overview:
      'Explore how the aigc SDK discovers and loads policy files through pluggable loader classes. ' +
      'Switch between FileSystem and InMemory loader modes, validate policy date ranges, ' +
      'and run automated policy test cases — all three capabilities make up the v0.3.0 loader story.',
    steps: [
      {
        title: 'Select a loader mode',
        instruction:
          'Choose FileSystem or InMemory at the top of the Loaders tab. ' +
          'FileSystem uses FilePolicyLoader to read a policy file from disk via the API backend. ' +
          'InMemory uses InMemoryPolicyLoader — a custom PolicyLoaderBase subclass — to parse raw YAML directly, ' +
          'with no file path required. The SDK calls loader.load() transparently in both cases.',
        tip: 'AIGC(policy_loader=InMemoryPolicyLoader(yaml_text)) is a one-line swap — the enforcement pipeline is identical.',
      },
      {
        title: 'Load or parse a policy',
        instruction:
          'In FileSystem mode, select a policy from the dropdown and click Load. ' +
          'In InMemory mode, paste or edit YAML in the textarea and click Parse. ' +
          'The parsed policy is displayed and the active loader class is shown above the result.',
      },
      {
        title: 'Validate policy dates',
        instruction:
          'Switch to the Versioning tab. Set effective_date, expiration_date, and reference_date, ' +
          'then click Validate Dates. The timeline panel shows the policy validity window with a cursor ' +
          'at the reference date. A policy outside its date range is rejected by the SDK at load time.',
        tip: 'Set reference_date to a date before effective_date to see the policy go inactive.',
      },
      {
        title: 'Run policy tests',
        instruction:
          'Switch to the Testing tab. Select a policy and click Run Tests. ' +
          'The SDK generates three test cases — valid role, unauthorized role, missing precondition — ' +
          'and reports pass or fail for each against the selected policy.',
      },
    ],
    glossary: [
      { term: 'PolicyLoaderBase', definition: 'Abstract base class for custom policy loaders. Implement load(policy_ref) to load from any source.' },
      { term: 'FilePolicyLoader', definition: 'Default loader. Reads a YAML policy from a file path on disk.' },
      { term: 'InMemoryPolicyLoader', definition: 'Demo custom loader. Holds a policy dict parsed from a raw YAML string; no filesystem access.' },
      { term: 'effective_date', definition: 'The date from which a policy becomes active. Invocations before this date are rejected.' },
      { term: 'expiration_date', definition: 'The date after which a policy becomes inactive. Invocations after this date are rejected.' },
      { term: 'Policy test case', definition: 'A deterministic invocation with a declared expected outcome (pass or fail) used to validate policy behavior.' },
    ],
  },

  6: {
    title: 'Custom Gates Guide',
    overview:
      'Add custom enforcement logic at four insertion points in the governance pipeline: ' +
      'pre_authorization, post_authorization, pre_output, and post_output. ' +
      'Gates can block or annotate an invocation without modifying the core SDK.',
    steps: [
      {
        title: 'Select a gate',
        instruction:
          'Click a gate name to load its description and insertion point. ' +
          'Gate info loads automatically — you can inspect the gate before running anything. ' +
          'The pipeline visualization highlights where in the enforcement sequence this gate runs.',
        tip: 'Gates run in insertion-point order: pre_authorization → post_authorization → pre_output → post_output.',
      },
      {
        title: 'Review gate info and pipeline position',
        instruction:
          'The gate info panel shows the gate description and its insertion_point. ' +
          'The pipeline strip highlights the active phase in the enforcement sequence. ' +
          'Click "show source" to inspect the gate implementation.',
      },
      {
        title: 'Select a scenario and run',
        instruction:
          'Choose a scenario (High Confidence, Low Confidence, PII Present, or Clean Output) ' +
          'and click Run Gate. The SDK runs full enforcement with the selected gate active at its insertion point.',
      },
      {
        title: 'Inspect gate result and artifact evidence',
        instruction:
          'The gate result shows pass or fail, any failure messages, and gate metadata. ' +
          'Below it, gates_evaluated lists the ordered gate IDs recorded in the audit artifact — ' +
          'the selected custom gate appears highlighted at its position in the sequence.',
      },
    ],
    glossary: [
      { term: 'EnforcementGate', definition: 'A plugin class that inserts custom logic at a specific pipeline phase. Extend EnforcementGate and set insertion_point.' },
      { term: 'insertion_point', definition: 'One of four pipeline phases: pre_authorization, post_authorization, pre_output, post_output.' },
      { term: 'GateResult', definition: 'Returned by a gate\'s evaluate() method. Contains passed (bool), failures list, and metadata dict.' },
      { term: 'gates_evaluated', definition: 'Ordered list of gate identifiers recorded in the audit artifact metadata. Shows which gates ran during enforcement.' },
    ],
  },

  7: {
    title: 'Compliance Dashboard Guide',
    overview:
      'Review, filter, and export audit artifacts produced during your session. ' +
      'The dashboard is backed by live session data — every enforcement run in any lab ' +
      'adds a record here. Use sample data to explore the dashboard before running labs.',
    steps: [
      {
        title: 'Build your audit log',
        instruction:
          'Run enforcement in any lab (Labs 1–6) to add records to the session audit trail. ' +
          'Records appear here automatically. If no records exist yet, click Load Sample Data ' +
          'to see an example dataset — sample mode is shown with a banner and can be cleared.',
      },
      {
        title: 'Filter records',
        instruction:
          'Use ALL, PASS, and FAIL to filter by enforcement result. ' +
          'If multiple policies appear, use the policy dropdown to narrow to a single policy file. ' +
          'Both filters apply together; exports respect the current filter state.',
      },
      {
        title: 'Inspect a record',
        instruction:
          'Click any row to expand it. Session records show full artifact detail: ' +
          'checksum, previous_audit_checksum, risk mode and threshold, gates_evaluated, and signature presence. ' +
          'Sample records show summary fields only.',
        tip: 'Risk scores above 0.70 are highlighted in magenta.',
      },
      {
        title: 'Export for compliance',
        instruction:
          'Click JSON or CSV to download the visible records. ' +
          'The equivalent CLI command is: aigc compliance export --input audit.jsonl. ' +
          'Add --output report.json --include-artifacts to include full artifact records in the report.',
      },
    ],
    glossary: [
      { term: 'Audit artifact', definition: 'The immutable record produced by each enforce_invocation() call. Contains checksums, risk score, policy metadata, and optional signature.' },
      { term: 'Enforcement result', definition: 'The final governance decision: PASS (allowed) or FAIL (blocked).' },
      { term: 'Signed (✓)', definition: 'Indicates signing was enabled for this invocation. Verification requires the original signing key.' },
      { term: 'Sample mode', definition: 'An explicit mode activated by clicking Load Sample Data. Shows fixture records with a banner; does not replace live session data.' },
    ],
  },
}
