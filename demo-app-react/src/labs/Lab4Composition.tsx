import { useState } from 'react'
import PolicyEditor from '@/components/shared/PolicyEditor'
import CodeBlock from '@/components/shared/CodeBlock'

type Strategy = 'intersect' | 'union' | 'replace'

const PARENT_YAML = `policy_version: "1.0"
roles: [doctor, nurse]
pre_conditions:
  required: [domain, role_declared]
risk:
  mode: strict
  threshold: 0.7`

const CHILD_YAML = `policy_version: "1.0"
extends: medical_ai.yaml
roles: [doctor]
risk:
  mode: risk_scored
  threshold: 0.5`

function mergeYaml(parent: string, child: string, strategy: Strategy): string {
  // Simplified demo merge — shows the strategy concept
  if (strategy === 'replace') return child
  if (strategy === 'union') {
    return `# union merge: all fields from both policies\n${parent}\n# + child overrides:\n${child}`
  }
  // intersect: only fields present in both
  return `# intersect merge: fields common to both policies\npolicy_version: "1.0"\nroles: [doctor]\nrisk:\n  mode: risk_scored\n  threshold: 0.5`
}

export default function Lab4Composition() {
  const [parentYaml, setParentYaml] = useState(PARENT_YAML)
  const [childYaml, setChildYaml] = useState(CHILD_YAML)
  const [strategy, setStrategy] = useState<Strategy>('intersect')
  const [merged, setMerged] = useState<string | null>(null)

  const strategies: Strategy[] = ['intersect', 'union', 'replace']

  return (
    <div className="p-4 max-w-4xl mx-auto">
      <p className="font-mono text-[9px] mb-4" style={{ color: 'var(--text-secondary)' }}>
        // compose parent + child policies with configurable merge strategy
      </p>

      <div className="grid grid-cols-2 gap-4 mb-4">
        <PolicyEditor initialYaml={parentYaml} label="parent_policy.yaml" onChange={setParentYaml} />
        <PolicyEditor initialYaml={childYaml}  label="child_policy.yaml"  onChange={setChildYaml} />
      </div>

      <div className="flex items-center gap-2 mb-4">
        <span className="font-mono text-[9px]" style={{ color: 'var(--text-secondary)' }}>↳ Strategy:</span>
        {strategies.map(s => (
          <button
            key={s}
            onClick={() => { setStrategy(s); setMerged(null) }}
            className="font-mono text-[9px] px-2.5 py-1 rounded"
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
          onClick={() => setMerged(mergeYaml(parentYaml, childYaml, strategy))}
          className="font-mono text-[11px] px-4 py-1.5 rounded ml-auto"
          style={{ background: 'var(--ibm-blue-60)', color: '#fff' }}
        >
          Merge →
        </button>
      </div>

      {merged !== null && <CodeBlock code={merged} label="merged_policy.yaml" />}
    </div>
  )
}
