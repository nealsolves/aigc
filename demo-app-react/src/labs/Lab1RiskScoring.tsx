import { useState, useEffect } from 'react'
import MetricCard from '@/components/shared/MetricCard'
import RiskGauge from '@/components/shared/RiskGauge'
import SignalBar from '@/components/shared/SignalBar'
import StatusBadge from '@/components/shared/StatusBadge'
import { useApi } from '@/hooks/useApi'
import { IBM_COLORS } from '@/theme/tokens'
import type { Artifact } from '@/types/artifact'

type RiskMode = 'strict' | 'risk_scored' | 'warn_only'
type EnforcementFlow = 'unified' | 'split'

const SCENARIOS = [
  { key: 'low_risk_faq',               label: 'Low Risk: Simple FAQ',               flowHint: 'unified' as const },
  { key: 'medium_risk_medical',        label: 'Medium Risk: Medical Advice',        flowHint: 'unified' as const },
  { key: 'high_risk_drug_interaction', label: 'High Risk: Drug Interaction',        flowHint: 'unified' as const },
  { key: 'split_precall_block',        label: 'Split Demo: Missing Role Declaration', flowHint: 'split' as const },
]
const MODES: RiskMode[] = ['strict', 'risk_scored', 'warn_only']
const FLOWS: { key: EnforcementFlow; label: string; hint: string }[] = [
  { key: 'unified', label: 'Unified', hint: 'One enforcement call with output present up front.' },
  { key: 'split', label: 'Split', hint: 'Phase A authorizes before the model call; Phase B validates after output exists.' },
]

const SIGNAL_COLORS: Record<string, string> = {
  no_output_schema: IBM_COLORS.purple40,
  broad_roles:      IBM_COLORS.cyan30,
  missing_guards:   IBM_COLORS.magenta40,
  external_model:   IBM_COLORS.blue40,
  no_preconditions: IBM_COLORS.teal30,
}

interface ScenarioDetail {
  prompt: string
  context: Record<string, unknown>
  policy: string
  model_provider: string
  model_id: string
  role: string
}

interface EnforceResponse { artifact: Artifact | null; error: string | null }

function readGateList(value: unknown): string[] {
  if (!Array.isArray(value)) return []
  return value.map(v => String(v))
}

function scenarioRequiresSplit(flowHint: 'unified' | 'split'): boolean {
  return flowHint === 'split'
}

export default function Lab1RiskScoring() {
  const [scenarioIdx,     setScenarioIdx]     = useState(1)
  const [mode,            setMode]            = useState<RiskMode>('risk_scored')
  const [flow,            setFlow]            = useState<EnforcementFlow>('split')
  const [artifact,        setArtifact]        = useState<Artifact | null>(null)
  const [scenarioDetail,  setScenarioDetail]  = useState<ScenarioDetail | null>(null)

  const { call,             loading, error: apiError } = useApi<EnforceResponse>()
  const { call: callDetail                            } = useApi<ScenarioDetail>()

  // Load scenario detail whenever the selected scenario changes
  useEffect(() => {
    let cancelled = false
    const key = SCENARIOS[scenarioIdx].key
    callDetail(`/api/scenarios/${key}`).then(res => {
      if (!cancelled && res) setScenarioDetail(res)
    })
    setArtifact(null)
    return () => { cancelled = true }
  }, [scenarioIdx]) // eslint-disable-line react-hooks/exhaustive-deps

  const run = async () => {
    const res = await call('/api/enforce', {
      scenario_key: SCENARIOS[scenarioIdx].key,
      mode,
      flow,
    })
    if (res) setArtifact(res.artifact ?? null)
  }

  const risk = artifact?.metadata?.risk_scoring
  const factors = risk?.basis ?? []
  const enforcementMode = typeof artifact?.metadata?.enforcement_mode === 'string'
    ? artifact.metadata.enforcement_mode
    : null
  const preCallGates = readGateList(artifact?.metadata?.pre_call_gates_evaluated)
  const postCallGates = readGateList(artifact?.metadata?.post_call_gates_evaluated)
  const phaseABlocked = enforcementMode === 'split_pre_call_only'
  const selectedScenario = SCENARIOS[scenarioIdx]
  const flowLockedToSplit = scenarioRequiresSplit(selectedScenario.flowHint)

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
                onClick={() => {
                  setScenarioIdx(i)
                  setFlow(scenarioRequiresSplit(s.flowHint) ? 'split' : 'unified')
                  setArtifact(null)
                }}
                className="text-left font-mono text-[13px] px-3 py-2 rounded transition-colors"
                style={
                  scenarioIdx === i
                    ? { background: 'rgba(15,98,254,0.18)', color: 'var(--ibm-cyan-30)', border: '1px solid rgba(15,98,254,0.3)' }
                    : { color: 'var(--text-secondary)', border: '1px solid var(--border-ui)', background: 'var(--bg-surface)' }
                }
              >
                {s.label}
                {s.flowHint === 'split' && (
                  <span className="ml-2 text-[10px]" style={{ color: 'var(--ibm-cyan-30)' }}>
                    split demo
                  </span>
                )}
              </button>
            ))}
          </div>

          {/* Scenario context panel */}
          {scenarioDetail && (
            <div className="mt-3 rounded p-3 space-y-1" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-ui)' }}>
              <div className="font-mono text-[11px]" style={{ color: 'var(--text-secondary)' }}>// scenario context</div>
              <div className="font-mono text-[11px]">
                <span style={{ color: 'var(--text-secondary)' }}>prompt: </span>
                <span style={{ color: 'var(--text-primary)' }}>&ldquo;{scenarioDetail.prompt}&rdquo;</span>
              </div>
              <div className="font-mono text-[11px]">
                <span style={{ color: 'var(--text-secondary)' }}>policy: </span>
                <span style={{ color: 'var(--ibm-cyan-30)' }}>{scenarioDetail.policy}</span>
              </div>
              <div className="font-mono text-[11px]">
                <span style={{ color: 'var(--text-secondary)' }}>model: </span>
                <span style={{ color: 'var(--ibm-blue-40)' }}>{scenarioDetail.model_provider}/{scenarioDetail.model_id}</span>
              </div>
              <div className="font-mono text-[11px]">
                <span style={{ color: 'var(--text-secondary)' }}>role: </span>
                <span style={{ color: 'var(--ibm-purple-40)' }}>{scenarioDetail.role}</span>
              </div>
              {Object.entries(scenarioDetail.context).map(([k, v]) => (
                <div key={k} className="font-mono text-[11px]">
                  <span style={{ color: 'var(--text-secondary)' }}>{k}: </span>
                  <span style={{ color: String(v) === 'true' ? 'var(--ibm-teal-30)' : String(v) === 'false' ? 'var(--ibm-magenta-40)' : 'var(--text-primary)' }}>
                    {String(v)}
                  </span>
                </div>
              ))}
            </div>
          )}
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
          <div className="font-mono text-xs mb-2" style={{ color: 'var(--text-secondary)' }}>↳ Enforcement Flow</div>
          <div className="flex flex-col gap-1 mb-3">
            {FLOWS.map(option => (
              (() => {
                const isDisabled = flowLockedToSplit && option.key === 'unified'
                return (
              <button
                key={option.key}
                onClick={() => {
                  if (isDisabled) return
                  setFlow(option.key)
                  setArtifact(null)
                }}
                disabled={isDisabled}
                aria-disabled={isDisabled}
                className="text-left font-mono text-[13px] px-3 py-2 rounded transition-colors"
                style={
                  isDisabled
                    ? { color: 'var(--text-secondary)', border: '1px solid var(--border-ui)', background: 'var(--bg-surface)', opacity: 0.45, cursor: 'not-allowed' }
                    : flow === option.key
                      ? { background: 'rgba(15,98,254,0.18)', color: 'var(--ibm-cyan-30)', border: '1px solid rgba(15,98,254,0.3)' }
                      : { color: 'var(--text-secondary)', border: '1px solid var(--border-ui)', background: 'var(--bg-surface)' }
                }
              >
                <div>{option.label}</div>
                <div className="text-[11px]" style={{ color: !isDisabled && flow === option.key ? 'var(--ibm-cyan-30)' : 'var(--text-secondary)' }}>
                  {option.hint}
                </div>
                {isDisabled && (
                  <div className="text-[10px]" style={{ color: 'var(--ibm-magenta-40)' }}>
                    disabled for split demo scenario
                  </div>
                )}
              </button>
                )
              })()
            ))}
          </div>
          {selectedScenario.flowHint === 'split' && (
            <div className="font-mono text-[11px] px-3 py-2 rounded mb-3" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-ui)', color: 'var(--text-secondary)' }}>
              // this scenario is locked to Split so the demo always shows a Phase A block before the model call
            </div>
          )}
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
          <div className="grid grid-cols-4 gap-2">
            <MetricCard value={risk ? risk.score.toFixed(2) : '—'} label="RISK SCORE" color={risk && risk.score > (risk.threshold ?? 0.7) ? 'var(--ibm-magenta-40)' : 'var(--ibm-blue-40)'} />
            <MetricCard value={mode.toUpperCase()} label="MODE" color="var(--ibm-purple-40)" />
            <MetricCard value={flow.toUpperCase()} label="FLOW" color="var(--ibm-cyan-30)" />
            <MetricCard value={(enforcementMode ?? '—').toUpperCase()} label="ARTIFACT MODE" color="var(--ibm-teal-60)" />
          </div>

          <div className="flex items-center gap-2">
            <StatusBadge status={artifact.enforcement_result} />
            <span className="font-mono text-sm" style={{ color: 'var(--text-secondary)' }}>
              — {phaseABlocked
                ? 'Phase A blocked before the model call'
                : enforcementMode === 'split'
                  ? 'split enforcement completed across Phase A and Phase B'
                  : artifact.enforcement_result === 'PASS'
                    ? 'policy check passed'
                    : 'policy check failed'}
            </span>
          </div>

          {risk && (
            <div className="font-mono text-[11px]" style={{ color: 'var(--text-secondary)' }}>
              threshold: {risk.threshold.toFixed(2)}
            </div>
          )}

          {risk && <RiskGauge score={risk.score} threshold={risk.threshold} />}

          {(flow === 'split' || enforcementMode?.startsWith('split')) && (
            <div className="rounded p-3" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-ui)' }}>
              <div className="font-mono text-xs mb-2" style={{ color: 'var(--text-secondary)' }}>// split boundary evidence</div>
              <div className="font-mono text-[11px] mb-2">
                <span style={{ color: 'var(--text-secondary)' }}>enforcement_mode: </span>
                <span style={{ color: 'var(--ibm-cyan-30)' }}>{enforcementMode ?? 'unknown'}</span>
              </div>
              {phaseABlocked && (
                <div className="font-mono text-[11px] mb-2" style={{ color: 'var(--ibm-magenta-40)' }}>
                  // model output was never consumed because Phase A failed
                </div>
              )}
              {preCallGates.length > 0 && (
                <div className="mb-2">
                  <div className="font-mono text-[11px] mb-1" style={{ color: 'var(--text-secondary)' }}>Phase A gates</div>
                  <div className="flex flex-wrap gap-2">
                    {preCallGates.map(gate => (
                      <span key={gate} className="font-mono text-[11px] px-2 py-0.5 rounded" style={{ color: 'var(--ibm-blue-40)', border: '1px solid var(--border-ui)' }}>
                        {gate}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              {postCallGates.length > 0 && (
                <div>
                  <div className="font-mono text-[11px] mb-1" style={{ color: 'var(--text-secondary)' }}>Phase B gates</div>
                  <div className="flex flex-wrap gap-2">
                    {postCallGates.map(gate => (
                      <span key={gate} className="font-mono text-[11px] px-2 py-0.5 rounded" style={{ color: 'var(--ibm-teal-30)', border: '1px solid var(--border-ui)' }}>
                        {gate}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

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
          // run enforcement to compare unified vs split behavior
        </div>
      )}
    </div>
  )
}
