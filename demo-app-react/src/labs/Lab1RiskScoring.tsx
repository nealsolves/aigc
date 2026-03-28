import { useState } from 'react'
import MetricCard from '@/components/shared/MetricCard'
import RiskGauge from '@/components/shared/RiskGauge'
import SignalBar from '@/components/shared/SignalBar'
import StatusBadge from '@/components/shared/StatusBadge'
import { getScenario } from '@/mock/scenarios'
import { evaluateRisk, MEDICAL_FACTORS, type RiskMode } from '@/mock/riskEngine'
import { IBM_COLORS } from '@/theme/tokens'

const SCENARIOS = [
  { key: 'low_risk_faq',             label: 'Low Risk: Simple FAQ',          factorSet: 'low_risk',    desc: 'Well-configured policy, internal model. Expected score ≈ 0.00.' },
  { key: 'medium_risk_medical',      label: 'Medium Risk: Medical Advice',   factorSet: 'medium_risk', desc: 'Standard policy: broad_roles, missing_guards, external_model. Expected score ≈ 0.65.' },
  { key: 'high_risk_drug_interaction', label: 'High Risk: Drug Interaction', factorSet: 'high_risk',   desc: 'Loose policy: all 5 factors trigger. Expected score ≈ 1.00.' },
]

const MODES: RiskMode[] = ['strict', 'risk_scored', 'warn_only']
const SIGNAL_COLORS: Record<string, string> = {
  no_output_schema: IBM_COLORS.purple40,
  broad_roles:      IBM_COLORS.cyan30,
  missing_guards:   IBM_COLORS.magenta40,
  external_model:   IBM_COLORS.blue40,
  no_preconditions: IBM_COLORS.teal30,
}

export default function Lab1RiskScoring() {
  const [scenarioIdx, setScenarioIdx] = useState(1)
  const [mode, setMode] = useState<RiskMode>('risk_scored')
  const [result, setResult] = useState<ReturnType<typeof evaluateRisk> | null>(null)

  const selected = SCENARIOS[scenarioIdx]
  const scenario = getScenario(selected.key)

  const run = () => {
    const factors = MEDICAL_FACTORS[selected.factorSet]
    setResult(evaluateRisk(factors, 0.7, mode))
  }

  return (
    <div className="p-4 max-w-4xl mx-auto">
      <p className="font-mono text-[9px] mb-4" style={{ color: 'var(--text-secondary)' }}>
        // evaluate invocation risk across signal dimensions
      </p>

      {/* controls */}
      <div className="grid grid-cols-2 gap-4 mb-4">
        <div>
          <div className="font-mono text-[9px] mb-2" style={{ color: 'var(--text-secondary)' }}>↳ Preset Scenario</div>
          <div className="flex flex-col gap-1">
            {SCENARIOS.map((s, i) => (
              <button
                key={s.key}
                onClick={() => { setScenarioIdx(i); setResult(null) }}
                className="text-left font-mono text-[10px] px-3 py-2 rounded transition-colors"
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
          <div className="font-mono text-[9px] mb-2" style={{ color: 'var(--text-secondary)' }}>↳ Risk Mode</div>
          <div className="flex flex-col gap-1 mb-3">
            {MODES.map(m => (
              <button
                key={m}
                onClick={() => { setMode(m); setResult(null) }}
                className="text-left font-mono text-[10px] px-3 py-2 rounded transition-colors"
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
            className="w-full font-mono text-[11px] py-2 rounded transition-colors"
            style={{ background: 'var(--ibm-blue-60)', color: '#fff' }}
          >
            Run Enforcement →
          </button>
        </div>
      </div>

      {/* scenario description */}
      <div className="font-mono text-[9px] px-3 py-2 rounded mb-4" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-ui)', color: 'var(--text-secondary)' }}>
        {selected.desc}
      </div>

      {/* prompt preview */}
      <div className="font-mono text-[9px] mb-4" style={{ color: 'var(--text-secondary)' }}>
        <span style={{ color: 'var(--ibm-blue-60)' }}>↳ prompt: </span>
        <span style={{ color: 'var(--text-primary)' }}>{scenario.prompt}</span>
      </div>

      {/* results */}
      {result ? (
        <div className="space-y-3">
          <div className="grid grid-cols-3 gap-2">
            <MetricCard value={result.score.toFixed(2)} label="RISK SCORE"  color={result.breached ? 'var(--ibm-magenta-40)' : 'var(--ibm-blue-40)'} />
            <MetricCard value={mode.toUpperCase()}       label="MODE"        color="var(--ibm-purple-40)" />
            <MetricCard value={result.threshold.toFixed(2)} label="THRESHOLD" color="var(--ibm-teal-60)" />
          </div>

          <div className="flex items-center gap-2">
            <StatusBadge status={result.enforcement} />
            <span className="font-mono text-[9px]" style={{ color: 'var(--text-secondary)' }}>
              {result.enforcement === 'FAIL' ? '— governance violation detected' : '— all governance rules satisfied'}
            </span>
          </div>

          <RiskGauge score={result.score} threshold={result.threshold} />

          <div className="rounded p-3" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-ui)' }}>
            <div className="font-mono text-[9px] mb-2" style={{ color: 'var(--text-secondary)' }}>// signal breakdown</div>
            {result.factors.map(f => (
              <SignalBar
                key={f.name}
                name={f.name}
                contribution={f.contribution ?? 0}
                color={SIGNAL_COLORS[f.name] ?? 'var(--ibm-blue-60)'}
              />
            ))}
          </div>
        </div>
      ) : (
        <div className="font-mono text-[9px] px-3 py-2 rounded" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-ui)', color: 'var(--text-secondary)' }}>
          // run enforcement to see results
        </div>
      )}
    </div>
  )
}
