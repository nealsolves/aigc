export interface LabStep {
  title: string
  instruction: string
  tip?: string
}

export interface LabHelp {
  title: string
  overview: string
  whyItMatters: string
  whatThisLabShows: string[]
  howToNavigate: string[]
  steps: LabStep[]
  takeaway: string
  glossary?: { term: string; definition: string }[]
}

export const helpContent: Record<number, LabHelp> = {
  0: {
    title: 'Architecture Guide',
    overview:
      'If you are new to AIGC, start here. AIGC is a runtime governance layer that sits between ' +
      'your application and an AI model call. It checks each invocation against policy, emits an ' +
      'audit artifact on pass or fail, and leaves opt-in utilities like signing, chaining, and ' +
      'compliance export outside the core enforcement path.',
    whyItMatters:
      'Most teams treat AI governance as documentation or prompt advice. AIGC turns it into a ' +
      'deterministic control plane: policy is declared up front, enforcement is fail-closed, and ' +
      'evidence is generated every time.',
    whatThisLabShows: [
      'Where the host app, model provider, policy layer, and SDK enforcement core sit at runtime.',
      'Which checks belong to the core fail-closed pipeline and which capabilities are opt-in utilities.',
      'How split enforcement (the default since v0.3.3) and legacy unified mode share the same ordered gates.',
      'Why AIGC is provider-agnostic: it wraps model calls instead of replacing the model itself.',
    ],
    howToNavigate: [
      'Read Component View first to see where AIGC sits in the call path.',
      'Move to Enforcement Pipeline next to understand the exact gate order.',
      'Use Key Boundaries to separate core enforcement from signing, AuditChain, and compliance export.',
      'Then open Labs 1-7 to study one capability at a time.',
    ],
    steps: [
      {
        title: 'Component View - what connects to what',
        instruction:
          'Your app, agent, or orchestrator calls a model through the SDK. The SDK loads the policy, ' +
          'runs the enforcement core, then returns the governance result and audit artifact to your app. ' +
          'The model provider still does the generation in the middle; AIGC governs the call boundary around it.',
        tip: 'Since v0.3.3, @governed defaults to split enforcement (Phase A before the model call, Phase B after). Pass pre_call_enforcement=False for legacy unified mode (deprecated).',
      },
      {
        title: 'Enforcement Pipeline - the gate sequence',
        instruction:
          'Every invocation passes through a fixed sequence of gates: pre_authorization gates -> guard evaluation -> ' +
          'role check -> precondition check -> tool constraints -> post_authorization gates -> pre_output gates -> ' +
          'schema validation -> postcondition check -> post_output gates -> risk scoring -> audit artifact emission. ' +
          'The core gates are fail-closed: a violation stops the pipeline and produces a FAIL artifact.',
      },
      {
        title: 'Phase boundary in v0.3.3',
        instruction:
          'Split mode moves the model-call boundary between post_authorization and pre_output. ' +
          'Phase A is authorize-before-call; Phase B is validate-after-output. Unified mode still uses the same gate order, but inside one enforcement call.',
        tip: 'Look for Phase A / Phase B labeling on the pipeline view when you want to reason about token-spend avoidance.',
      },
      {
        title: 'Risk scoring is the last gate',
        instruction:
          'Risk scoring runs only after the structural checks pass. Depending on the configured mode, a high score ' +
          'blocks the call (strict), records the score without blocking (risk_scored), or records a warning (warn_only).',
        tip: 'Lab 1 shows that the score can stay the same while the enforcement outcome changes by mode.',
      },
      {
        title: 'Key Boundaries - what is not in the pipeline',
        instruction:
          'AuditChain, artifact signing, and the compliance export CLI all operate on artifacts after enforcement. ' +
          'They are important integrity and reporting tools, but they are not runtime gates and do not decide whether a call is allowed.',
      },
    ],
    takeaway:
      'AIGC is not another model. It is a deterministic governance wrapper that makes AI invocation rules enforceable and auditable.',
    glossary: [
      { term: 'enforce_invocation()', definition: 'The SDK entry point. Accepts policy, input, output, context, model identity, and role, then returns an audit artifact or raises with one attached.' },
      { term: 'enforce_pre_call()', definition: 'The split-mode Phase A entry point. It authorizes the invocation before the model call and returns a PreCallResult token for Phase B.' },
      { term: 'Audit artifact', definition: 'The immutable record produced after each enforcement run. It contains checksums, policy metadata, result, and supporting evidence.' },
      { term: '@governed', definition: 'A decorator that defaults to split enforcement since v0.3.3 (Phase A before the model call, Phase B after). Pass pre_call_enforcement=False for legacy unified mode (deprecated).' },
      { term: 'Fail-closed', definition: 'If a core governance check fails, the invocation is rejected and a FAIL artifact is emitted. The system does not silently continue.' },
    ],
  },

  1: {
    title: 'Risk Scoring Guide',
    overview:
      'This lab introduces one of AIGC\'s judgment surfaces: quantified invocation risk. It shows how the SDK ' +
      'turns a fuzzy question like "is this call risky?" into an explicit score, threshold, and enforcement outcome.',
    whyItMatters:
      'Risk scoring gives operators a controlled way to treat borderline AI behavior differently without weakening the ' +
      'core policy gates. The score is deterministic, explainable, and captured in the audit artifact.',
    whatThisLabShows: [
      'Five named risk signals contribute weighted evidence to one final score.',
      'The same score can lead to different outcomes depending on strict, risk_scored, or warn_only mode.',
      'Risk scoring happens after the structural policy checks, so it complements core enforcement instead of replacing it.',
      'Unified and split enforcement can evaluate the same scenario differently when Phase A blocks before the model call.',
    ],
    howToNavigate: [
      'Start with Low Risk to establish the baseline, then move to Medium Risk and High Risk.',
      'Keep one scenario fixed and switch modes to see how policy treatment changes at the same threshold.',
      'Use the Enforcement Flow control to compare unified vs split behavior on the same invocation.',
      'Read the score, status badge, threshold, and signal bars together rather than in isolation.',
      'Use the scenario context panel to connect the score back to prompt, policy, model, role, and boolean context flags.',
    ],
    steps: [
      {
        title: 'Choose a preset scenario',
        instruction:
          'Select Low Risk, Medium Risk, or High Risk: Drug Interaction from the scenario panel. ' +
          'The context panel below shows the prompt, policy, model, and role used for that run.',
        tip: 'Start with Low Risk to see a clean baseline score of 0.00, then escalate.',
      },
      {
        title: 'Select a risk mode',
        instruction:
          'Choose strict, risk_scored, or warn_only. This controls what happens when the computed score exceeds the 0.70 threshold.',
        tip: 'Try the same High Risk scenario in strict mode and then in risk_scored mode. The score can stay 1.00 while the decision changes.',
      },
      {
        title: 'Compare unified and split flow',
        instruction:
          'Choose Unified to run one enforcement call with output already present, or Split to run Phase A before the model call and Phase B after output exists. The split metadata shows which gates ran in each phase.',
        tip: 'Use the Split Demo: Missing Role Declaration scenario with Split flow to see a Phase A block before any model output is consumed.',
      },
      {
        title: 'Run Enforcement',
        instruction:
          'Click Run Enforcement to evaluate the invocation. The SDK computes the total from the configured signal weights and compares it to the threshold.',
      },
      {
        title: 'Read the signal breakdown',
        instruction:
          'Each signal bar shows which factor fired and how much it contributed. The result badge and message show whether the invocation passed, failed, or passed with risk recorded.',
        tip: 'In risk_scored mode a score above 0.70 still shows Pass because the score is audited without blocking the call.',
      },
    ],
    takeaway:
      'AIGC turns "this feels risky" into a deterministic, inspectable score tied to an explicit enforcement policy.',
    glossary: [
      { term: 'Risk Mode', definition: 'Controls what happens when score exceeds threshold. strict blocks; risk_scored records the exceedance without blocking; warn_only records a warning without blocking.' },
      { term: 'Risk Factor', definition: 'A named signal such as no_output_schema or missing_guards with a configured weight. Triggered factors add to the total score.' },
      { term: 'Threshold', definition: 'The score ceiling. In this lab the API sets it to 0.70.' },
      { term: 'Breach', definition: 'When the computed score exceeds the threshold. The follow-on action depends on risk mode.' },
    ],
  },

  2: {
    title: 'Signing & Verification Guide',
    overview:
      'This lab shows how AIGC can add cryptographic integrity to audit artifacts. Enforcement still happens first; signing is an ' +
      'opt-in step that lets you prove the stored artifact has not changed since it was produced.',
    whyItMatters:
      'Governance evidence is only useful if you can trust the record. Signing makes an audit artifact portable and tamper-evident when it leaves the process that created it.',
    whatThisLabShows: [
      'AIGC can sign artifacts with HMAC-SHA256 when a signer is configured.',
      'Verification is a separate action from enforcement and requires the original signing key.',
      'A one-field payload change is enough to invalidate the signature.',
    ],
    howToNavigate: [
      'Generate a key first or paste a valid 64-hex-character key.',
      'Sign the artifact before exploring the verification panel.',
      'Verify once in the clean state, then toggle tamper payload and verify again.',
      'Compare the signed artifact JSON, signature snippet, and VALID or INVALID card together.',
    ],
    steps: [
      {
        title: 'Generate a key and sign an artifact',
        instruction:
          'Click Generate to create a random 32-byte hex key, then click Sign Artifact. The SDK computes an HMAC-SHA256 digest of the artifact payload using that key.',
      },
      {
        title: 'Inspect the signed artifact',
        instruction:
          'The signed_artifact.json CodeBlock shows the full artifact JSON with the signature field included. This is the evidence package you would store or transmit.',
      },
      {
        title: 'Verify the signature',
        instruction:
          'Click Verify. The SDK recomputes the HMAC from the payload and compares it to the stored signature using constant-time comparison.',
      },
      {
        title: 'Test tamper detection',
        instruction:
          'Toggle Tamper to change the payload, then click Verify again. The signature no longer matches, so the result flips to Fail.',
        tip: 'The Signed metric only tells you the artifact carries a signature. Verification still requires the original key.',
      },
    ],
    takeaway:
      'Signing turns an audit artifact from a log record into integrity evidence you can verify later.',
    glossary: [
      { term: 'HMAC-SHA256', definition: 'A keyed hash algorithm that produces a fixed-length digest. In this lab it is used to sign audit artifacts.' },
      { term: 'Constant-time comparison', definition: 'A comparison technique that avoids leaking information through timing differences when checking signatures.' },
      { term: 'Tamper detection', definition: 'If any signed field changes, the recomputed HMAC differs from the stored signature and verification fails.' },
    ],
  },

  3: {
    title: 'Audit Chain Guide',
    overview:
      'This lab moves from single-record evidence to sequence-level evidence. It shows how AIGC artifacts can be linked so that an auditor can detect tampering across a timeline, not just inside one artifact.',
    whyItMatters:
      'Compliance investigations rarely examine one record in isolation. They need to know whether a historical sequence has been edited, removed, or reordered after the fact.',
    whatThisLabShows: [
      'Each new artifact can carry chain_id, chain_index, and previous_audit_checksum fields that link it to the prior artifact.',
      'verify_chain checks whether the sequence still forms a valid hash-linked chain.',
      'AuditChain behavior is opt-in and happens after enforcement, not inside the core gate pipeline.',
    ],
    howToNavigate: [
      'Add one entry first so you can identify the genesis block.',
      'Add more entries and compare each prev value to the checksum of the block above it.',
      'Verify the chain before tampering so you have a clean reference point.',
      'Tamper one entry, re-run verification, and then export the JSON chain if you want the full record set.',
    ],
    steps: [
      {
        title: 'Add your first artifact',
        instruction:
          'Click + Entry 1, + Entry 2, or + Entry 3 to add the first record to the chain. It has no previous checksum, so it becomes the genesis entry.',
      },
      {
        title: 'Grow the chain',
        instruction:
          'Add more entries. Each new artifact stores the previous artifact checksum in previous_audit_checksum, shown as prev: in the chain view.',
        tip: 'Verify by eye: the prev value on block N+1 should match the checksum on block N.',
      },
      {
        title: 'Inspect the chain visualization',
        instruction:
          'Each block shows its index, timestamp-derived order, status, checksum fragment, and previous checksum fragment. The arrow indicates the hash pointer relationship.',
      },
      {
        title: 'Break and verify the chain',
        instruction:
          'Use tamper on a block, then click Verify Chain. The integrity card changes because a broken checksum invalidates the links that follow it.',
      },
    ],
    takeaway:
      'AIGC can extend one audit artifact into a tamper-evident history of many AI decisions.',
    glossary: [
      { term: 'Hash pointer', definition: 'The previous_audit_checksum field stores the SHA-256 digest of the previous artifact, creating the link between records.' },
      { term: 'Genesis block', definition: 'The first artifact in a chain. It has no previous checksum.' },
      { term: 'Tamper-evident', definition: 'If any past artifact changes, later links no longer validate and the chain fails verification.' },
    ],
  },

  4: {
    title: 'Policy Composition Guide',
    overview:
      'This lab shows how AIGC handles policy reuse without hiding the consequences. A base policy and child policy are merged in a controlled way so you can see exactly how inheritance changes allowed behavior.',
    whyItMatters:
      'Real programs need shared governance baselines plus local specialization. AIGC makes that composition explicit, reviewable, and testable instead of leaving it to copy-paste policy forks.',
    whatThisLabShows: [
      'A child policy can declare extends to inherit from a base policy.',
      'intersect, union, and replace produce materially different effective policies.',
      'The UI makes privilege escalation visible through merged YAML, role diffs, and escalation warnings.',
    ],
    howToNavigate: [
      'Compare the parent and child editors side by side before changing anything.',
      'Start with intersect to see the most restrictive merge, then switch to union and replace for contrast.',
      'After each merge, inspect the merged YAML and the kept, removed, and added roles together.',
      'Treat the escalation panel as the summary judgment of whether the child expanded the base policy.',
    ],
    steps: [
      {
        title: 'Review the base policy',
        instruction:
          'The left editor shows the base policy (medical_ai.yaml). It defines the shared governance baseline: roles, pre-conditions, output schema, and risk configuration. This is what the child policy inherits from.',
      },
      {
        title: 'Edit the child policy',
        instruction:
          'The right editor shows the child policy (medical_ai_child.yaml). Notice the first line: extends: "medical_ai.yaml". That field tells the SDK which base policy to merge with. Try changing a pre-condition or adding a role to see the merge result change.',
      },
      {
        title: 'Choose a composition strategy',
        instruction:
          'Select how conflicts between the two policies are resolved. intersect keeps only fields present in both, union combines all fields from both with the child winning on conflict, and replace drops the base entirely and uses only the child policy.',
        tip: 'Start with intersect. With the shipped sample child policy it restricts roles and produces no escalation.',
      },
      {
        title: 'Merge and inspect the result',
        instruction:
          'Click Merge. The merged policy YAML appears below. The roles diff shows which roles were kept, removed, or added. The escalation panel flags new tools or removed postconditions that make the merged policy more permissive than the base.',
        tip: 'An escalation means the child granted something the base policy did not.',
      },
    ],
    takeaway:
      'AIGC treats policy inheritance as a governed operation with visible consequences, not a hidden merge behind the scenes.',
    glossary: [
      { term: 'extends', definition: 'A field in the child policy YAML that names the base policy to inherit from. Written as extends: "base_policy.yaml" at the top of the child.' },
      { term: 'intersect', definition: 'Keeps only fields present in both base and child. This is the most restrictive strategy.' },
      { term: 'union', definition: 'Combines all fields from base and child; the child wins on conflicts. This is the most permissive strategy.' },
      { term: 'replace', definition: 'Drops the base policy and uses only the child policy.' },
    ],
  },

  5: {
    title: 'Loaders & Versioning Guide',
    overview:
      'This lab shows the operational side of AIGC policy management. It covers where policies come from, when they are active, and how you can test them before trusting them in production.',
    whyItMatters:
      'Governance is not just policy syntax. Production systems need controlled policy loading, time-bounded activation, and regression tests that prove the policy behaves as intended.',
    whatThisLabShows: [
      'AIGC supports the default FilePolicyLoader and custom loaders built on PolicyLoaderBase, including the InMemoryPolicyLoader in this demo.',
      'effective_date and expiration_date make policy validity explicit instead of relying on deployment timing.',
      'Policy test cases let you validate pass or fail expectations before a policy reaches live traffic.',
    ],
    howToNavigate: [
      'Use the Loaders tab first to compare FileSystem and InMemory loading paths.',
      'Switch to Versioning next and move the reference date across the validity window to see activation behavior.',
      'Finish on Testing and run the generated cases against a real sample policy.',
      'Watch the active loader class, date result, and test expectation summary as the main evidence surfaces.',
    ],
    steps: [
      {
        title: 'Select a loader mode',
        instruction:
          'Choose FileSystem or InMemory at the top of the Loaders tab. FileSystem uses FilePolicyLoader to read a policy file from disk. InMemory uses InMemoryPolicyLoader, a custom PolicyLoaderBase subclass, to parse raw YAML directly.',
        tip: 'The loader changes how policy is sourced, not how enforcement works after the policy is loaded.',
      },
      {
        title: 'Load or parse a policy',
        instruction:
          'In FileSystem mode, select a policy from the dropdown and click Load. In InMemory mode, paste or edit YAML in the textarea and click Parse. The loaded YAML and active loader class appear below.',
      },
      {
        title: 'Validate policy dates',
        instruction:
          'Switch to the Versioning tab. Set effective_date, expiration_date, and reference_date, then click Validate Dates. The timeline panel shows the policy validity window and whether the reference date is inside it.',
        tip: 'Set reference_date before effective_date or after expiration_date to see the policy become inactive.',
      },
      {
        title: 'Run policy tests',
        instruction:
          'Switch to the Testing tab. Select a policy and click Run Tests. The demo generates three policy test cases and reports whether enforcement matched the declared expectations.',
      },
    ],
    takeaway:
      'AIGC governance is operationalized: policies are loadable from controlled sources, valid for explicit time windows, and testable before release.',
    glossary: [
      { term: 'PolicyLoaderBase', definition: 'Abstract base class for custom policy loaders. Implement load(policy_ref) to source policy from any location.' },
      { term: 'FilePolicyLoader', definition: 'Default loader. Reads a YAML policy from a filesystem path.' },
      { term: 'InMemoryPolicyLoader', definition: 'Demo custom loader that parses policy YAML held in memory instead of reading from disk.' },
      { term: 'effective_date', definition: 'The date from which a policy becomes active.' },
      { term: 'expiration_date', definition: 'The date after which a policy becomes inactive.' },
      { term: 'Policy test case', definition: 'A deterministic invocation with a declared expected outcome used to validate policy behavior.' },
    ],
  },

  6: {
    title: 'Custom Gates Guide',
    overview:
      'This lab shows how teams can extend AIGC with domain-specific enforcement logic without forking the SDK. Custom gates plug into fixed phases of the pipeline and still produce auditable results.',
    whyItMatters:
      'Core governance covers common controls, but production systems often need checks that are specific to one domain, tenant, or workflow. AIGC supports that extension while keeping the execution model explicit.',
    whatThisLabShows: [
      'Custom EnforcementGate plugins can run at pre_authorization, post_authorization, pre_output, or post_output.',
      'A gate returns structured pass or fail data plus metadata instead of making opaque side effects.',
      'The artifact records gates_evaluated so operators can prove which gates ran for a decision.',
    ],
    howToNavigate: [
      'Pick a gate first and read its description before you run anything.',
      'Use the highlighted pipeline row to anchor where that gate sits in the sequence.',
      'Open show source when you want to connect the behavior back to implementation.',
      'Run contrasting scenarios for the selected gate and compare the gate result panel with the gates_evaluated list in the artifact.',
    ],
    steps: [
      {
        title: 'Select a gate',
        instruction:
          'Click a gate name to load its description and insertion point. You can inspect the gate before running any scenario.',
        tip: 'The supported insertion points are fixed: pre_authorization, post_authorization, pre_output, and post_output.',
      },
      {
        title: 'Review gate info and pipeline position',
        instruction:
          'The gate info panel shows the gate description and insertion_point. The pipeline strip highlights where in the enforcement sequence this gate runs. Click show source to inspect the implementation.',
      },
      {
        title: 'Select a scenario and run',
        instruction:
          'Choose a scenario that matches the selected gate, then click Run Gate. Session authorization and domain allowlist gates demonstrate pre_authorization and post_authorization, while confidence, response length, PII detection, and audit metadata cover the output phases.',
      },
      {
        title: 'Inspect gate result and artifact evidence',
        instruction:
          'The gate result shows pass or fail, failure messages, and metadata. Below it, gates_evaluated lists the gate identifiers recorded in the artifact, including the selected custom gate.',
      },
    ],
    takeaway:
      'AIGC is extensible without becoming arbitrary: custom logic plugs into declared phases and still leaves evidence.',
    glossary: [
      { term: 'EnforcementGate', definition: 'A plugin class that inserts custom logic at one pipeline phase. Extend EnforcementGate and set insertion_point.' },
      { term: 'insertion_point', definition: 'One of four supported phases: pre_authorization, post_authorization, pre_output, or post_output.' },
      { term: 'GateResult', definition: 'Returned by evaluate(). Contains passed, failures, and metadata.' },
      { term: 'gates_evaluated', definition: 'Ordered list of gate identifiers recorded in artifact metadata. It shows which gates actually ran.' },
    ],
  },

  7: {
    title: 'Compliance Dashboard Guide',
    overview:
      'This lab turns all prior enforcement activity into an operator-facing evidence surface. It shows how AIGC moves from runtime control to reviewable audit history, filtering, and export.',
    whyItMatters:
      'Governance only matters if someone can inspect the record afterward. The compliance dashboard shows what an analyst or auditor can actually do with AIGC evidence once the SDK has produced it.',
    whatThisLabShows: [
      'Every enforcement run in Labs 1-6 can feed a live session audit trail.',
      'Sample mode is an explicit teaching aid, not a silent default data source.',
      'The UI mirrors the compliance export workflow with filterable records, downloadable JSON and CSV, and CLI equivalents.',
    ],
    howToNavigate: [
      'If the table is empty, either run earlier labs to create live records or click Load Sample Data.',
      'Use ALL, PASS, FAIL, and the policy dropdown together to narrow the dataset.',
      'Expand rows to inspect checksums, risk data, gates_evaluated, chain fields, and signature presence.',
      'Compare what you see in the dashboard with the aigc compliance export commands shown below the table.',
    ],
    steps: [
      {
        title: 'Build your audit log',
        instruction:
          'Run enforcement in any lab from Labs 1-6 to add records to the session audit trail. If no records exist yet, click Load Sample Data to explore the dashboard with fixture records.',
      },
      {
        title: 'Filter records',
        instruction:
          'Use ALL, PASS, and FAIL to filter by enforcement result. If multiple policies appear, use the policy dropdown to narrow to a single policy file. Both filters apply together.',
      },
      {
        title: 'Inspect a record',
        instruction:
          'Click any row to expand it. Session records show full artifact detail such as checksum, previous_audit_checksum, risk mode and threshold, gates_evaluated, and signature presence. Sample records show summary fields only.',
        tip: 'A signed indicator means signing was enabled for that record. It does not prove verification on its own.',
      },
      {
        title: 'Export for compliance',
        instruction:
          'Use the JSON or CSV export controls to download the visible records. The matching CLI path is aigc compliance export --input audit.jsonl, with --include-artifacts for full-record reports.',
      },
    ],
    takeaway:
      'AIGC ends with usable evidence: a filterable audit trail that operators can inspect and export, not just internal enforcement logic.',
    glossary: [
      { term: 'Audit artifact', definition: 'The immutable record produced by each enforcement call. It carries the result plus evidence such as checksums, metadata, and optional signature.' },
      { term: 'Enforcement result', definition: 'The final governance decision: PASS when allowed, FAIL when blocked.' },
      { term: 'Signed (checkmark)', definition: 'Indicates signing was enabled for that invocation. Verification still requires the original signing key.' },
      { term: 'Sample mode', definition: 'An explicit mode activated by clicking Load Sample Data. It shows fixture records with a banner and can be cleared.' },
    ],
  },
  8: {
    title: 'Governed Knowledge Base Guide',
    overview:
      'This lab introduces a governed knowledge base in beginner-friendly terms. ' +
      'Think of it as a retrieval answer that is only allowed to pass when the app can ' +
      'name the documents it used. You choose one scenario, run one query, and then read ' +
      'the result cards, source IDs, and artifact together.',
    whyItMatters:
      'Retrieval and RAG systems often sound confident even when they cannot prove where ' +
      'an answer came from. Provenance enforcement turns "please cite your sources" into ' +
      'a runtime rule: if no source IDs are present, the answer is blocked.',
    whatThisLabShows: [
      'Why the same knowledge-base workflow passes when context.provenance.source_ids is present and fails when it is missing.',
      'How the source IDs metric changes from zero, to one cited document, to several cited documents.',
      'Where to find the key evidence surfaces: the enforcement result, provenance gate status, error line, and artifact JSON.',
      'How a built-in custom gate can enforce attribution without changing the rest of the policy model.',
    ],
    howToNavigate: [
      'Start with "Single source (pass)" to establish the clean baseline before you trigger a failure.',
      'Switch to "Unsourced (fail)" next so the missing-provenance block is easy to spot.',
      'Use "Multi-source (pass)" last to see that provenance is not just yes-or-no; the lab records how many source IDs were supplied.',
      'After each run, read the three metric cards first, then the source IDs or error line, then the artifact JSON.',
    ],
    steps: [
      {
        title: 'Establish the baseline with one cited source',
        instruction:
          'Choose "Single source (pass)" and click "Run KB Query". This gives you the ' +
          'easiest first run to read: enforcement_result is PASS, source IDs is 1, and the ' +
          'provenance gate card shows ALLOWED.',
        tip: 'Start here if you are new. It is easier to learn the screen from a clean pass before you compare failures.',
      },
      {
        title: 'Trigger the provenance failure',
        instruction:
          'Choose "Unsourced (fail)" and run the same workflow again. The built-in ProvenanceGate runs at pre_output and blocks the response because context.provenance.source_ids is missing.',
        tip: 'On this run, the cards change together: enforcement_result becomes FAIL, source IDs drops to 0, provenance gate flips to BLOCKED, and the error line explains what was missing.',
      },
      {
        title: 'Compare one source with many sources',
        instruction:
          'Run "Multi-source (pass)" after the baseline pass. Both sourced scenarios succeed, ' +
          'but the source IDs count grows from 1 to 3. That shows provenance is capturing specific supporting documents, not just a generic citation flag.',
      },
      {
        title: 'Read the artifact evidence',
        instruction:
          'Use the artifact JSON to confirm what happened. Passing runs show metadata with ' +
          'gates_evaluated including custom:provenance_gate. Failing runs keep the audit trail but also include failures that name the missing provenance reason.',
      },
    ],
    takeaway:
      'A governed knowledge-base answer is not just text. It is an answer plus enforceable source attribution, and this lab shows exactly where that evidence appears.',
    glossary: [
      { term: 'ProvenanceGate', definition: 'A built-in EnforcementGate that blocks output when context.provenance.source_ids is missing or empty. Runs at the pre_output insertion point.' },
      { term: 'source_ids', definition: 'A list of document identifiers in context.provenance.source_ids that attribute the response to specific knowledge sources.' },
      { term: 'provenance', definition: 'The invocation context field that carries source attribution data for the response.' },
      { term: 'custom:provenance_gate', definition: 'The gate identifier recorded in gates_evaluated when the provenance gate runs during enforcement.' },
    ],
  },
  9: {
    title: 'Governed vs. Ungoverned Guide',
    overview:
      'This lab is a side-by-side comparison for new users. It sends the same medical AI ' +
      'scenario down two paths: governed with AIGC and ungoverned with no checks. That ' +
      'makes governance visible without asking you to learn the whole SDK first.',
    whyItMatters:
      'Teams evaluating AIGC usually ask what governance adds beyond a normal model call. ' +
      'This lab answers with evidence instead of theory: the governed path produces an ' +
      'actual decision and metadata trail, while the ungoverned path does not.',
    whatThisLabShows: [
      'How the same prompt can produce a governed PASS or FAIL while the ungoverned path always returns PASS because there are no checks.',
      'Which evidence fields, such as policy_version, gates_evaluated, and risk_scoring, appear only on the governed side.',
      'Why a blocked high-risk scenario is the clearest demonstration of what an ungoverned path would miss.',
      'How the top metric cards summarize the governed decision before you inspect the two metadata panels.',
    ],
    howToNavigate: [
      'Start with "Low risk (governed PASS)" so you can see a normal successful run on both sides.',
      'Switch to "High risk (governed FAIL)" next because it creates the strongest governed-versus-ungoverned contrast.',
      'Use the top cards for the quick summary, then read the Governed and Ungoverned metadata panels side by side.',
      'Pay special attention to metadata.mode, gates_evaluated, and risk_scoring because those expose the evidence gap immediately.',
    ],
    steps: [
      {
        title: 'Start with a passing baseline',
        instruction:
          'Choose "Low risk (governed PASS)" and click "Compare". The governed side runs strict AIGC enforcement, while the ungoverned side returns a synthetic PASS record with no governance checks applied.',
        tip: 'This baseline helps you see that even when both sides pass, only the governed side produces meaningful governance evidence.',
      },
      {
        title: 'Run the high-risk contrast case',
        instruction:
          'Switch to "High risk (governed FAIL)" and compare again. In strict mode the governed path can fail on risk threshold or policy checks, but the ungoverned side still reports PASS because there is nothing to enforce.',
        tip: 'The ungoverned path can never produce a real FAIL in this lab because there are no gates to fail.',
      },
      {
        title: 'Read the metadata panels',
        instruction:
          'Read the two code panels as a before-and-after comparison. The governed panel shows governance metadata such as policy_version, gates_evaluated, and risk_scoring. The ungoverned panel shows metadata.mode set to ungoverned with an empty gates_evaluated list.',
      },
      {
        title: 'Interpret the evidence gap',
        instruction:
          'Use the top cards and metadata panels together to decide what would be missing in production without governance. If a decision, score, or gate list exists only on the governed side, that is evidence the ungoverned path would never capture.',
      },
    ],
    takeaway:
      'Governance changes more than the verdict. It adds the evidence needed to explain, audit, and defend that verdict.',
    glossary: [
      { term: 'Governed path', definition: 'The side of the comparison that runs the scenario through AIGC enforcement and returns a policy-driven result.' },
      { term: 'Ungoverned path', definition: 'The side of the comparison that returns output without policy checks. In this lab it is represented by a synthetic PASS record.' },
      { term: 'metadata.mode', definition: 'A metadata field that marks the ungoverned comparison record with mode: "ungoverned".' },
      { term: 'Evidence gap', definition: 'The missing decision data, risk data, and gate history you lose when an AI call is not governed.' },
    ],
  },
  10: {
    title: 'Split Enforcement Explorer Guide',
    overview:
      'This lab breaks split enforcement into two visible phases so new users can see where ' +
      'the model call sits. Instead of treating split mode as magic, it shows what runs before ' +
      'the call, what runs after the output returns, and what happens when the request is blocked early.',
    whyItMatters:
      'Split enforcement changes when governance work happens, not just how it is labeled. ' +
      'Phase A can stop an unauthorized request before token spend, while Phase B validates ' +
      'the returned output afterward. This is the default execution model since v0.3.3.',
    whatThisLabShows: [
      'Which checks belong to Phase A (pre-call authorization) and which belong to Phase B (post-output validation).',
      'How a Phase A failure prevents Phase B from running and avoids the model call altogether.',
      'How the lab summarizes each phase with its own result badge and gate count.',
      'How enforcement_mode distinguishes a full split run from a pre-call-only block.',
    ],
    howToNavigate: [
      'Start with "Low risk (both phases pass)" so you can see the full two-phase flow before you trigger a block.',
      'Then run "Pre-call block (Phase A fails)" to see the Phase B panel dim and show "not reached - token cost avoided".',
      'Use the four metric cards first, then compare the gate lists in the Phase A and Phase B panels.',
      'Finish by reading the footer line for the combined result and enforcement_mode value.',
    ],
    steps: [
      {
        title: 'See the full split flow first',
        instruction:
          'Choose "Low risk (both phases pass)" and click "Run Split Trace". Both phase panels populate, the Phase A and Phase B metric cards show PASS, and the gate counts tell you how much work happened in each phase.',
        tip: 'Start here if split enforcement is new to you. It is easier to learn the layout when both panels are active.',
      },
      {
        title: 'Trigger a Phase A block',
        instruction:
          'Switch to "Pre-call block (Phase A fails)" and run again. Phase A fails on pre-call checks such as role or precondition validation, and the Phase B panel shows "not reached - token cost avoided".',
        tip: 'When this happens, the footer reports enforcement_mode: split_pre_call_only.',
      },
      {
        title: 'Read the phase gate lists',
        instruction:
          'Compare the gate names listed under each phase. Phase A covers pre_authorization and post_authorization work such as guards, roles, and preconditions. Phase B covers pre_output, schema, postconditions, post_output, and risk scoring.',
      },
      {
        title: 'Use enforcement_mode as the summary',
        instruction:
          'Read the footer after each run. enforcement_mode: split means both phases ran. enforcement_mode: split_pre_call_only means Phase A blocked the request before the model call.',
      },
    ],
    takeaway:
      'Split enforcement makes the policy boundary visible. Phase A protects the model call, Phase B validates the output, and the lab shows both pieces separately.',
    glossary: [
      { term: 'Phase A', definition: 'Pre-call authorization phase. Runs pre_authorization and post_authorization gates before the model call. A failure here prevents the model from being called.' },
      { term: 'Phase B', definition: 'Post-output validation phase. Runs pre_output, schema, postconditions, post_output, and risk scoring after the model returns output.' },
      { term: 'split_pre_call_only', definition: 'enforcement_mode value when Phase A blocked the call. Phase B never ran.' },
      { term: 'split', definition: 'enforcement_mode value when both Phase A and Phase B ran as part of split enforcement.' },
    ],
  },
}
