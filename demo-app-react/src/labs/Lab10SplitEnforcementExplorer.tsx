import { useState } from 'react'
import MetricCard from '@/components/shared/MetricCard'
import StatusBadge from '@/components/shared/StatusBadge'
import { useApi } from '@/hooks/useApi'
import { IBM_COLORS } from '@/theme/tokens'
import type { Artifact } from '@/types/artifact'

interface PhaseInfo {
  result: 'PASS' | 'FAIL'
  gates_evaluated: string[]
  failures: unknown[]
  blocked: boolean
}

interface Lab10Response {
  phase_a: PhaseInfo | null
  phase_b: PhaseInfo | null
  artifact: Artifact | null
  combined_result: 'PASS' | 'FAIL'
  error: string | null
}

const SPLIT_SCENARIOS = [
  { key: 'split_precall_block', label: 'Pre-call block (Phase A fails)' },
  { key: 'low_risk_faq',        label: 'Low risk (both phases pass)'    },
  { key: 'medium_risk_medical', label: 'Medium risk'                    },
] as const

export default function Lab10SplitEnforcementExplorer() {
  const { call: callApi, loading } = useApi<Lab10Response>()
  const [scenarioKey, setScenarioKey] = useState<string>('split_precall_block')
  const [result, setResult] = useState<Lab10Response | null>(null)

  const run = async () => {
    const res = await callApi('/api/lab10/split-trace', { scenario_key: scenarioKey })
    if (res) setResult(res)
  }

  const phaseAGates = result?.phase_a?.gates_evaluated?.length ?? 0
  const phaseBGates = result?.phase_b?.gates_evaluated?.length ?? 0

  return (
    <div className="p-4 max-w-5xl mx-auto">
      <p className="font-mono text-xs mb-4" style={{ color: 'var(--text-secondary)' }}>
        // lab 10 — split enforcement explorer: phase a · phase b · token cost
      </p>

      <div className="flex items-center gap-3 mb-4">
        <select
          className="border rounded px-3 py-1.5 text-sm bg-base text-text-1"
          value={scenarioKey}
          onChange={e => setScenarioKey(e.target.value)}
        >
          {SPLIT_SCENARIOS.map(s => (
            <option key={s.key} value={s.key}>{s.label}</option>
          ))}
        </select>
        <button
          className="px-4 py-1.5 rounded text-sm font-medium text-white disabled:opacity-50"
          style={{ background: IBM_COLORS.red40 }}
          onClick={run}
          disabled={loading}
        >
          {loading ? 'Running…' : 'Run Split Trace'}
        </button>
      </div>

      {result && (
        <>
          <div className="grid grid-cols-4 gap-2 mb-4">
            <MetricCard
              value={result.phase_a?.result ?? '—'}
              label="Phase A"
              color={result.phase_a?.result === 'PASS' ? IBM_COLORS.green40 : IBM_COLORS.red40}
            />
            <MetricCard
              value={result.phase_b ? result.phase_b.result : 'skipped'}
              label="Phase B"
              color={result.phase_b
                ? (result.phase_b.result === 'PASS' ? IBM_COLORS.green40 : IBM_COLORS.red40)
                : IBM_COLORS.coolGray30}
            />
            <MetricCard value={String(phaseAGates)} label="Phase A gates" color={IBM_COLORS.red40} />
            <MetricCard value={String(phaseBGates)} label="Phase B gates" color={IBM_COLORS.red40} />
          </div>

          {/* Pipeline visualization */}
          <div className="grid grid-cols-2 gap-4 mb-4">
            {/* Phase A */}
            <div className="rounded border p-3" style={{ borderColor: 'var(--border-ui)' }}>
              <div className="flex items-center gap-2 mb-2">
                <span className="text-xs font-semibold uppercase" style={{ color: IBM_COLORS.red40 }}>
                  Phase A
                </span>
                <span className="text-xs font-mono" style={{ color: 'var(--text-secondary)' }}>
                  pre-call authorization
                </span>
                {result.phase_a && <StatusBadge status={result.phase_a.result} />}
              </div>
              {(result.phase_a?.gates_evaluated?.length ?? 0) > 0 && (
                <ul className="text-xs font-mono space-y-0.5 mb-2">
                  {result.phase_a!.gates_evaluated.map((g, i) => (
                    <li key={i} style={{ color: 'var(--text-secondary)' }}>→ {g}</li>
                  ))}
                </ul>
              )}
              {result.phase_a?.blocked && (
                <p className="text-xs mt-1" style={{ color: IBM_COLORS.red40 }}>
                  call blocked — Phase B not reached
                </p>
              )}
            </div>

            {/* Phase B */}
            <div
              className="rounded border p-3"
              style={{
                borderColor: 'var(--border-ui)',
                opacity: result.phase_b ? 1 : 0.4,
              }}
            >
              <div className="flex items-center gap-2 mb-2">
                <span className="text-xs font-semibold uppercase" style={{ color: IBM_COLORS.red40 }}>
                  Phase B
                </span>
                <span className="text-xs font-mono" style={{ color: 'var(--text-secondary)' }}>
                  post-output validation
                </span>
                {result.phase_b && <StatusBadge status={result.phase_b.result} />}
              </div>
              {result.phase_b ? (
                <>
                  {result.phase_b.gates_evaluated?.length > 0 && (
                    <ul className="text-xs font-mono space-y-0.5">
                      {result.phase_b.gates_evaluated.map((g, i) => (
                        <li key={i} style={{ color: 'var(--text-secondary)' }}>→ {g}</li>
                      ))}
                    </ul>
                  )}
                </>
              ) : (
                <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                  not reached — token cost avoided
                </p>
              )}
            </div>
          </div>

          <div className="flex items-center gap-2 text-sm">
            <span className="font-mono text-xs" style={{ color: 'var(--text-secondary)' }}>
              combined result:
            </span>
            <StatusBadge status={result.combined_result} />
            <span className="font-mono text-xs" style={{ color: 'var(--text-secondary)' }}>
              enforcement_mode: {result.artifact?.metadata?.enforcement_mode ?? '—'}
            </span>
          </div>
        </>
      )}
    </div>
  )
}
