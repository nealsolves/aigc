import { useState } from 'react'
import StatusBadge from '@/components/shared/StatusBadge'
import SignalBar from '@/components/shared/SignalBar'
import CodeBlock from '@/components/shared/CodeBlock'
import { getScenario } from '@/mock/scenarios'
import { IBM_COLORS } from '@/theme/tokens'

interface Gate {
  name: string
  phase: 'pre_authorization' | 'post_authorization' | 'pre_output' | 'post_output'
  result: 'PASS' | 'FAIL' | 'WARN'
  detail: string
}

function evaluateGates(scenarioKey: string): Gate[] {
  const s = getScenario(scenarioKey)
  const hasPii = s.output.result.includes('SSN') || s.output.result.includes('@')
  const confidence = (s.output as { confidence?: number }).confidence ?? 1
  return [
    { name: 'RoleAuthGate',       phase: 'pre_authorization',  result: 'PASS', detail: 'role=doctor, authorized' },
    { name: 'PreconditionGate',   phase: 'pre_authorization',  result: 'PASS', detail: 'all preconditions met' },
    { name: 'SchemaGate',         phase: 'post_authorization', result: 'PASS', detail: 'output schema validated' },
    { name: 'PiiDetectionGate',   phase: 'pre_output',         result: hasPii ? 'FAIL' : 'PASS', detail: hasPii ? 'PII detected — SSN/email found' : 'no PII detected' },
    { name: 'ConfidenceGate',     phase: 'pre_output',         result: confidence < 0.5 ? 'WARN' : 'PASS', detail: `confidence=${confidence.toFixed(2)}` },
    { name: 'AuditRecorderGate',  phase: 'post_output',        result: 'PASS', detail: 'audit artifact persisted' },
  ]
}

const GATE_SCENARIOS = [
  { key: 'gate_high_confidence', label: 'High Confidence' },
  { key: 'gate_low_confidence',  label: 'Low Confidence' },
  { key: 'gate_pii_present',     label: 'PII Present' },
  { key: 'gate_clean_output',    label: 'Clean Output' },
]

const PHASE_COLORS: Record<string, string> = {
  pre_authorization:  IBM_COLORS.blue40,
  post_authorization: IBM_COLORS.purple40,
  pre_output:         IBM_COLORS.teal30,
  post_output:        IBM_COLORS.cyan30,
}

export default function Lab6CustomGates() {
  const [scenarioKey, setScenarioKey] = useState('gate_high_confidence')
  const [gates, setGates] = useState<Gate[] | null>(null)

  const run = () => setGates(evaluateGates(scenarioKey))

  const overallStatus = gates
    ? gates.some(g => g.result === 'FAIL') ? 'FAIL' : gates.some(g => g.result === 'WARN') ? 'WARN' : 'PASS'
    : null

  return (
    <div className="p-4 max-w-4xl mx-auto">
      <p className="font-mono text-[9px] mb-4" style={{ color: 'var(--text-secondary)' }}>
        // custom enforcement gate plugins — four insertion points in the pipeline
      </p>

      <div className="flex gap-2 mb-4 flex-wrap">
        {GATE_SCENARIOS.map(s => (
          <button
            key={s.key}
            onClick={() => { setScenarioKey(s.key); setGates(null) }}
            className="font-mono text-[9px] px-3 py-1.5 rounded"
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
          className="font-mono text-[11px] px-4 py-1.5 rounded ml-auto"
          style={{ background: 'var(--ibm-blue-60)', color: '#fff' }}
        >
          Run Gates →
        </button>
      </div>

      {gates && (
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            {overallStatus && <StatusBadge status={overallStatus} />}
            <span className="font-mono text-[9px]" style={{ color: 'var(--text-secondary)' }}>
              {gates.length} gates evaluated
            </span>
          </div>

          {/* pipeline visualization */}
          {(['pre_authorization', 'post_authorization', 'pre_output', 'post_output'] as const).map(phase => {
            const phaseGates = gates.filter(g => g.phase === phase)
            if (!phaseGates.length) return null
            return (
              <div key={phase} className="rounded p-3" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-ui)' }}>
                <div className="font-mono text-[8px] mb-2 tracking-widest" style={{ color: PHASE_COLORS[phase] }}>
                  {phase.toUpperCase().replace('_', ' ')}
                </div>
                {phaseGates.map(g => (
                  <div key={g.name} className="flex items-center gap-2 mb-1.5">
                    <StatusBadge status={g.result} />
                    <span className="font-mono text-[9px] flex-1" style={{ color: 'var(--text-primary)' }}>{g.name}</span>
                    <span className="font-mono text-[8px]" style={{ color: 'var(--text-secondary)' }}>{g.detail}</span>
                  </div>
                ))}
              </div>
            )
          })}

          {/* signal bars */}
          <div className="rounded p-3" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-ui)' }}>
            <div className="font-mono text-[9px] mb-2" style={{ color: 'var(--text-secondary)' }}>// gate pass rate</div>
            {Object.entries(PHASE_COLORS).map(([phase, color]) => {
              const phaseGates = gates.filter(g => g.phase === phase)
              const passRate = phaseGates.length ? phaseGates.filter(g => g.result === 'PASS').length / phaseGates.length : 0
              return (
                <SignalBar key={phase} name={phase} contribution={passRate} color={color} />
              )
            })}
          </div>
        </div>
      )}

      {!gates && (
        <div className="font-mono text-[9px] px-3 py-2 rounded" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-ui)', color: 'var(--text-secondary)' }}>
          // run gates to see pipeline evaluation
        </div>
      )}

      {/* recipe example */}
      <div className="mt-4">
        <div className="font-mono text-[9px] mb-2" style={{ color: 'var(--text-secondary)' }}>↳ Gate Recipe (Python SDK)</div>
        <CodeBlock
          label="custom_gate.py"
          code={`from aigc import EnforcementGate

class PiiDetectionGate(EnforcementGate):
    phase = "pre_output"
    name  = "PiiDetectionGate"

    def run(self, invocation, artifact):
        output = invocation.get("output", {})
        text   = str(output.get("result", ""))
        if "SSN" in text or "@" in text:
            raise ValueError("PII detected in output")`}
        />
      </div>
    </div>
  )
}
