import { useState, Fragment } from 'react'
import StatusBadge from './StatusBadge'
import type { AuditRecord } from '@/mock/auditFixtures'

interface Props { records: AuditRecord[] }

export default function AuditTable({ records }: Props) {
  const [filter,      setFilter]      = useState<'ALL' | 'PASS' | 'FAIL'>('ALL')
  const [expandedRow, setExpandedRow] = useState<string | null>(null)

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

  const toggleRow = (id: string) => setExpandedRow(prev => prev === id ? null : id)

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
        <table className="w-full font-mono">
          <thead>
            <tr style={{ background: 'var(--bg-surface)', borderBottom: '1px solid var(--border-ui)' }}>
              <th className="w-6 px-2 py-2" />
              {['ID', 'Timestamp', 'Policy', 'Role', 'Provider', 'Result', 'Risk', 'Signed'].map(h => (
                <th key={h} className="text-left px-3 py-2 font-light text-xs tracking-wide" style={{ color: 'var(--text-secondary)' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {visible.map((r, i) => {
              const isExpanded = expandedRow === r.id
              const raw = r.rawArtifact
              return (
                <Fragment key={r.id}>
                  <tr
                    className="text-sm cursor-pointer"
                    onClick={() => toggleRow(r.id)}
                    style={{
                      background: i % 2 === 0 ? 'var(--bg-base)' : 'var(--bg-surface)',
                      borderBottom: isExpanded ? 'none' : '1px solid var(--border-ui)',
                    }}
                  >
                    <td className="px-2 py-2 font-mono text-[10px]" style={{ color: 'var(--text-secondary)' }}>
                      {isExpanded ? '▼' : '▶'}
                    </td>
                    <td className="px-3 py-2" style={{ color: 'var(--ibm-cyan-30)' }}>{r.id}</td>
                    <td className="px-3 py-2" style={{ color: 'var(--text-secondary)' }}>{String(r.timestamp).replace('T', ' ').replace('Z', '')}</td>
                    <td className="px-3 py-2" style={{ color: 'var(--text-primary)' }}>{r.policy_file}</td>
                    <td className="px-3 py-2" style={{ color: 'var(--text-secondary)' }}>{r.role}</td>
                    <td className="px-3 py-2" style={{ color: 'var(--text-secondary)' }}>{r.model_provider}</td>
                    <td className="px-3 py-2"><StatusBadge status={r.enforcement_result} /></td>
                    <td className="px-3 py-2" style={{ color: r.risk_score > 0.7 ? 'var(--ibm-magenta-40)' : 'var(--ibm-teal-30)' }}>{r.risk_score.toFixed(2)}</td>
                    <td className="px-3 py-2" style={{ color: r.signed ? 'var(--ibm-teal-30)' : 'var(--text-secondary)' }}>{r.signed ? '✓' : '—'}</td>
                  </tr>
                  {isExpanded && (
                    <tr key={`${r.id}-detail`} style={{ background: i % 2 === 0 ? 'var(--bg-base)' : 'var(--bg-surface)', borderBottom: '1px solid var(--border-ui)' }}>
                      <td colSpan={9} className="px-4 pb-3 pt-1">
                        {raw ? (
                          <div className="grid grid-cols-2 gap-x-6 gap-y-1 font-mono text-[11px]">
                            <div><span style={{ color: 'var(--text-secondary)' }}>checksum: </span><span style={{ color: 'var(--ibm-teal-30)' }}>{raw.checksum ? raw.checksum.slice(0, 24) + '…' : '—'}</span></div>
                            <div><span style={{ color: 'var(--text-secondary)' }}>previous_audit_checksum: </span><span style={{ color: 'var(--text-secondary)' }}>{raw.previous_audit_checksum ? String(raw.previous_audit_checksum).slice(0, 16) + '…' : 'none'}</span></div>
                            <div><span style={{ color: 'var(--text-secondary)' }}>model_identifier: </span><span style={{ color: 'var(--text-primary)' }}>{raw.model_identifier}</span></div>
                            <div><span style={{ color: 'var(--text-secondary)' }}>audit_schema_version: </span><span style={{ color: 'var(--text-primary)' }}>{raw.audit_schema_version ?? '—'}</span></div>
                            <div><span style={{ color: 'var(--text-secondary)' }}>risk mode: </span><span style={{ color: 'var(--ibm-purple-40)' }}>{raw.metadata?.risk_scoring?.mode ?? '—'}</span></div>
                            <div><span style={{ color: 'var(--text-secondary)' }}>risk threshold: </span><span style={{ color: 'var(--text-primary)' }}>{raw.metadata?.risk_scoring?.threshold ?? '—'}</span></div>
                            {raw.metadata?.gates_evaluated && raw.metadata.gates_evaluated.length > 0 && (
                              <div className="col-span-2"><span style={{ color: 'var(--text-secondary)' }}>gates_evaluated: </span><span style={{ color: 'var(--ibm-cyan-30)' }}>{raw.metadata.gates_evaluated.join(', ')}</span></div>
                            )}
                            <div><span style={{ color: 'var(--text-secondary)' }}>signature: </span><span style={{ color: raw.signature ? 'var(--ibm-teal-30)' : 'var(--text-secondary)' }}>{raw.signature ? 'present' : 'none'}</span></div>
                            {r.chain_id && <div><span style={{ color: 'var(--text-secondary)' }}>chain_id: </span><span style={{ color: 'var(--ibm-blue-40)' }}>{r.chain_id}</span></div>}
                          </div>
                        ) : (
                          <div className="font-mono text-[11px]" style={{ color: 'var(--text-secondary)' }}>
                            // full artifact data available for session-generated records only
                          </div>
                        )}
                      </td>
                    </tr>
                  )}
                </Fragment>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
