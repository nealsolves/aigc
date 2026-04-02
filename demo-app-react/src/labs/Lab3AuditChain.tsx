import { useState } from 'react'
import StatusBadge from '@/components/shared/StatusBadge'
import MetricCard from '@/components/shared/MetricCard'
import { useApi } from '@/hooks/useApi'
import type { Artifact } from '@/types/artifact'

interface AppendResponse { artifact: Artifact; chain_id: string }
interface VerifyResponse { valid: boolean; errors: string[] }
interface TamperResponse { artifacts: Artifact[] }

const CHAIN_SCENARIOS = ['chain_entry_1', 'chain_entry_2', 'chain_entry_3']

export default function Lab3AuditChain() {
  const [entries, setEntries]     = useState<Artifact[]>([])
  const [chainId, setChainId]     = useState<string | null>(null)
  const [tampered, setTampered]   = useState(false)
  const [verified, setVerified]   = useState<{ valid: boolean; errors: string[] } | null>(null)

  const { call: callAppend,  loading: loadingAppend  } = useApi<AppendResponse>()
  const { call: callVerify,  loading: loadingVerify  } = useApi<VerifyResponse>()
  const { call: callTamper,  loading: loadingTamper  } = useApi<TamperResponse>()

  const addEntry = async (scenarioKey: string) => {
    const lastEntry = entries[entries.length - 1] ?? null
    const res = await callAppend('/api/chain/append', {
      scenario_key: scenarioKey,
      chain_id: chainId,
      previous_checksum: lastEntry?.checksum ?? null,
      chain_index: entries.length,
    })
    if (res) {
      if (!chainId) setChainId(res.chain_id)
      setEntries(prev => [...prev, res.artifact])
      setVerified(null)
    }
  }

  const verify = async () => {
    if (!entries.length) return
    const res = await callVerify('/api/chain/verify', { artifacts: entries })
    if (res) setVerified(res)
  }

  const tamperEntry = async (idx: number) => {
    const res = await callTamper('/api/chain/tamper', { artifacts: entries, index: idx })
    if (res) { setEntries(res.artifacts); setTampered(true); setVerified(null) }
  }

  const reset = () => { setEntries([]); setChainId(null); setTampered(false); setVerified(null) }

  const exportChain = () => {
    const blob = new Blob([JSON.stringify(entries, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url; a.download = 'audit_chain.json'; a.click()
    URL.revokeObjectURL(url)
  }

  const integrityLabel = verified === null ? 'Not checked' : verified.valid ? 'INTACT' : 'BROKEN'
  const integrityColor = verified === null ? 'var(--text-secondary)' : verified.valid ? 'var(--ibm-teal-30)' : 'var(--ibm-magenta-40)'

  return (
    <div className="p-4 max-w-4xl mx-auto">
      <p className="font-mono text-xs mb-4" style={{ color: 'var(--text-secondary)' }}>
        // hash-linked audit chain — each entry commits to previous
      </p>

      {/* Controls */}
      <div className="flex gap-2 mb-4 flex-wrap">
        {CHAIN_SCENARIOS.map(key => (
          <button
            key={key}
            onClick={() => addEntry(key)}
            disabled={loadingAppend}
            className="font-mono text-xs px-3 py-1.5 rounded"
            style={{ background: 'var(--ibm-blue-60)', color: '#fff', opacity: loadingAppend ? 0.7 : 1 }}
          >
            {loadingAppend ? '…' : `+ ${key.replace('chain_entry_', 'Entry ')}`}
          </button>
        ))}
        <button
          onClick={verify}
          disabled={!entries.length || loadingVerify}
          className="font-mono text-xs px-3 py-1.5 rounded"
          style={{ background: 'var(--ibm-teal-60)', color: '#fff', opacity: (!entries.length || loadingVerify) ? 0.7 : 1 }}
        >
          {loadingVerify ? '…' : 'Verify Chain'}
        </button>
        <button
          onClick={reset}
          className="font-mono text-xs px-3 py-1.5 rounded ml-auto"
          style={{ color: 'var(--text-secondary)', border: '1px solid var(--border-ui)' }}
        >
          reset
        </button>
      </div>

      {/* Chain stats */}
      {(entries.length > 0 || chainId) && (
        <div className="grid grid-cols-3 gap-2 mb-4">
          <MetricCard value={String(entries.length)} label="CHAIN LENGTH" color="var(--ibm-blue-40)" />
          <MetricCard value={chainId ? chainId.slice(0, 12) + '…' : '—'} label="CHAIN ID" color="var(--ibm-cyan-30)" />
          <MetricCard value={integrityLabel} label="INTEGRITY" color={integrityColor} />
        </div>
      )}

      {/* Verification result */}
      {verified !== null && (
        <div className="font-mono text-xs px-3 py-2 rounded mb-4"
          style={{
            background: verified.valid ? 'rgba(8,186,132,0.08)' : 'rgba(255,126,182,0.08)',
            border: `1px solid ${verified.valid ? 'rgba(8,186,132,0.3)' : 'rgba(255,126,182,0.3)'}`,
            color: verified.valid ? 'var(--ibm-teal-30)' : 'var(--ibm-magenta-40)',
          }}
        >
          {verified.valid
            ? '// chain integrity verified — all links intact'
            : `// chain BROKEN — ${verified.errors.length} error(s): ${verified.errors[0]}`}
        </div>
      )}

      {entries.length === 0 && (
        <div className="font-mono text-xs px-3 py-2 rounded" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-ui)', color: 'var(--text-secondary)' }}>
          // add entries to build the chain
        </div>
      )}

      {/* Chain visualization */}
      <div className="space-y-2">
        {entries.map((entry, i) => {
          const checksum = entry.checksum ?? '—'
          const prev = entry.previous_audit_checksum

          return (
            <div key={i}>
              <div className="rounded p-3" style={{ border: `1px solid ${tampered ? 'rgba(255,126,182,0.4)' : 'var(--border-ui)'}`, background: 'var(--bg-surface)' }}>
                <div className="flex items-center gap-2 mb-2">
                  <span className="font-mono text-xs" style={{ color: 'var(--ibm-cyan-30)' }}>#{i}</span>
                  <StatusBadge status={entry.enforcement_result} />
                  {!tampered && (
                    <button
                      onClick={() => tamperEntry(i)}
                      disabled={loadingTamper}
                      className="font-mono text-[11px] px-2 py-0.5 rounded ml-auto"
                      style={{ color: 'var(--ibm-magenta-40)', border: '1px solid rgba(255,126,182,0.3)' }}
                    >
                      tamper
                    </button>
                  )}
                </div>
                <div className="font-mono text-xs space-y-1">
                  <div><span style={{ color: 'var(--text-secondary)' }}>checksum: </span><span style={{ color: 'var(--ibm-teal-30)' }}>{checksum.slice(0, 16)}…</span></div>
                  <div><span style={{ color: 'var(--text-secondary)' }}>prev: </span><span style={{ color: 'var(--text-secondary)' }}>{prev ? prev.slice(0, 16) + '…' : 'genesis'}</span></div>
                </div>
              </div>
              {i < entries.length - 1 && (
                <div className="font-mono text-xs mt-1" style={{ color: 'var(--ibm-blue-60)' }}>↓</div>
              )}
            </div>
          )
        })}
      </div>

      {/* Export */}
      {entries.length > 0 && (
        <button
          onClick={exportChain}
          className="mt-4 font-mono text-xs px-3 py-1.5 rounded"
          style={{ color: 'var(--text-secondary)', border: '1px solid var(--border-ui)' }}
        >
          Export Chain (JSON)
        </button>
      )}
    </div>
  )
}
