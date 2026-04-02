import { useMemo } from 'react'
import MetricCard from '@/components/shared/MetricCard'
import AuditTable from '@/components/shared/AuditTable'
import { useAigc } from '@/context/AigcContext'
import type { Artifact } from '@/types/artifact'
import type { AuditRecord } from '@/mock/auditFixtures'

function toRecord(a: Artifact, idx: number): AuditRecord {
  return {
    id: (a.checksum ?? String(idx)).slice(0, 6),
    timestamp: (a.timestamp as string | undefined) ?? new Date().toISOString(),
    policy_file: String(a.policy_file ?? 'unknown'),
    role: a.role,
    model_provider: a.model_provider,
    model_identifier: a.model_identifier,
    enforcement_result: a.enforcement_result,
    risk_score: a.metadata?.risk_scoring?.score ?? 0,
    signed: !!a.signature,
    chain_id: a.chain_id,
  }
}

export default function Lab7Compliance() {
  const { auditHistory } = useAigc()

  const records: AuditRecord[] = useMemo(
    () => auditHistory.map(toRecord),
    [auditHistory],
  )

  const total   = records.length
  const passed  = records.filter(r => r.enforcement_result === 'PASS').length
  const failed  = total - passed
  const avgRisk = total > 0
    ? (records.reduce((s, r) => s + r.risk_score, 0) / total).toFixed(2)
    : '—'

  return (
    <div className="p-4 max-w-5xl mx-auto">
      <p className="font-mono text-xs mb-4" style={{ color: 'var(--text-secondary)' }}>
        // full audit trail — filter, inspect, and export governance records
      </p>

      <div className="grid grid-cols-4 gap-2 mb-6">
        <MetricCard value={String(total)}  label="TOTAL"    color="var(--ibm-cyan-30)" />
        <MetricCard value={String(passed)} label="PASS"     color="var(--ibm-teal-30)" />
        <MetricCard value={String(failed)} label="FAIL"     color="var(--ibm-magenta-40)" />
        <MetricCard value={avgRisk}        label="AVG RISK" color="var(--ibm-blue-40)" />
      </div>

      {total === 0 ? (
        <div className="font-mono text-xs px-3 py-2 rounded" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-ui)', color: 'var(--text-secondary)' }}>
          // no audit records yet — run enforcement in any lab to populate this view
        </div>
      ) : (
        <AuditTable records={records} />
      )}
    </div>
  )
}
