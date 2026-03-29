import { useState } from 'react'
import StatusBadge from './StatusBadge'
import type { AuditRecord } from '@/mock/auditFixtures'

interface Props { records: AuditRecord[] }

export default function AuditTable({ records }: Props) {
  const [filter, setFilter] = useState<'ALL' | 'PASS' | 'FAIL'>('ALL')

  const visible = filter === 'ALL' ? records : records.filter(r => r.enforcement_result === filter)

  const exportJSON = () => {
    const blob = new Blob([JSON.stringify(visible, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a'); a.href = url; a.download = 'audit-log.json'; a.click()
    URL.revokeObjectURL(url)
  }

  const exportCSV = () => {
    const headers = 'id,timestamp,policy_file,role,model_provider,enforcement_result,risk_score,signed'
    const rows = visible.map(r =>
      `${r.id},${r.timestamp},${r.policy_file},${r.role},${r.model_provider},${r.enforcement_result},${r.risk_score},${r.signed}`
    )
    const blob = new Blob([[headers, ...rows].join('\n')], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a'); a.href = url; a.download = 'audit-log.csv'; a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div>
      {/* toolbar */}
      <div className="flex items-center gap-2 mb-3">
        {(['ALL', 'PASS', 'FAIL'] as const).map(f => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className="font-mono text-xs px-2.5 py-1 rounded transition-colors"
            style={
              filter === f
                ? { background: 'rgba(15,98,254,0.18)', color: 'var(--ibm-cyan-30)', border: '1px solid rgba(15,98,254,0.3)' }
                : { color: 'var(--text-secondary)', border: '1px solid var(--border-ui)' }
            }
          >
            {f}
          </button>
        ))}
        <div className="flex-1" />
        <button onClick={exportJSON} className="font-mono text-xs px-2.5 py-1 rounded" style={{ color: 'var(--ibm-blue-40)', border: '1px solid var(--border-ui)' }}>
          ↓ JSON
        </button>
        <button onClick={exportCSV} className="font-mono text-xs px-2.5 py-1 rounded" style={{ color: 'var(--ibm-teal-30)', border: '1px solid var(--border-ui)' }}>
          ↓ CSV
        </button>
      </div>

      {/* table */}
      <div className="overflow-x-auto rounded" style={{ border: '1px solid var(--border-ui)' }}>
        <table className="w-full text-xs font-mono">
          <thead>
            <tr style={{ background: 'var(--bg-surface)', borderBottom: '1px solid var(--border-ui)' }}>
              {['ID', 'Timestamp', 'Policy', 'Role', 'Provider', 'Result', 'Risk', 'Signed'].map(h => (
                <th key={h} className="text-left px-3 py-2 font-light tracking-wide" style={{ color: 'var(--text-secondary)' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {visible.map((r, i) => (
              <tr
                key={r.id}
                style={{
                  background: i % 2 === 0 ? 'var(--bg-base)' : 'var(--bg-surface)',
                  borderBottom: '1px solid var(--border-ui)',
                }}
              >
                <td className="px-3 py-2" style={{ color: 'var(--ibm-cyan-30)' }}>{r.id}</td>
                <td className="px-3 py-2" style={{ color: 'var(--text-secondary)' }}>{r.timestamp.replace('T', ' ').replace('Z', '')}</td>
                <td className="px-3 py-2" style={{ color: 'var(--text-primary)' }}>{r.policy_file}</td>
                <td className="px-3 py-2" style={{ color: 'var(--text-secondary)' }}>{r.role}</td>
                <td className="px-3 py-2" style={{ color: 'var(--text-secondary)' }}>{r.model_provider}</td>
                <td className="px-3 py-2"><StatusBadge status={r.enforcement_result} /></td>
                <td className="px-3 py-2" style={{ color: r.risk_score > 0.7 ? 'var(--ibm-magenta-40)' : 'var(--ibm-teal-30)' }}>{r.risk_score.toFixed(2)}</td>
                <td className="px-3 py-2" style={{ color: r.signed ? 'var(--ibm-teal-30)' : 'var(--text-secondary)' }}>{r.signed ? '✓' : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
