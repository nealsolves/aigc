export interface RiskFactor {
  name: string
  contribution: number
  triggered?: boolean
}

export interface Artifact {
  enforcement_result: 'PASS' | 'FAIL'
  model_provider: string
  model_identifier: string
  role: string
  policy_version?: string
  policy_file?: string
  audit_schema_version?: string
  timestamp?: string | number
  checksum?: string
  signature?: string
  chain_id?: string
  chain_index?: number
  previous_audit_checksum?: string | null
  metadata?: {
    risk_scoring?: {
      score: number
      threshold: number
      mode: string
      basis?: RiskFactor[]
    }
    gates_evaluated?: string[]
  }
  [key: string]: unknown
}
