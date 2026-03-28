// Static audit log fixture for Lab 7 — Compliance Dashboard

export interface AuditRecord {
  id: string
  timestamp: string
  policy_file: string
  role: string
  model_provider: string
  model_identifier: string
  enforcement_result: 'PASS' | 'FAIL'
  risk_score: number
  signed: boolean
  chain_id?: string
}

export const AUDIT_LOG: AuditRecord[] = [
  { id: 'a1b2c3', timestamp: '2026-03-28T09:00:01Z', policy_file: 'medical_ai.yaml',       role: 'doctor',    model_provider: 'mock', model_identifier: 'mock-model', enforcement_result: 'PASS', risk_score: 0.65, signed: true,  chain_id: 'ch-001' },
  { id: 'd4e5f6', timestamp: '2026-03-28T09:01:15Z', policy_file: 'medical_ai.yaml',       role: 'nurse',     model_provider: 'mock', model_identifier: 'mock-model', enforcement_result: 'FAIL', risk_score: 0.82, signed: true,  chain_id: 'ch-001' },
  { id: 'g7h8i9', timestamp: '2026-03-28T09:03:44Z', policy_file: 'finance_ai.yaml',       role: 'analyst',   model_provider: 'mock', model_identifier: 'mock-model', enforcement_result: 'PASS', risk_score: 0.30, signed: false, chain_id: undefined },
  { id: 'j0k1l2', timestamp: '2026-03-28T09:07:02Z', policy_file: 'medical_ai_child.yaml', role: 'doctor',    model_provider: 'internal', model_identifier: 'internal-med-v1', enforcement_result: 'PASS', risk_score: 0.00, signed: true, chain_id: 'ch-002' },
  { id: 'm3n4o5', timestamp: '2026-03-28T09:10:33Z', policy_file: 'content_moderation.yaml', role: 'content_reviewer', model_provider: 'mock', model_identifier: 'mock-model', enforcement_result: 'FAIL', risk_score: 0.90, signed: true, chain_id: undefined },
  { id: 'p6q7r8', timestamp: '2026-03-28T09:15:12Z', policy_file: 'high_risk.yaml',        role: 'admin',     model_provider: 'mock', model_identifier: 'mock-model', enforcement_result: 'FAIL', risk_score: 1.00, signed: false, chain_id: undefined },
  { id: 's9t0u1', timestamp: '2026-03-28T09:18:55Z', policy_file: 'finance_ai.yaml',       role: 'auditor',   model_provider: 'internal', model_identifier: 'internal-fin-v2', enforcement_result: 'PASS', risk_score: 0.15, signed: true, chain_id: 'ch-003' },
  { id: 'v2w3x4', timestamp: '2026-03-28T09:22:08Z', policy_file: 'medical_ai.yaml',       role: 'doctor',    model_provider: 'mock', model_identifier: 'mock-model', enforcement_result: 'PASS', risk_score: 0.50, signed: true, chain_id: 'ch-002' },
]
