import { useState } from 'react'
import MetricCard from '@/components/shared/MetricCard'
import StatusBadge from '@/components/shared/StatusBadge'
import CodeBlock from '@/components/shared/CodeBlock'
import { useApi } from '@/hooks/useApi'
import { IBM_COLORS } from '@/theme/tokens'
import type { Artifact } from '@/types/artifact'

// ── types ────────────────────────────────────────────────────────────────────

interface WorkflowRunResponse {
  artifact: Artifact | null
  error: string | null
}

interface CompareResponse {
  governed: { artifact: Artifact | null }
  ungoverned: { artifact: Artifact | null }
}

interface DiagnosisFinding {
  severity: string
  code: string
  message: string
  next_action: string
}

interface DiagnoseResponse {
  findings: DiagnosisFinding[]
  source: string
}

// ── tab config ───────────────────────────────────────────────────────────────

type Tab = 'start-here' | 'failure-fix' | 'governed-vs-ungoverned' | 'evidence-view'

const TABS: { id: Tab; label: string }[] = [
  { id: 'start-here',              label: 'Start Here'              },
  { id: 'failure-fix',             label: 'Failure & Fix'           },
  { id: 'governed-vs-ungoverned',  label: 'Governed vs Ungoverned'  },
  { id: 'evidence-view',           label: 'Evidence View'           },
]

// ── severity color ────────────────────────────────────────────────────────────

function severityColor(severity: string): string {
  switch (severity.toUpperCase()) {
    case 'ERROR':   return IBM_COLORS.red40
    case 'WARNING': return IBM_COLORS.orange40
    default:        return IBM_COLORS.blue40
  }
}

// ── component ────────────────────────────────────────────────────────────────

export default function Lab11WorkflowLab() {
  const { call: callApi, loading } = useApi<WorkflowRunResponse>()
  const compareApi  = useApi<CompareResponse>()
  const diagnoseApi = useApi<DiagnoseResponse>()

  const [activeTab, setActiveTab] = useState<Tab>('start-here')

  // Start Here tab
  const [runResult, setRunResult]           = useState<WorkflowRunResponse | null>(null)
  const [lastArtifact, setLastArtifact]     = useState<Artifact | null>(null)

  // Failure & Fix tab
  const [failureResult, setFailureResult]   = useState<WorkflowRunResponse | null>(null)
  const [findings, setFindings]             = useState<DiagnosisFinding[]>([])
  const [diagnoseSource, setDiagnoseSource] = useState<string>('')
  const [fixResult, setFixResult]           = useState<WorkflowRunResponse | null>(null)

  // Governed vs Ungoverned tab
  const [compareResult, setCompareResult]   = useState<CompareResponse | null>(null)

  // ── handlers ────────────────────────────────────────────────────────────────

  const runMinimal = async () => {
    const res = await callApi('/api/workflow/v090/run', { scenario: 'minimal' })
    if (res) {
      setRunResult(res)
      if (res.artifact) setLastArtifact(res.artifact)
    }
  }

  const runStandard = async () => {
    const res = await callApi('/api/workflow/v090/run', { scenario: 'standard' })
    if (res) {
      setRunResult(res)
      if (res.artifact) setLastArtifact(res.artifact)
    }
  }

  const triggerFailure = async () => {
    const res = await callApi('/api/workflow/v090/run', { scenario: 'failure' })
    if (res) {
      setFailureResult(res)
      if (res.artifact) setLastArtifact(res.artifact)
    }
  }

  const runDoctorDiagnosis = async () => {
    const res = await diagnoseApi.call('/api/workflow/v090/diagnose')
    if (res) {
      setFindings(res.findings ?? [])
      setDiagnoseSource(res.source ?? '')
    }
  }

  const applyFixAndRerun = async () => {
    const res = await callApi('/api/workflow/v090/run', { scenario: 'minimal' })
    if (res) {
      setFixResult(res)
      if (res.artifact) setLastArtifact(res.artifact)
    }
  }

  const runCompare = async () => {
    const res = await compareApi.call('/api/workflow/v090/compare', {})
    if (res) setCompareResult(res)
  }

  // ── render ──────────────────────────────────────────────────────────────────

  return (
    <div className="p-4 max-w-5xl mx-auto">
      <p className="font-mono text-xs mb-4" style={{ color: 'var(--text-secondary)' }}>
        // lab 11 — workflow governance v0.9.0 beta
      </p>

      {/* Tab bar */}
      <div className="flex gap-1 mb-5 flex-wrap">
        {TABS.map(tab => (
          <button
            key={tab.id}
            role="button"
            className="px-3 py-1.5 rounded text-sm font-medium border transition-colors"
            style={{
              background:   activeTab === tab.id ? IBM_COLORS.blue60  : 'var(--bg-surface)',
              color:        activeTab === tab.id ? IBM_COLORS.white    : 'var(--text-primary)',
              borderColor:  activeTab === tab.id ? IBM_COLORS.blue60   : 'var(--border-ui)',
            }}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* ── Start Here tab ───────────────────────────────────────────────────── */}
      {activeTab === 'start-here' && (
        <div>
          <p className="text-sm mb-3" style={{ color: 'var(--text-secondary)' }}>
            Run a minimal or standard workflow scenario through the AIGC governance engine.
          </p>

          <div className="flex gap-2 mb-4">
            <button
              role="button"
              className="px-4 py-1.5 rounded text-sm font-medium text-white disabled:opacity-50"
              style={{ background: IBM_COLORS.blue60 }}
              onClick={runMinimal}
              disabled={loading}
            >
              {loading ? 'Running…' : 'Run Minimal'}
            </button>
            <button
              role="button"
              className="px-4 py-1.5 rounded text-sm font-medium text-white disabled:opacity-50"
              style={{ background: IBM_COLORS.teal60 }}
              onClick={runStandard}
              disabled={loading}
            >
              {loading ? 'Running…' : 'Run Standard'}
            </button>
          </div>

          {runResult && (
            <>
              <div className="grid grid-cols-2 gap-2 mb-4">
                <MetricCard
                  value={runResult.error ? 'ERROR' : (runResult.artifact?.enforcement_result ?? '—')}
                  label="enforcement result"
                  color={runResult.error ? IBM_COLORS.red40 : IBM_COLORS.blue60}
                />
                <MetricCard
                  value={runResult.artifact?.metadata?.risk_scoring?.score != null
                    ? String(runResult.artifact.metadata.risk_scoring.score)
                    : '—'}
                  label="risk score"
                  color={IBM_COLORS.blue40}
                />
              </div>

              {runResult.error && (
                <p className="text-xs mb-2" style={{ color: IBM_COLORS.red40 }}>
                  {runResult.error}
                </p>
              )}

              {runResult.artifact && (
                <CodeBlock
                  code={JSON.stringify(runResult.artifact, null, 2)}
                  label="workflow artifact"
                />
              )}
            </>
          )}
        </div>
      )}

      {/* ── Failure & Fix tab ────────────────────────────────────────────────── */}
      {activeTab === 'failure-fix' && (
        <div>
          <p className="text-sm mb-3" style={{ color: 'var(--text-secondary)' }}>
            Trigger an intentional workflow failure, diagnose it with <code>workflow doctor</code>, then apply the fix and rerun.
          </p>

          <div className="flex gap-2 mb-4 flex-wrap">
            <button
              role="button"
              className="px-4 py-1.5 rounded text-sm font-medium text-white disabled:opacity-50"
              style={{ background: IBM_COLORS.red40 }}
              onClick={triggerFailure}
              disabled={loading}
            >
              {loading ? 'Running…' : 'Trigger Failure'}
            </button>
            <button
              role="button"
              className="px-4 py-1.5 rounded text-sm font-medium text-white disabled:opacity-50"
              style={{ background: IBM_COLORS.orange40 }}
              onClick={runDoctorDiagnosis}
              disabled={diagnoseApi.loading}
            >
              {diagnoseApi.loading ? 'Diagnosing…' : 'Run Doctor Diagnosis'}
            </button>
            <button
              role="button"
              className="px-4 py-1.5 rounded text-sm font-medium text-white disabled:opacity-50"
              style={{ background: IBM_COLORS.green40 }}
              onClick={applyFixAndRerun}
              disabled={loading}
            >
              {loading ? 'Running…' : 'Apply Fix & Rerun'}
            </button>
          </div>

          {failureResult && (
            <div className="mb-4">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-xs font-semibold uppercase" style={{ color: IBM_COLORS.red40 }}>
                  Failure result
                </span>
                {failureResult.artifact && (
                  <StatusBadge status={failureResult.artifact.enforcement_result ?? 'ERROR'} />
                )}
              </div>
              {failureResult.error && (
                <p className="text-xs mb-1" style={{ color: IBM_COLORS.red40 }}>
                  {failureResult.error}
                </p>
              )}
            </div>
          )}

          {findings.length > 0 && (
            <div className="mb-4">
              <p className="text-xs font-semibold uppercase mb-2" style={{ color: IBM_COLORS.orange40 }}>
                Doctor findings {diagnoseSource && `— ${diagnoseSource}`}
              </p>
              <div className="flex flex-col gap-2">
                {findings.map((f, i) => (
                  <div
                    key={i}
                    className="rounded border p-2 text-xs"
                    style={{ borderColor: severityColor(f.severity) }}
                  >
                    <div className="flex items-center gap-2 mb-0.5">
                      <span
                        className="font-semibold uppercase"
                        style={{ color: severityColor(f.severity) }}
                      >
                        {f.severity}
                      </span>
                      <span className="font-mono" style={{ color: 'var(--text-secondary)' }}>
                        {f.code}
                      </span>
                    </div>
                    <p style={{ color: 'var(--text-primary)' }}>{f.message}</p>
                    <p className="mt-0.5" style={{ color: 'var(--text-secondary)' }}>
                      Next: {f.next_action}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {fixResult && (
            <div className="mb-4">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-xs font-semibold uppercase" style={{ color: IBM_COLORS.green40 }}>
                  Post-fix result
                </span>
                {fixResult.artifact && (
                  <StatusBadge status={fixResult.artifact.enforcement_result ?? 'PASS'} />
                )}
              </div>
              {fixResult.artifact && (
                <CodeBlock
                  code={JSON.stringify(fixResult.artifact, null, 2)}
                  label="fixed workflow artifact"
                />
              )}
            </div>
          )}
        </div>
      )}

      {/* ── Governed vs Ungoverned tab ───────────────────────────────────────── */}
      {activeTab === 'governed-vs-ungoverned' && (
        <div>
          <p className="text-sm mb-3" style={{ color: 'var(--text-secondary)' }}>
            Run the same workflow scenario with and without governance enforcement to compare outcomes.
          </p>

          <div className="flex gap-2 mb-4">
            <button
              role="button"
              className="px-4 py-1.5 rounded text-sm font-medium text-white disabled:opacity-50"
              style={{ background: IBM_COLORS.blue60 }}
              onClick={runCompare}
              disabled={compareApi.loading}
            >
              {compareApi.loading ? 'Comparing…' : 'Compare'}
            </button>
          </div>

          {compareResult && (
            <div className="grid grid-cols-2 gap-4">
              {/* Governed panel */}
              <div className="rounded border p-3" style={{ borderColor: 'var(--border-ui)' }}>
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-xs font-semibold uppercase" style={{ color: IBM_COLORS.blue60 }}>
                    Governed
                  </span>
                  {compareResult.governed.artifact?.enforcement_result && (
                    <StatusBadge status={compareResult.governed.artifact.enforcement_result} />
                  )}
                </div>
                <CodeBlock
                  code={JSON.stringify(compareResult.governed.artifact?.metadata ?? {}, null, 2)}
                  label="governance metadata"
                />
              </div>

              {/* Ungoverned panel */}
              <div className="rounded border p-3" style={{ borderColor: 'var(--border-ui)' }}>
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-xs font-semibold uppercase" style={{ color: 'var(--text-secondary)' }}>
                    Ungoverned
                  </span>
                  <span
                    className="text-xs font-mono px-1 rounded"
                    style={{ background: 'var(--bg-surface)', color: 'var(--text-secondary)' }}
                  >
                    no checks
                  </span>
                </div>
                <CodeBlock
                  code={JSON.stringify(compareResult.ungoverned.artifact?.metadata ?? {}, null, 2)}
                  label="raw output metadata"
                />
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Evidence View tab ────────────────────────────────────────────────── */}
      {activeTab === 'evidence-view' && (
        <div>
          <p className="text-sm mb-3" style={{ color: 'var(--text-secondary)' }}>
            Audit artifact from the most recent workflow run.
          </p>

          {lastArtifact ? (
            <>
              <div className="grid grid-cols-3 gap-2 mb-4">
                <MetricCard
                  value={lastArtifact.enforcement_result ?? '—'}
                  label="enforcement result"
                  color={lastArtifact.enforcement_result === 'PASS' ? IBM_COLORS.green40 : IBM_COLORS.red40}
                />
                <MetricCard
                  value={lastArtifact.policy_version ?? '—'}
                  label="policy version"
                  color={IBM_COLORS.blue40}
                />
                <MetricCard
                  value={lastArtifact.metadata?.risk_scoring?.score != null
                    ? String(lastArtifact.metadata.risk_scoring.score)
                    : '—'}
                  label="risk score"
                  color={IBM_COLORS.orange40}
                />
              </div>
              <CodeBlock
                code={JSON.stringify(lastArtifact, null, 2)}
                label="full audit artifact"
              />
            </>
          ) : (
            <p className="text-sm italic" style={{ color: 'var(--text-secondary)' }}>
              No artifact yet — run a scenario from the Start Here or Failure &amp; Fix tabs.
            </p>
          )}
        </div>
      )}
    </div>
  )
}
