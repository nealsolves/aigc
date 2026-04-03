import { useState, useEffect } from 'react'
import PolicyEditor from '@/components/shared/PolicyEditor'
import CodeBlock from '@/components/shared/CodeBlock'
import { useApi } from '@/hooks/useApi'

type Strategy = 'intersect' | 'union' | 'replace'

interface LoadResponse { yaml_text: string | null; error: string | null }
interface ComposeResponse {
  merged_yaml: string | null
  escalations: string[]
  diff: { kept_roles: string[]; removed_roles: string[]; added_roles: string[] }
  error: string | null
}

export default function Lab4Composition() {
  const [parentYaml,    setParentYaml]    = useState('')
  const [childYaml,     setChildYaml]     = useState('')
  const [policiesReady, setPoliciesReady] = useState(false)
  const [loadError,     setLoadError]     = useState<string | null>(null)
  const [strategy,      setStrategy]      = useState<Strategy>('intersect')
  const [result,        setResult]        = useState<ComposeResponse | null>(null)

  const { call: callLoadParent } = useApi<LoadResponse>()
  const { call: callLoadChild  } = useApi<LoadResponse>()
  const { call,           loading, error: apiError } = useApi<ComposeResponse>()

  // Seed editors with real v0.3.0 sample policies on mount
  useEffect(() => {
    Promise.all([
      callLoadParent('/api/policy/load', { policy_name: 'medical_ai.yaml' }),
      callLoadChild('/api/policy/load', { policy_name: 'medical_ai_child.yaml' }),
    ]).then(([parent, child]) => {
      const parentYaml = parent?.yaml_text
      const childYaml  = child?.yaml_text
      if (parentYaml && childYaml) {
        setParentYaml(parentYaml)
        setChildYaml(childYaml)
        setPoliciesReady(true)
      } else {
        setLoadError(
          parent?.error ?? child?.error ?? 'Failed to load sample policies — check API connection'
        )
      }
    })
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const merge = async () => {
    const res = await call('/api/compose', {
      parent_yaml: parentYaml,
      child_yaml: childYaml,
      strategy,
    })
    if (res) setResult(res)
  }

  const strategies: Strategy[] = ['intersect', 'union', 'replace']

  return (
    <div className="p-4 max-w-4xl mx-auto">
      <p className="font-mono text-xs mb-4" style={{ color: 'var(--text-secondary)' }}>
        // compose parent + child policies with configurable merge strategy
      </p>

      {!policiesReady ? (
        <div className="grid grid-cols-2 gap-4 mb-4">
          {['medical_ai.yaml', 'medical_ai_child.yaml'].map(name => (
            <div key={name} className="rounded h-40 flex items-center justify-center" style={{ border: '1px solid var(--border-ui)', background: 'var(--bg-surface)' }}>
              {loadError
                ? <span className="font-mono text-xs px-3 text-center" style={{ color: 'var(--ibm-magenta-40)' }}>// load failed: {loadError}</span>
                : <span className="font-mono text-xs" style={{ color: 'var(--text-secondary)' }}>// loading {name}…</span>
              }
            </div>
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-4 mb-4">
          <PolicyEditor key="parent" initialYaml={parentYaml} label="medical_ai.yaml (parent)" onChange={setParentYaml} />
          <PolicyEditor key="child"  initialYaml={childYaml}  label="medical_ai_child.yaml (child)" onChange={setChildYaml} />
        </div>
      )}

      <div className="flex items-center gap-2 mb-4">
        <span className="font-mono text-xs" style={{ color: 'var(--text-secondary)' }}>↳ Strategy:</span>
        {strategies.map(s => (
          <button
            key={s}
            onClick={() => { setStrategy(s); setResult(null) }}
            className="font-mono text-xs px-2.5 py-1 rounded"
            style={
              strategy === s
                ? { background: 'rgba(15,98,254,0.18)', color: 'var(--ibm-cyan-30)', border: '1px solid rgba(15,98,254,0.3)' }
                : { color: 'var(--text-secondary)', border: '1px solid var(--border-ui)' }
            }
          >
            {s}
          </button>
        ))}
        <button
          onClick={merge}
          disabled={loading || !policiesReady}
          className="font-mono text-sm px-4 py-1.5 rounded ml-auto"
          style={{ background: 'var(--ibm-blue-60)', color: '#fff', opacity: (loading || !policiesReady) ? 0.7 : 1 }}
        >
          {loading ? 'Merging…' : 'Merge →'}
        </button>
      </div>

      {(apiError || result?.error) && (
        <div className="font-mono text-xs px-3 py-2 rounded mb-3" style={{ background: 'rgba(255,126,182,0.08)', border: '1px solid rgba(255,126,182,0.2)', color: 'var(--ibm-magenta-40)' }}>
          // error: {apiError ?? result?.error}
        </div>
      )}

      {result?.merged_yaml && (
        <>
          <CodeBlock code={result.merged_yaml} label="merged_policy.yaml" />

          {/* Roles diff */}
          <div className="grid grid-cols-3 gap-2 mt-3">
            {[
              { label: 'Kept roles',    items: result.diff.kept_roles,    color: 'var(--ibm-teal-30)' },
              { label: 'Removed roles', items: result.diff.removed_roles, color: 'var(--ibm-blue-40)' },
              { label: 'Added roles',   items: result.diff.added_roles,   color: 'var(--ibm-magenta-40)' },
            ].map(col => (
              <div key={col.label} className="rounded p-2" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-ui)' }}>
                <div className="font-mono text-[11px] mb-1" style={{ color: 'var(--text-secondary)' }}>{col.label}</div>
                {col.items.length === 0
                  ? <div className="font-mono text-[11px]" style={{ color: 'var(--text-secondary)' }}>—</div>
                  : col.items.map(r => (
                      <div key={r} className="font-mono text-xs" style={{ color: col.color }}>{r}</div>
                    ))
                }
              </div>
            ))}
          </div>

          {/* Escalation panel — covers new tools and removed postconditions */}
          {result.escalations.length > 0 ? (
            <div className="mt-3 rounded p-3" style={{ background: 'rgba(255,126,182,0.08)', border: '1px solid rgba(255,126,182,0.3)' }}>
              <div className="font-mono text-xs mb-1" style={{ color: 'var(--ibm-magenta-40)' }}>
                // privilege escalation detected ({result.escalations.length} violation{result.escalations.length > 1 ? 's' : ''})
              </div>
              {result.escalations.map((v, i) => (
                <div key={i} className="font-mono text-xs" style={{ color: 'var(--ibm-magenta-40)' }}>- {v}</div>
              ))}
            </div>
          ) : (
            <div className="mt-3 font-mono text-xs px-3 py-2 rounded" style={{ background: 'rgba(8,186,132,0.08)', border: '1px solid rgba(8,186,132,0.3)', color: 'var(--ibm-teal-30)' }}>
              // no privilege escalation — child is a restriction of the base
            </div>
          )}
        </>
      )}
    </div>
  )
}
