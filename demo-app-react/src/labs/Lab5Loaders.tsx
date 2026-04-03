import { useState, useEffect } from 'react'
import CodeBlock from '@/components/shared/CodeBlock'
import { useApi } from '@/hooks/useApi'

type Tab = 'loaders' | 'versioning' | 'testing'
type LoaderMode = 'filesystem' | 'inmemory'

interface PoliciesResponse { policies: string[] }
interface LoadResponse { policy: Record<string, unknown> | null; yaml_text: string | null; loader_class?: string; error: string | null }
interface ValidateDatesResponse { in_range: boolean; evidence: Record<string, unknown>; error: string | null }
interface TestResult { name: string; enforcement_result: string; passed: boolean; failure_reason: string | null }
interface TestResponse { results: TestResult[]; all_met_expectations: boolean; error: string | null }

const SAMPLE_INMEMORY_YAML = `policy_version: "1.0"
roles: [doctor, nurse]
pre_conditions:
  required: [domain, role_declared]
risk:
  mode: risk_scored
  threshold: 0.7
`

export default function Lab5Loaders() {
  const [tab, setTab] = useState<Tab>('loaders')
  const [loaderMode, setLoaderMode] = useState<LoaderMode>('filesystem')

  // Loaders tab state
  const [policies, setPolicies]             = useState<string[]>([])
  const [selectedPolicy, setSelectedPolicy] = useState('')
  const [loadedPolicy, setLoadedPolicy]     = useState<LoadResponse | null>(null)
  const [inMemoryYaml, setInMemoryYaml]     = useState(SAMPLE_INMEMORY_YAML)

  // Versioning tab state
  const [effectiveDate,  setEffectiveDate]  = useState('2020-01-01')
  const [expirationDate, setExpirationDate] = useState('2030-12-31')
  const [referenceDate,  setReferenceDate]  = useState('2026-04-01')
  const [dateResult,     setDateResult]     = useState<ValidateDatesResponse | null>(null)

  // Testing tab state
  const [testPolicy,  setTestPolicy]  = useState('')
  const [testResults, setTestResults] = useState<TestResponse | null>(null)

  const { call: callPolicies } = useApi<PoliciesResponse>()
  const { call: callLoad,       loading: loadingLoad    } = useApi<LoadResponse>()
  const { call: callInMemory,   loading: loadingInMemory } = useApi<LoadResponse>()
  const { call: callDates,      loading: loadingDates   } = useApi<ValidateDatesResponse>()
  const { call: callTest,       loading: loadingTest    } = useApi<TestResponse>()

  useEffect(() => {
    callPolicies('/api/policies').then(res => {
      if (res) {
        setPolicies(res.policies)
        if (res.policies.length > 0) {
          setSelectedPolicy(res.policies[0])
          setTestPolicy(res.policies[0])
        }
      }
    })
  }, [])

  const loadFilesystem = async () => {
    const res = await callLoad('/api/policy/load', { policy_name: selectedPolicy })
    if (res) setLoadedPolicy(res)
  }

  const loadInMemory = async () => {
    const res = await callInMemory('/api/policy/load-inmemory', { yaml_text: inMemoryYaml })
    if (res) setLoadedPolicy(res)
  }

  const validateDates = async () => {
    const res = await callDates('/api/policy/validate-dates', {
      effective_date: effectiveDate || null,
      expiration_date: expirationDate || null,
      reference_date: referenceDate || null,
    })
    if (res) setDateResult(res)
  }

  const runTests = async () => {
    const res = await callTest('/api/policy/test', { policy_name: testPolicy })
    if (res) setTestResults(res)
  }

  const TABS: { key: Tab; label: string }[] = [
    { key: 'loaders',    label: 'Loaders'    },
    { key: 'versioning', label: 'Versioning' },
    { key: 'testing',    label: 'Testing'    },
  ]

  // Compute timeline bar positions (0–100%) for the versioning panel
  const timelineStart = effectiveDate
  const timelineEnd   = expirationDate
  const timelineRef   = referenceDate

  const toYear = (d: string) => new Date(d).getFullYear() + new Date(d).getMonth() / 12
  const clamp  = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, v))
  const pct = timelineStart && timelineEnd
    ? (d: string) => {
        const lo = toYear(timelineStart)
        const hi = toYear(timelineEnd)
        return hi > lo ? clamp(((toYear(d) - lo) / (hi - lo)) * 100, 0, 100) : 0
      }
    : null

  return (
    <div className="p-4 max-w-4xl mx-auto">
      <p className="font-mono text-xs mb-4" style={{ color: 'var(--text-secondary)' }}>
        // policy loading strategies, date validation, and test framework
      </p>

      {/* Tab selector */}
      <div className="flex gap-2 mb-4">
        {TABS.map(t => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className="font-mono text-xs px-3 py-1.5 rounded"
            style={
              tab === t.key
                ? { background: 'rgba(15,98,254,0.18)', color: 'var(--ibm-cyan-30)', border: '1px solid rgba(15,98,254,0.3)' }
                : { color: 'var(--text-secondary)', border: '1px solid var(--border-ui)' }
            }
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Loaders tab */}
      {tab === 'loaders' && (
        <div className="space-y-3">
          {/* Loader mode selector */}
          <div>
            <div className="font-mono text-xs mb-2" style={{ color: 'var(--text-secondary)' }}>↳ Loader Mode</div>
            <div className="flex gap-2 mb-3">
              {(['filesystem', 'inmemory'] as LoaderMode[]).map(mode => (
                <button
                  key={mode}
                  onClick={() => { setLoaderMode(mode); setLoadedPolicy(null) }}
                  className="font-mono text-xs px-3 py-1.5 rounded"
                  style={
                    loaderMode === mode
                      ? { background: 'rgba(15,98,254,0.18)', color: 'var(--ibm-cyan-30)', border: '1px solid rgba(15,98,254,0.3)' }
                      : { color: 'var(--text-secondary)', border: '1px solid var(--border-ui)' }
                  }
                >
                  {mode === 'filesystem' ? 'FileSystem' : 'InMemory'}
                </button>
              ))}
            </div>
            <div className="font-mono text-[11px] px-3 py-2 rounded" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-ui)', color: 'var(--text-secondary)' }}>
              {loaderMode === 'filesystem'
                ? '// FilePolicyLoader — reads YAML from a file path on disk'
                : '// InMemoryPolicyLoader(PolicyLoaderBase) — holds policy in memory; no filesystem required'}
            </div>
          </div>

          {/* FileSystem mode */}
          {loaderMode === 'filesystem' && (
            <div className="space-y-2">
              <div className="flex gap-2">
                <select
                  value={selectedPolicy}
                  onChange={e => { setSelectedPolicy(e.target.value); setLoadedPolicy(null) }}
                  className="flex-1 font-mono text-[13px] px-3 py-2 rounded outline-none"
                  style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-ui)', color: 'var(--text-primary)' }}
                >
                  {policies.map(p => <option key={p} value={p}>{p}</option>)}
                </select>
                <button
                  onClick={loadFilesystem}
                  disabled={!selectedPolicy || loadingLoad}
                  className="font-mono text-xs px-3 py-2 rounded"
                  style={{ background: 'var(--ibm-blue-60)', color: '#fff', opacity: (!selectedPolicy || loadingLoad) ? 0.7 : 1 }}
                >
                  {loadingLoad ? '…' : 'Load →'}
                </button>
              </div>
            </div>
          )}

          {/* InMemory mode */}
          {loaderMode === 'inmemory' && (
            <div className="space-y-2">
              <div className="font-mono text-xs" style={{ color: 'var(--text-secondary)' }}>↳ Paste or edit policy YAML — parsed directly, no file path needed</div>
              <textarea
                value={inMemoryYaml}
                onChange={e => { setInMemoryYaml(e.target.value); setLoadedPolicy(null) }}
                rows={8}
                className="w-full font-mono text-[12px] px-3 py-2 rounded outline-none resize-y"
                style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-ui)', color: 'var(--text-primary)' }}
                spellCheck={false}
              />
              <button
                onClick={loadInMemory}
                disabled={!inMemoryYaml.trim() || loadingInMemory}
                className="font-mono text-xs px-3 py-2 rounded"
                style={{ background: 'var(--ibm-blue-60)', color: '#fff', opacity: (!inMemoryYaml.trim() || loadingInMemory) ? 0.7 : 1 }}
              >
                {loadingInMemory ? '…' : 'Parse →'}
              </button>
            </div>
          )}

          {/* Shared result */}
          {loadedPolicy?.error && (
            <div className="font-mono text-xs" style={{ color: 'var(--ibm-magenta-40)' }}>// error: {loadedPolicy.error}</div>
          )}
          {loadedPolicy && !loadedPolicy.error && loadedPolicy.yaml_text && (
            <div className="space-y-2">
              {loadedPolicy.loader_class && (
                <div className="font-mono text-[11px]" style={{ color: 'var(--ibm-teal-30)' }}>
                  // loaded via {loadedPolicy.loader_class}
                </div>
              )}
              <CodeBlock code={loadedPolicy.yaml_text} label={loaderMode === 'filesystem' ? selectedPolicy : 'inline policy'} />
            </div>
          )}
        </div>
      )}

      {/* Versioning tab */}
      {tab === 'versioning' && (
        <div className="space-y-3">
          <div className="font-mono text-xs" style={{ color: 'var(--text-secondary)' }}>↳ Policy date range validation</div>
          <div className="grid grid-cols-3 gap-3">
            {[
              { label: 'effective_date', value: effectiveDate, onChange: setEffectiveDate },
              { label: 'expiration_date', value: expirationDate, onChange: setExpirationDate },
              { label: 'reference_date (today)', value: referenceDate, onChange: setReferenceDate },
            ].map(field => (
              <div key={field.label}>
                <div className="font-mono text-[11px] mb-1" style={{ color: 'var(--text-secondary)' }}>{field.label}</div>
                <input
                  type="date"
                  value={field.value}
                  onChange={e => { field.onChange(e.target.value); setDateResult(null) }}
                  className="w-full font-mono text-[13px] px-3 py-2 rounded outline-none"
                  style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-ui)', color: 'var(--text-primary)' }}
                />
              </div>
            ))}
          </div>

          {/* Version timeline panel */}
          {pct && timelineStart && timelineEnd && timelineRef && (
            <div className="rounded p-3" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-ui)' }}>
              <div className="font-mono text-[11px] mb-2" style={{ color: 'var(--text-secondary)' }}>// policy validity window</div>
              <div className="relative h-6 rounded" style={{ background: 'rgba(15,98,254,0.08)', border: '1px solid var(--border-ui)' }}>
                {/* active window bar */}
                <div
                  className="absolute top-0 bottom-0 rounded"
                  style={{
                    left: '0%',
                    right: '0%',
                    background: 'rgba(8,186,132,0.18)',
                  }}
                />
                {/* reference date cursor */}
                <div
                  className="absolute top-0 bottom-0 w-0.5"
                  style={{
                    left: `${pct(timelineRef)}%`,
                    background: 'var(--ibm-cyan-30)',
                  }}
                />
              </div>
              <div className="flex justify-between font-mono text-[10px] mt-1" style={{ color: 'var(--text-secondary)' }}>
                <span>{timelineStart}</span>
                <span style={{ color: 'var(--ibm-cyan-30)' }}>▲ {timelineRef}</span>
                <span>{timelineEnd}</span>
              </div>
            </div>
          )}

          <button
            onClick={validateDates}
            disabled={loadingDates}
            className="font-mono text-xs px-4 py-2 rounded"
            style={{ background: 'var(--ibm-blue-60)', color: '#fff', opacity: loadingDates ? 0.7 : 1 }}
          >
            {loadingDates ? '…' : 'Validate Dates →'}
          </button>
          {dateResult && (
            <div className="rounded p-3" style={{ background: 'var(--bg-surface)', border: `1px solid ${dateResult.in_range ? 'rgba(8,186,132,0.3)' : 'rgba(255,126,182,0.3)'}` }}>
              <div className="font-mono text-xs mb-2" style={{ color: dateResult.in_range ? 'var(--ibm-teal-30)' : 'var(--ibm-magenta-40)' }}>
                {dateResult.in_range ? '// policy is active — within date range' : '// policy is NOT active — outside date range'}
              </div>
              {dateResult.error && <div className="font-mono text-xs" style={{ color: 'var(--ibm-magenta-40)' }}>{dateResult.error}</div>}
            </div>
          )}
        </div>
      )}

      {/* Testing tab */}
      {tab === 'testing' && (
        <div className="space-y-3">
          <div className="font-mono text-xs" style={{ color: 'var(--text-secondary)' }}>↳ Policy test suite — auto-generates 3 test cases</div>
          <div className="flex gap-2">
            <select
              value={testPolicy}
              onChange={e => { setTestPolicy(e.target.value); setTestResults(null) }}
              className="flex-1 font-mono text-[13px] px-3 py-2 rounded outline-none"
              style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-ui)', color: 'var(--text-primary)' }}
            >
              {policies.map(p => <option key={p} value={p}>{p}</option>)}
            </select>
            <button
              onClick={runTests}
              disabled={!testPolicy || loadingTest}
              className="font-mono text-xs px-3 py-2 rounded"
              style={{ background: 'var(--ibm-blue-60)', color: '#fff', opacity: (!testPolicy || loadingTest) ? 0.7 : 1 }}
            >
              {loadingTest ? '…' : 'Run Tests →'}
            </button>
          </div>
          {testResults && (
            <div className="space-y-2">
              {testResults.results.map((r, i) => (
                <div key={i} className="flex items-start gap-3 rounded p-2" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-ui)' }}>
                  <span className="font-mono text-sm" style={{ color: r.enforcement_result === 'PASS' ? 'var(--ibm-teal-30)' : 'var(--ibm-magenta-40)' }}>
                    {r.enforcement_result === 'PASS' ? '✓' : '✗'}
                  </span>
                  <div>
                    <div className="font-mono text-xs" style={{ color: 'var(--text-primary)' }}>{r.name}</div>
                    {r.failure_reason && (
                      <div className="font-mono text-[11px]" style={{ color: 'var(--text-secondary)' }}>{r.failure_reason}</div>
                    )}
                  </div>
                </div>
              ))}
              <div className="font-mono text-xs" style={{ color: testResults.all_met_expectations ? 'var(--ibm-teal-30)' : 'var(--ibm-magenta-40)' }}>
                {testResults.all_met_expectations ? '// all expectations met' : '// some expectations not met'}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
