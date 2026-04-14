import { useState } from 'react'
import MetricCard from '@/components/shared/MetricCard'
import StatusBadge from '@/components/shared/StatusBadge'
import CodeBlock from '@/components/shared/CodeBlock'
import { useApi } from '@/hooks/useApi'
import { IBM_COLORS } from '@/theme/tokens'
import type { Artifact } from '@/types/artifact'

interface Lab8Response {
  artifact: Artifact | null
  source_ids: string[]
  error: string | null
}

const KB_SCENARIOS = [
  { key: 'kb_sourced_pass',    label: 'Single source (pass)' },
  { key: 'kb_unsourced_fail',  label: 'Unsourced (fail)'     },
  { key: 'kb_multi_source_pass', label: 'Multi-source (pass)' },
] as const

export default function Lab8GovernedKnowledgeBase() {
  const { call: callApi, loading } = useApi<Lab8Response>()
  const [scenarioKey, setScenarioKey] = useState<string>('kb_sourced_pass')
  const [result, setResult] = useState<Lab8Response | null>(null)

  const run = async () => {
    const res = await callApi('/api/lab8/query-kb', { scenario_key: scenarioKey })
    if (res) setResult(res)
  }

  const enforcementResult = result?.artifact?.enforcement_result ?? null
  const sourceCount = result?.source_ids?.length ?? 0

  return (
    <div className="p-4 max-w-5xl mx-auto">
      <p className="font-mono text-xs mb-4" style={{ color: 'var(--text-secondary)' }}>
        // lab 8 — governed knowledge base: provenance enforcement over retrieval workflows
      </p>

      <div className="flex items-center gap-3 mb-4">
        <select
          className="border rounded px-3 py-1.5 text-sm bg-base text-text-1"
          value={scenarioKey}
          onChange={e => setScenarioKey(e.target.value)}
        >
          {KB_SCENARIOS.map(s => (
            <option key={s.key} value={s.key}>{s.label}</option>
          ))}
        </select>
        <button
          className="px-4 py-1.5 rounded text-sm font-medium text-white disabled:opacity-50"
          style={{ background: IBM_COLORS.green40 }}
          onClick={run}
          disabled={loading}
        >
          {loading ? 'Running…' : 'Run KB Query'}
        </button>
      </div>

      {result && (
        <>
          <div className="grid grid-cols-3 gap-2 mb-4">
            <MetricCard
              value={enforcementResult ?? '—'}
              label="enforcement result"
              color={enforcementResult === 'PASS' ? IBM_COLORS.green40 : IBM_COLORS.red40}
            />
            <MetricCard
              value={String(sourceCount)}
              label="source IDs"
              color={IBM_COLORS.green40}
            />
            <MetricCard
              value={result.error ? 'BLOCKED' : 'ALLOWED'}
              label="provenance gate"
              color={result.error ? IBM_COLORS.red40 : IBM_COLORS.green40}
            />
          </div>

          {result.source_ids.length > 0 && (
            <div className="mb-4 p-3 rounded border text-sm font-mono" style={{ borderColor: 'var(--border-ui)' }}>
              <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>source IDs: </span>
              {result.source_ids.join(', ')}
            </div>
          )}

          {result.error && (
            <p className="text-sm mb-3" style={{ color: IBM_COLORS.red40 }}>{result.error}</p>
          )}

          <div className="flex items-center gap-2 mb-2">
            <StatusBadge status={enforcementResult ?? 'FAIL'} />
            <span className="text-xs font-mono" style={{ color: 'var(--text-secondary)' }}>
              {result.artifact?.metadata?.enforcement_mode ?? 'unified'}
            </span>
          </div>

          <CodeBlock
            code={JSON.stringify(result.artifact, null, 2)}
            label="artifact"
          />
        </>
      )}
    </div>
  )
}
