import { useState, useMemo } from 'react'
import MetricCard from '@/components/shared/MetricCard'
import AuditTable from '@/components/shared/AuditTable'
import CodeBlock from '@/components/shared/CodeBlock'
import { useAigc } from '@/context/AigcContext'
import type { Artifact } from '@/types/artifact'
import { AUDIT_LOG, type AuditRecord } from '@/mock/auditFixtures'

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
    rawArtifact: a,
  }
}

const CLI_BASIC    = 'aigc compliance export --input audit.jsonl'
const CLI_FULL     = 'aigc compliance export --input audit.jsonl --output report.json --include-artifacts'

export default function Lab7Compliance() {
  const { auditHistory } = useAigc()
  const [useSampleData, setUseSampleData] = useState(false)
  const [policyFilter,  setPolicyFilter]  = useState('ALL')

  const sessionRecords: AuditRecord[] = useMemo(
    () => auditHistory.map(toRecord),
    [auditHistory],
  )

  const baseRecords: AuditRecord[] = useSampleData ? AUDIT_LOG : sessionRecords

  const policyOptions = useMemo(() => {
    const values = Array.from(new Set(baseRecords.map(r => r.policy_file))).sort()
    return ['ALL', ...values]
  }, [baseRecords])

  const records: AuditRecord[] = useMemo(
    () => policyFilter === 'ALL' ? baseRecords : baseRecords.filter(r => r.policy_file === policyFilter),
    [baseRecords, policyFilter],
  )

  const total   = records.length
  const passed  = records.filter(r => r.enforcement_result === 'PASS').length
  const failed  = total - passed
  const avgRisk = total > 0
    ? (records.reduce((s, r) => s + r.risk_score, 0) / total).toFixed(2)
    : '—'

  const isEmpty = auditHistory.length === 0 && !useSampleData

  return (
    <div className="p-4 max-w-5xl mx-auto">
      <p className="font-mono text-xs mb-4" style={{ color: 'var(--text-secondary)' }}>
        // full audit trail — filter, inspect, and export governance records
      </p>

      {/* Sample data banner */}
      {useSampleData && (
        <div className="flex items-center gap-3 rounded px-3 py-2 mb-4" style={{ background: 'rgba(15,98,254,0.08)', border: '1px solid rgba(15,98,254,0.2)' }}>
          <span className="font-mono text-xs" style={{ color: 'var(--ibm-blue-40)' }}>// viewing sample data</span>
          <button
            onClick={() => { setUseSampleData(false); setPolicyFilter('ALL') }}
            className="font-mono text-[11px] ml-auto"
            style={{ color: 'var(--ibm-blue-60)' }}
          >
            clear
          </button>
        </div>
      )}

      {/* Empty state */}
      {isEmpty ? (
        <div className="rounded p-6 text-center" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-ui)' }}>
          <div className="font-mono text-xs mb-3" style={{ color: 'var(--text-secondary)' }}>
            // no audit records yet — run enforcement in any lab to populate this view
          </div>
          <button
            onClick={() => setUseSampleData(true)}
            className="font-mono text-xs px-4 py-2 rounded"
            style={{ background: 'var(--ibm-blue-60)', color: '#fff' }}
          >
            Load Sample Data
          </button>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-4 gap-2 mb-4">
            <MetricCard value={String(total)}  label="TOTAL"    color="var(--ibm-cyan-30)" />
            <MetricCard value={String(passed)} label="PASS"     color="var(--ibm-teal-30)" />
            <MetricCard value={String(failed)} label="FAIL"     color="var(--ibm-magenta-40)" />
            <MetricCard value={avgRisk}        label="AVG RISK" color="var(--ibm-blue-40)" />
          </div>

          {/* Policy filter */}
          {policyOptions.length > 2 && (
            <div className="flex items-center gap-2 mb-3">
              <span className="font-mono text-[11px]" style={{ color: 'var(--text-secondary)' }}>policy:</span>
              <select
                value={policyFilter}
                onChange={e => setPolicyFilter(e.target.value)}
                className="font-mono text-[12px] px-2 py-1 rounded outline-none"
                style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-ui)', color: 'var(--text-primary)' }}
              >
                {policyOptions.map(p => <option key={p} value={p}>{p}</option>)}
              </select>
            </div>
          )}

          <AuditTable records={records} />
        </>
      )}

      {/* CLI-equivalent section */}
      <div className="mt-6">
        <div className="font-mono text-xs mb-2" style={{ color: 'var(--text-secondary)' }}>// CLI equivalent — aigc compliance export</div>
        <CodeBlock code={`# Print compliance report to stdout\n${CLI_BASIC}\n\n# Write report with full artifact records\n${CLI_FULL}`} label="terminal" />
      </div>
    </div>
  )
}
