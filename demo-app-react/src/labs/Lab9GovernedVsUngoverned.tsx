import { useState } from 'react'
import MetricCard from '@/components/shared/MetricCard'
import StatusBadge from '@/components/shared/StatusBadge'
import CodeBlock from '@/components/shared/CodeBlock'
import { useApi } from '@/hooks/useApi'
import { IBM_COLORS } from '@/theme/tokens'
import type { Artifact } from '@/types/artifact'

interface ComparePanel {
  artifact: Artifact | null
  error: string | null
}

interface Lab9Response {
  artifact: Artifact | null  // governed artifact surfaced for useApi auditHistory ingestion
  governed: ComparePanel
  ungoverned: ComparePanel
  scenario_key: string
}

const COMPARE_SCENARIOS = [
  { key: 'low_risk_faq',               label: 'Low risk (governed PASS)'         },
  { key: 'high_risk_drug_interaction',  label: 'High risk (governed FAIL)'        },
  { key: 'medium_risk_medical',         label: 'Medium risk'                      },
] as const

export default function Lab9GovernedVsUngoverned() {
  const { call: callApi, loading } = useApi<Lab9Response>()
  const [scenarioKey, setScenarioKey] = useState<string>('high_risk_drug_interaction')
  const [result, setResult] = useState<Lab9Response | null>(null)

  const run = async () => {
    const res = await callApi('/api/lab9/compare', { scenario_key: scenarioKey })
    if (res) setResult(res)
  }

  const govResult = result?.governed?.artifact?.enforcement_result ?? null
  const govGates  = result?.governed?.artifact?.metadata?.gates_evaluated?.length ?? 0
  const govRisk   = result?.governed?.artifact?.metadata?.risk_scoring?.score ?? null

  return (
    <div className="p-4 max-w-5xl mx-auto">
      <p className="font-mono text-xs mb-4" style={{ color: 'var(--text-secondary)' }}>
        // lab 9 — governed vs. ungoverned: same query, different evidence
      </p>

      <div className="flex items-center gap-3 mb-4">
        <select
          className="border rounded px-3 py-1.5 text-sm bg-base text-text-1"
          value={scenarioKey}
          onChange={e => setScenarioKey(e.target.value)}
        >
          {COMPARE_SCENARIOS.map(s => (
            <option key={s.key} value={s.key}>{s.label}</option>
          ))}
        </select>
        <button
          className="px-4 py-1.5 rounded text-sm font-medium text-white disabled:opacity-50"
          style={{ background: IBM_COLORS.orange40 }}
          onClick={run}
          disabled={loading}
        >
          {loading ? 'Running…' : 'Compare'}
        </button>
      </div>

      {result && (
        <>
          <div className="grid grid-cols-3 gap-2 mb-4">
            <MetricCard
              value={govResult ?? '—'}
              label="governed result"
              color={govResult === 'PASS' ? IBM_COLORS.green40 : IBM_COLORS.red40}
            />
            <MetricCard
              value={String(govGates)}
              label="gates evaluated"
              color={IBM_COLORS.orange40}
            />
            <MetricCard
              value={govRisk !== null ? govRisk.toFixed(2) : '—'}
              label="risk score"
              color={IBM_COLORS.orange40}
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            {/* Governed panel */}
            <div className="rounded border p-3" style={{ borderColor: 'var(--border-ui)' }}>
              <div className="flex items-center gap-2 mb-2">
                <span className="text-xs font-semibold uppercase" style={{ color: IBM_COLORS.orange40 }}>
                  Governed
                </span>
                {govResult && <StatusBadge status={govResult} />}
              </div>
              {result.governed.error && (
                <p className="text-xs mb-2" style={{ color: IBM_COLORS.red40 }}>
                  {result.governed.error}
                </p>
              )}
              <CodeBlock
                code={JSON.stringify(result.governed.artifact?.metadata ?? {}, null, 2)}
                label="governance metadata"
              />
            </div>

            {/* Ungoverned panel */}
            <div className="rounded border p-3" style={{ borderColor: 'var(--border-ui)' }}>
              <div className="flex items-center gap-2 mb-2">
                <span className="text-xs font-semibold uppercase" style={{ color: 'var(--text-secondary)' }}>
                  Ungoverned
                </span>
                <span className="text-xs font-mono px-1 rounded" style={{ background: 'var(--bg-surface)', color: 'var(--text-secondary)' }}>
                  no checks
                </span>
              </div>
              <CodeBlock
                code={JSON.stringify(result.ungoverned.artifact?.metadata ?? {}, null, 2)}
                label="raw output metadata"
              />
            </div>
          </div>
        </>
      )}
    </div>
  )
}
