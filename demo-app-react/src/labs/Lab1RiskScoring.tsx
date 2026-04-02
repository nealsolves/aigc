import { useState } from 'react'
import MetricCard from '@/components/shared/MetricCard'
import RiskGauge from '@/components/shared/RiskGauge'
import SignalBar from '@/components/shared/SignalBar'
import StatusBadge from '@/components/shared/StatusBadge'
import { useApi } from '@/hooks/useApi'
import { IBM_COLORS } from '@/theme/tokens'
import type { Artifact } from '@/types/artifact'

const SCENARIOS = [
  { key: 'low_risk_faq',              label: 'Low Risk: Simple FAQ',        mode_hint: 'warn_only'   },
  { key: 'medium_risk_medical',       label: 'Medium Risk: Medical Advice', mode_hint: 'risk_scored' },
  { key: 'high_risk_drug_interaction', label: 'High Risk: Drug Interaction', mode_hint: 'strict'     },
]
const MODES = ['strict', 'risk_scored', 'warn_only']

const SIGNAL_COLORS: Record<string, string> = {
  no_output_schema: IBM_COLORS.purple40,
  broad_roles:      IBM_COLORS.cyan30,
  missing_guards:   IBM_COLORS.magenta40,
  external_model:   IBM_COLORS.blue40,
  no_preconditions: IBM_COLORS.teal30,
}

interface EnforceResponse { artifact: Artifact; error: string | null }

export default function Lab1RiskScoring() {
  const [scenarioIdx, setScenarioIdx] = useState(1)
  const [mode, setMode] = useState('risk_scored')
  const [artifact, setArtifact] = useState<Artifact | null>(null)
  const { call, loading, error: apiError } = useApi<EnforceResponse>()

  const run = async () => {
    const res = await call('/api/enforce', {
      scenario_key: SCENARIOS[scenarioIdx].key,
      mode,
    })
    if (res) setArtifact(res.artifact)
  }

  const risk = artifact?.metadata?.risk_scoring
  const factors = risk?.basis ?? []

  return (
    <div className="p-4 max-w-4xl mx-auto">
      <p className="font-mono text-xs mb-4" style={{ color: 'var(--text-secondary)' }}>
        // evaluate invocation risk across signal dimensions
      </p>

      <div className="grid grid-cols-2 gap-4 mb-4">
        <div>
          <div className="font-mono text-xs mb-2" style={{ color: 'var(--text-secondary)' }}>↳ Preset Scenario</div>
          <div className="flex flex-col gap-1">
            {SCENARIOS.map((s, i) => (
              <button
                key={s.key}
                onClick={() => { setScenarioIdx(i); setArtifact(null) }}
                className="text-left font-mono text-[13px] px-3 py-2 rounded transition-colors"
                style={
                  scenarioIdx === i
                    ? { background: 'rgba(15,98,254,0.18)', color: 'var(--ibm-cyan-30)', border: '1px solid rgba(15,98,254,0.3)' }
                    : { color: 'var(--text-secondary)', border: '1px solid var(--border-ui)', background: 'var(--bg-surface)' }
                }
              >
                {s.label}
              </button>
            ))}
          </div>
        </div>

        <div>
          <div className="font-mono text-xs mb-2" style={{ color: 'var(--text-secondary)' }}>↳ Risk Mode</div>
          <div className="flex flex-col gap-1 mb-3">
            {MODES.map(m => (
              <button
                key={m}
                onClick={() => { setMode(m); setArtifact(null) }}
                className="text-left font-mono text-[13px] px-3 py-2 rounded transition-colors"
                style={
                  mode === m
                    ? { background: 'rgba(15,98,254,0.18)', color: 'var(--ibm-cyan-30)', border: '1px solid rgba(15,98,254,0.3)' }
                    : { color: 'var(--text-secondary)', border: '1px solid var(--border-ui)', background: 'var(--bg-surface)' }
                }
              >
                {m}
              </button>
            ))}
          </div>
          <button
            onClick={run}
            disabled={loading}
            className="w-full font-mono text-sm py-2 rounded transition-colors"
            style={{ background: 'var(--ibm-blue-60)', color: '#fff', opacity: loading ? 0.7 : 1 }}
          >
            {loading ? 'Running…' : 'Run Enforcement →'}
          </button>
        </div>
      </div>

      {apiError && (
        <div className="font-mono text-xs px-3 py-2 rounded mb-3" style={{ background: 'rgba(255,126,182,0.08)', border: '1px solid rgba(255,126,182,0.2)', color: 'var(--ibm-magenta-40)' }}>
          // API error: {apiError}
        </div>
      )}

      {artifact ? (
        <div className="space-y-3">
          <div className="grid grid-cols-3 gap-2">
            <MetricCard value={(risk?.score ?? 0).toFixed(2)} label="RISK SCORE" color={(risk?.score ?? 0) > (risk?.threshold ?? 0.7) ? 'var(--ibm-magenta-40)' : 'var(--ibm-blue-40)'} />
            <MetricCard value={mode.toUpperCase()} label="MODE" color="var(--ibm-purple-40)" />
            <MetricCard value={(risk?.threshold ?? 0.7).toFixed(2)} label="THRESHOLD" color="var(--ibm-teal-60)" />
          </div>

          <div className="flex items-center gap-2">
            <StatusBadge status={artifact.enforcement_result} />
            <span className="font-mono text-sm" style={{ color: 'var(--text-secondary)' }}>
              — {artifact.enforcement_result === 'PASS' ? 'policy check passed' : 'policy check failed'}
            </span>
          </div>

          {risk && <RiskGauge score={risk.score} threshold={risk.threshold} />}

          {factors.length > 0 && (
            <div className="rounded p-3" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-ui)' }}>
              <div className="font-mono text-xs mb-2" style={{ color: 'var(--text-secondary)' }}>// signal breakdown</div>
              {factors.map(f => (
                <SignalBar
                  key={f.name}
                  name={f.name}
                  contribution={f.contribution ?? 0}
                  color={SIGNAL_COLORS[f.name] ?? 'var(--ibm-blue-60)'}
                />
              ))}
            </div>
          )}
        </div>
      ) : (
        <div className="font-mono text-xs px-3 py-2 rounded" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-ui)', color: 'var(--text-secondary)' }}>
          // run enforcement to see results
        </div>
      )}
    </div>
  )
}
