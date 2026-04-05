# AIGC v0.3.0 Architecture Diagram

This document is a historical snapshot of the runtime architecture that shipped
in `v0.3.0`.

For the current release architecture, use the `v0.3.2` assets under
`docs/architecture/diagrams/` together with
`docs/architecture/AIGC_HIGH_LEVEL_DESIGN.md`.

It intentionally excludes roadmap-only concepts that are discussed elsewhere
but are not importable SDK features in `0.3.0`, including
`GovernedToolExecutor`, `GovernedLLMProvider`, `register_validator`,
and `register_resolver`.

## Component View

```mermaid
flowchart TB
    subgraph Host["Host Application"]
        direction LR
        App["App / Agent / Orchestrator"]
        Gov["@governed decorator<br/>post-call wrapper"]
        Provider["Model Provider<br/>OpenAI / Anthropic / local"]

        App -->|"decorated call"| Gov
        Gov -->|"calls wrapped function"| Provider
        Provider -->|"model output"| Gov
    end

    subgraph SDK["AIGC SDK v0.3.0"]
        direction TB

        subgraph Entry["Invocation Boundary"]
            direction LR
            E1["enforce_invocation()"]
            E2["AIGC.enforce()"]
        end

        subgraph Policy["Policy Layer"]
            direction LR
            PolicyFile["Policy YAML"]
            Loader["FilePolicyLoader or<br/>PolicyLoaderBase"]
            Cache["PolicyCache<br/>instance-scoped"]
            Schema["JSON Schemas<br/>policy DSL + audit artifact"]
            Rules["Dates + composition<br/>effective_date / expiration_date<br/>intersect / union / replace"]
        end

        subgraph Core["Deterministic Enforcement Core"]
            direction LR
            G0["Custom Gates<br/>pre_authorization"]
            G1["Guard Evaluation"]
            G2["Role Validation"]
            G3["Precondition Validation"]
            G4["Tool Constraint Validation"]
            G5["Custom Gates<br/>post_authorization"]
            G6["Custom Gates<br/>pre_output"]
            G7["Output Schema Validation"]
            G8["Postcondition Validation"]
            G9["Custom Gates<br/>post_output"]
            G10["Risk Scoring<br/>strict / risk_scored / warn_only"]
        end

        Artifact["Audit Artifact Generation<br/>PASS or FAIL"]
        Sign["ArtifactSigner / HMACSigner<br/>optional"]
        Sink["AuditSink emission<br/>JSONL / callback / custom"]
        Telemetry["OpenTelemetry spans + gate events<br/>optional, no-op if absent"]
        Returned["Audit artifact returned to caller"]
    end

    subgraph Ops["Operational Utilities Around The Runtime"]
        direction LR
        Chain["AuditChain.append()<br/>opt-in, host-managed"]
        CLI["aigc compliance export<br/>reads JSONL audit trails"]
    end

    App -->|"direct integration"| E1
    App -->|"instance integration"| E2
    Gov -->|"assembles invocation after wrapped call returns"| E1

    E1 --> Loader
    E2 --> Cache --> Loader
    PolicyFile --> Loader
    Schema --> Loader
    Loader --> Rules
    Rules --> G0
    G0 --> G1 --> G2 --> G3 --> G4 --> G5 --> G6 --> G7 --> G8 --> G9 --> G10 --> Artifact
    Telemetry -.-> G0
    Telemetry -.-> Artifact

    Artifact -->|"unsigned"| Sink
    Artifact -->|"sign if configured"| Sign --> Sink
    Artifact --> Returned
    Returned --> App

    Returned -.->|"optional chaining by host"| Chain
    Sink -->|"stored audit trail"| CLI
```

## Pipeline View

```mermaid
flowchart LR
    Start["Invocation received"] --> Load["Invocation validation + policy load"]
    Load --> PreAuth["Custom gates<br/>pre_authorization"]
    PreAuth --> Guards["Guard evaluation"]
    Guards --> Role["Role validation"]
    Role --> Preconditions["Precondition validation"]
    Preconditions --> Tools["Tool constraint validation"]
    Tools --> PostAuth["Custom gates<br/>post_authorization"]
    PostAuth --> PreOutput["Custom gates<br/>pre_output"]
    PreOutput --> Schema["Output schema validation"]
    Schema --> Postconditions["Postcondition validation"]
    Postconditions --> PostOutput["Custom gates<br/>post_output"]
    PostOutput --> Risk["Risk scoring<br/>if configured"]
    Risk --> Audit["Generate PASS / FAIL audit artifact"]
    Audit --> Emit["Emit to sink + return artifact"]
```

## Notes

- `@governed` is post-call governance. The wrapped function runs first, then
  AIGC assembles the invocation and enforces policy on the result.
- `AuditChain` is not part of the automatic enforcement pipeline in `0.3.0`.
  It is an opt-in utility the host applies to artifacts it manages.
- `aigc compliance export` is an offline analysis step over stored audit
  artifacts, not a live runtime gate.
- Pre-pipeline failures still produce schema-valid FAIL artifacts, but they
  bypass the core gate sequence because enforcement never fully starts.
