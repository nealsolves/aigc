import { useState, useEffect, useRef } from 'react'
import StatusBadge from '@/components/shared/StatusBadge'
import CodeBlock from '@/components/shared/CodeBlock'
import { useApi } from '@/hooks/useApi'
import { IBM_COLORS } from '@/theme/tokens'
import type { Artifact } from '@/types/artifact'

interface GateInfo {
  name: string
  insertion_point: string
  description: string
  source: string
}

interface GateResult {
  name: string
  insertion_point: string
  passed: boolean
  failures: Array<{ gate: string; message: string }>
  metadata: Record<string, unknown>
}

interface GateRunResponse {
  artifact: Artifact | null
  gate_result: GateResult | null
  error: string | null
}

type GateName =
  | 'session_authorization_gate'
  | 'domain_allowlist_gate'
  | 'confidence_gate'
  | 'response_length_gate'
  | 'pii_detection_gate'
  | 'audit_metadata_gate'

const GATE_CONFIG: Record<GateName, { scenarios: Array<{ key: string; label: string }> }> = {
  session_authorization_gate: {
    scenarios: [
      { key: 'gate_authorized_session', label: 'Authorized Session' },
      { key: 'gate_unauthorized_session', label: 'Unauthorized Session' },
    ],
  },
  domain_allowlist_gate: {
    scenarios: [
      { key: 'gate_allowed_domain', label: 'Allowed Domain' },
      { key: 'gate_untrusted_domain', label: 'Untrusted Domain' },
    ],
  },
  confidence_gate: {
    scenarios: [
      { key: 'gate_high_confidence', label: 'High Confidence' },
      { key: 'gate_low_confidence', label: 'Low Confidence' },
    ],
  },
  response_length_gate: {
    scenarios: [
      { key: 'gate_clean_output', label: 'Short Output' },
      { key: 'gate_long_response', label: 'Long Output' },
    ],
  },
  pii_detection_gate: {
    scenarios: [
      { key: 'gate_clean_output', label: 'Clean Output' },
      { key: 'gate_pii_present', label: 'PII Present' },
    ],
  },
  audit_metadata_gate: {
    scenarios: [
      { key: 'gate_clean_output', label: 'Metadata Injection' },
    ],
  },
}

const GATE_NAMES = Object.keys(GATE_CONFIG) as GateName[]

const PIPELINE_PHASES = [
  'pre_authorization',
  'post_authorization',
  'pre_output',
  'post_output',
] as const

const PHASE_COLORS: Record<string, string> = {
  pre_authorization:  IBM_COLORS.blue40,
  post_authorization: IBM_COLORS.purple40,
  pre_output:         IBM_COLORS.teal30,
  post_output:        IBM_COLORS.cyan30,
}

export default function Lab6CustomGates() {
  const [gateName,    setGateName]    = useState<GateName>('session_authorization_gate')
  const gateNameRef = useRef<GateName>('session_authorization_gate')
  const [scenarioKey, setScenarioKey] = useState(GATE_CONFIG.session_authorization_gate.scenarios[0].key)
  const [gateInfo,    setGateInfo]    = useState<GateInfo | null>(null)
  const [showSource,  setShowSource]  = useState(false)
  const [runResult,   setRunResult]   = useState<GateRunResponse | null>(null)

  const { call: callInfo } = useApi<GateInfo>()
  const { call: callRun,  loading: loadingRun  } = useApi<GateRunResponse>()

  const loadGateInfo = async (name: GateName) => {
    const res = await callInfo(`/api/gate/${name}`)
    if (res && gateNameRef.current === name) setGateInfo(res)
  }

  // Auto-load gate info on mount for the default gate
  useEffect(() => {
    loadGateInfo(gateName)
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const run = async () => {
    const res = await callRun('/api/gate/run', { gate_name: gateName, scenario_key: scenarioKey })
    if (res) setRunResult(res)
  }

  const selectGate = (name: GateName) => {
    gateNameRef.current = name
    setGateName(name)
    setScenarioKey(GATE_CONFIG[name].scenarios[0].key)
    setRunResult(null)
    loadGateInfo(name)
  }

  const gatesEvaluated: string[] = runResult?.artifact?.metadata?.gates_evaluated ?? []
  const activeScenarios = GATE_CONFIG[gateName].scenarios

  return (
    <div className="p-4 max-w-4xl mx-auto">
      <p className="font-mono text-xs mb-4" style={{ color: 'var(--text-secondary)' }}>
        // custom enforcement gate plugins — four insertion points in the pipeline
      </p>

      {/* Gate selector */}
      <div className="mb-3">
        <div className="font-mono text-xs mb-2" style={{ color: 'var(--text-secondary)' }}>↳ Select Gate</div>
        <div className="flex gap-2 flex-wrap">
          {GATE_NAMES.map(name => (
            <button
              key={name}
              onClick={() => selectGate(name)}
              className="font-mono text-xs px-3 py-1.5 rounded"
              style={
                gateName === name
                  ? { background: 'rgba(15,98,254,0.18)', color: 'var(--ibm-cyan-30)', border: '1px solid rgba(15,98,254,0.3)' }
                  : { color: 'var(--text-secondary)', border: '1px solid var(--border-ui)' }
              }
            >
              {name}
            </button>
          ))}
        </div>
      </div>

      {/* Gate info */}
      {gateInfo && (
        <div className="rounded p-3 mb-3" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-ui)' }}>
          <div className="flex items-center gap-2 mb-1">
            <span className="font-mono text-xs" style={{ color: 'var(--ibm-cyan-30)' }}>{gateInfo.name}</span>
            <span className="font-mono text-[11px] px-2 py-0.5 rounded" style={{ background: 'rgba(15,98,254,0.1)', color: PHASE_COLORS[gateInfo.insertion_point] ?? 'var(--text-secondary)' }}>
              {gateInfo.insertion_point}
            </span>
          </div>
          <div className="font-mono text-[11px]" style={{ color: 'var(--text-secondary)' }}>{gateInfo.description}</div>

          {/* Pipeline visualization */}
          <div className="mt-3 mb-1">
            <div className="font-mono text-[11px] mb-1" style={{ color: 'var(--text-secondary)' }}>// pipeline insertion point</div>
            <div className="flex items-center gap-1">
              {PIPELINE_PHASES.map((phase, i) => {
                const isActive = phase === gateInfo.insertion_point
                return (
                  <div key={phase} className="flex items-center gap-1">
                    <div
                      className="font-mono text-[10px] px-2 py-1 rounded"
                      style={{
                        background: isActive ? `${PHASE_COLORS[phase]}22` : 'var(--bg-base)',
                        border: `1px solid ${isActive ? PHASE_COLORS[phase] : 'var(--border-ui)'}`,
                        color: isActive ? PHASE_COLORS[phase] : 'var(--text-secondary)',
                        fontWeight: isActive ? 600 : 400,
                      }}
                    >
                      {phase}
                    </div>
                    {i < PIPELINE_PHASES.length - 1 && (
                      <span className="font-mono text-[10px]" style={{ color: 'var(--text-secondary)' }}>→</span>
                    )}
                  </div>
                )
              })}
            </div>
          </div>

          <button
            onClick={() => setShowSource(s => !s)}
            className="font-mono text-[11px] mt-2"
            style={{ color: 'var(--ibm-blue-60)' }}
          >
            {showSource ? '▲ hide source' : '▼ show source'}
          </button>
          {showSource && <div className="mt-2"><CodeBlock code={gateInfo.source} label={`${gateInfo.name}.py`} /></div>}
        </div>
      )}

      {/* Scenario selector + run */}
      <div className="flex gap-2 mb-4 flex-wrap">
        {activeScenarios.map(s => (
          <button
            key={s.key}
            onClick={() => { setScenarioKey(s.key); setRunResult(null) }}
            className="font-mono text-xs px-3 py-1.5 rounded"
            style={
              scenarioKey === s.key
                ? { background: 'rgba(15,98,254,0.18)', color: 'var(--ibm-cyan-30)', border: '1px solid rgba(15,98,254,0.3)' }
                : { color: 'var(--text-secondary)', border: '1px solid var(--border-ui)' }
            }
              >
                {s.label}
              </button>
        ))}
        <button
          onClick={run}
          disabled={loadingRun}
          className="font-mono text-sm px-4 py-1.5 rounded ml-auto"
          style={{ background: 'var(--ibm-blue-60)', color: '#fff', opacity: loadingRun ? 0.7 : 1 }}
        >
          {loadingRun ? 'Running…' : 'Run Gate →'}
        </button>
      </div>

      {runResult && runResult.gate_result && (
        <div className="space-y-3">
          {/* Gate result */}
          <div className="flex items-center gap-2">
            <StatusBadge status={runResult.gate_result.passed ? 'PASS' : 'FAIL'} />
            <span className="font-mono text-xs" style={{ color: 'var(--text-secondary)' }}>
              {runResult.gate_result.name} @ {runResult.gate_result.insertion_point}
            </span>
          </div>

          {runResult.gate_result.failures.length > 0 && (
            <div className="rounded p-2" style={{ background: 'rgba(255,126,182,0.08)', border: '1px solid rgba(255,126,182,0.2)' }}>
              {runResult.gate_result.failures.map((f, i) => (
                <div key={i} className="font-mono text-xs" style={{ color: 'var(--ibm-magenta-40)' }}>// {f.message}</div>
              ))}
            </div>
          )}

          {Object.keys(runResult.gate_result.metadata).length > 0 && (
            <div className="rounded p-2" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-ui)' }}>
              <div className="font-mono text-[11px] mb-1" style={{ color: 'var(--text-secondary)' }}>gate metadata</div>
              {Object.entries(runResult.gate_result.metadata).map(([k, v]) => (
                <div key={k} className="font-mono text-xs">
                  <span style={{ color: 'var(--text-secondary)' }}>{k}: </span>
                  <span style={{ color: 'var(--ibm-cyan-30)' }}>{String(v)}</span>
                </div>
              ))}
            </div>
          )}

          {/* gates_evaluated from full artifact */}
          {gatesEvaluated.length > 0 && (
            <div className="rounded p-2" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-ui)' }}>
              <div className="font-mono text-[11px] mb-2" style={{ color: 'var(--text-secondary)' }}>// gates_evaluated (artifact metadata)</div>
              <div className="flex flex-col gap-1">
                {gatesEvaluated.map((gid, i) => {
                  const isCustom = gid === `custom:${gateName}`
                  return (
                    <div key={i} className="flex items-center gap-2">
                      <span className="font-mono text-[11px]" style={{ color: 'var(--text-secondary)' }}>{i + 1}.</span>
                      <span
                        className="font-mono text-[11px] px-2 py-0.5 rounded"
                        style={{
                          background: isCustom ? 'rgba(15,98,254,0.15)' : 'transparent',
                          color: isCustom ? 'var(--ibm-cyan-30)' : 'var(--text-secondary)',
                          border: isCustom ? '1px solid rgba(15,98,254,0.3)' : 'none',
                        }}
                      >
                        {gid}
                      </span>
                      {isCustom && (
                        <span className="font-mono text-[10px]" style={{ color: 'var(--ibm-cyan-30)' }}>← selected gate</span>
                      )}
                    </div>
                  )
                })}
              </div>
            </div>
          )}
        </div>
      )}

      {!runResult && !loadingRun && (
        <div className="font-mono text-xs px-3 py-2 rounded" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-ui)', color: 'var(--text-secondary)' }}>
          // select a scenario and run to see gate evaluation
        </div>
      )}
    </div>
  )
}
