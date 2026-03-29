import MetricCard from '@/components/shared/MetricCard'
import AuditTable from '@/components/shared/AuditTable'
import { AUDIT_LOG } from '@/mock/auditFixtures'

export default function Lab7Compliance() {
  const total  = AUDIT_LOG.length
  const passed = AUDIT_LOG.filter(r => r.enforcement_result === 'PASS').length
  const failed = total - passed
  const avgRisk = (AUDIT_LOG.reduce((s, r) => s + r.risk_score, 0) / total).toFixed(2)

  return (
    <div className="p-4 max-w-5xl mx-auto">
      <p className="font-mono text-xs mb-4" style={{ color: 'var(--text-secondary)' }}>
        // full audit trail — filter, inspect, and export governance records
      </p>

      <div className="grid grid-cols-4 gap-2 mb-6">
        <MetricCard value={String(total)}  label="TOTAL"       color="var(--ibm-cyan-30)" />
        <MetricCard value={String(passed)} label="PASS"        color="var(--ibm-teal-30)" />
        <MetricCard value={String(failed)} label="FAIL"        color="var(--ibm-magenta-40)" />
        <MetricCard value={avgRisk}        label="AVG RISK"    color="var(--ibm-blue-40)" />
      </div>

      <AuditTable records={AUDIT_LOG} />
    </div>
  )
}
