import { useState } from 'react'
import StatusBadge from '@/components/shared/StatusBadge'
import { getScenario } from '@/mock/scenarios'

interface ChainEntry {
  index: number
  id: string
  checksum: string
  prevChecksum: string | null
  prompt: string
  result: string
  valid: boolean
}

function mockChecksum(data: string): string {
  let h = 5381
  for (let i = 0; i < data.length; i++) h = ((h << 5) + h) ^ data.charCodeAt(i)
  return Math.abs(h).toString(16).padStart(8, '0')
}

const CHAIN_SCENARIOS = ['chain_entry_1', 'chain_entry_2', 'chain_entry_3']

export default function Lab3AuditChain() {
  const [entries, setEntries] = useState<ChainEntry[]>([])
  const [tamperIdx, setTamperIdx] = useState<number | null>(null)

  const addEntry = (scenarioKey: string) => {
    const s = getScenario(scenarioKey)
    const idx = entries.length
    const prev = entries[idx - 1] ?? null
    const data = s.prompt + s.output.result + (prev?.checksum ?? 'genesis')
    const checksum = mockChecksum(data)
    const entry: ChainEntry = {
      index: idx,
      id: `entry-${idx + 1}`,
      checksum,
      prevChecksum: prev?.checksum ?? null,
      prompt: s.prompt,
      result: s.output.result,
      valid: true,
    }
    setEntries(e => [...e, entry])
    setTamperIdx(null)
  }

  const tamper = (idx: number) => {
    setTamperIdx(idx)
    setEntries(prev =>
      prev.map((e, i) => {
        if (i < idx) return e
        if (i === idx) return { ...e, checksum: 'deadbeef', valid: false }
        return { ...e, valid: false }
      })
    )
  }

  const reset = () => { setEntries([]); setTamperIdx(null) }

  return (
    <div className="p-4 max-w-4xl mx-auto">
      <p className="font-mono text-xs mb-4" style={{ color: 'var(--text-secondary)' }}>
        // hash-linked audit chain — each entry commits to previous
      </p>

      <div className="flex gap-2 mb-4 flex-wrap">
        {CHAIN_SCENARIOS.map(key => (
          <button
            key={key}
            onClick={() => addEntry(key)}
            className="font-mono text-xs px-3 py-1.5 rounded"
            style={{ background: 'var(--ibm-blue-60)', color: '#fff' }}
          >
            + {key.replace('chain_entry_', 'Entry ')}
          </button>
        ))}
        <button
          onClick={reset}
          className="font-mono text-xs px-3 py-1.5 rounded ml-auto"
          style={{ color: 'var(--text-secondary)', border: '1px solid var(--border-ui)' }}
        >
          reset
        </button>
      </div>

      {entries.length === 0 && (
        <div className="font-mono text-xs px-3 py-2 rounded" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-ui)', color: 'var(--text-secondary)' }}>
          // add entries to build the chain
        </div>
      )}

      <div className="space-y-2">
        {entries.map((entry, i) => (
          <div key={entry.id} className="rounded p-3" style={{ border: `1px solid ${entry.valid ? 'var(--border-ui)' : 'rgba(255,126,182,0.4)'}`, background: 'var(--bg-surface)' }}>
            <div className="flex items-center gap-2 mb-2">
              <span className="font-mono text-xs" style={{ color: 'var(--ibm-cyan-30)' }}>#{entry.index}</span>
              <StatusBadge status={entry.valid ? 'PASS' : 'FAIL'} />
              {tamperIdx === null && (
                <button onClick={() => tamper(i)} className="font-mono text-[11px] px-2 py-0.5 rounded ml-auto" style={{ color: 'var(--ibm-magenta-40)', border: '1px solid rgba(255,126,182,0.3)' }}>
                  tamper
                </button>
              )}
            </div>
            <div className="font-mono text-xs space-y-1">
              <div><span style={{ color: 'var(--text-secondary)' }}>prompt: </span><span style={{ color: 'var(--text-primary)' }}>{entry.prompt}</span></div>
              <div><span style={{ color: 'var(--text-secondary)' }}>checksum: </span><span style={{ color: entry.valid ? 'var(--ibm-teal-30)' : 'var(--ibm-magenta-40)' }}>{entry.checksum}</span></div>
              <div><span style={{ color: 'var(--text-secondary)' }}>prev: </span><span style={{ color: 'var(--text-secondary)' }}>{entry.prevChecksum ?? 'genesis'}</span></div>
            </div>
            {i < entries.length - 1 && (
              <div className="mt-2 font-mono text-xs" style={{ color: 'var(--ibm-blue-60)' }}>↓</div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
