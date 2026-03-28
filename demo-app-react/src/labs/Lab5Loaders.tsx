import { useState } from 'react'
import CodeBlock from '@/components/shared/CodeBlock'
import StatusBadge from '@/components/shared/StatusBadge'

type LoaderType = 'filesystem' | 'inmemory'

const VERSIONS = [
  { version: '1.0', date: '2026-01-10', changes: 'Initial policy — no guards, broad roles' },
  { version: '1.1', date: '2026-02-03', changes: 'Added output schema validation' },
  { version: '2.0', date: '2026-03-01', changes: 'Strict risk mode, guards added' },
  { version: '2.1', date: '2026-03-28', changes: 'Threshold tightened: 0.7 → 0.5' },
]

const POLICY_SAMPLES: Record<string, string> = {
  '1.0': `policy_version: "1.0"\nroles: [doctor, nurse, admin, viewer]\nrisk:\n  mode: warn_only\n  threshold: 0.9`,
  '1.1': `policy_version: "1.1"\nroles: [doctor, nurse, admin, viewer]\noutput_schema:\n  type: object\nrisk:\n  mode: warn_only\n  threshold: 0.9`,
  '2.0': `policy_version: "2.0"\nroles: [doctor, nurse]\nguards:\n  - expression: "role in ['doctor','nurse']"\noutput_schema:\n  type: object\nrisk:\n  mode: strict\n  threshold: 0.7`,
  '2.1': `policy_version: "2.1"\nroles: [doctor, nurse]\nguards:\n  - expression: "role in ['doctor','nurse']"\noutput_schema:\n  type: object\nrisk:\n  mode: strict\n  threshold: 0.5`,
}

export default function Lab5Loaders() {
  const [loaderType, setLoaderType] = useState<LoaderType>('filesystem')
  const [selectedVersion, setSelectedVersion] = useState('2.1')

  return (
    <div className="p-4 max-w-4xl mx-auto">
      <p className="font-mono text-[9px] mb-4" style={{ color: 'var(--text-secondary)' }}>
        // policy loading strategies and version history
      </p>

      <div className="flex gap-2 mb-4">
        {(['filesystem', 'inmemory'] as LoaderType[]).map(t => (
          <button
            key={t}
            onClick={() => setLoaderType(t)}
            className="font-mono text-[9px] px-3 py-1.5 rounded"
            style={
              loaderType === t
                ? { background: 'rgba(15,98,254,0.18)', color: 'var(--ibm-cyan-30)', border: '1px solid rgba(15,98,254,0.3)' }
                : { color: 'var(--text-secondary)', border: '1px solid var(--border-ui)' }
            }
          >
            {t === 'filesystem' ? 'FileSystem Loader' : 'InMemory Loader'}
          </button>
        ))}
      </div>

      <div className="font-mono text-[9px] px-3 py-2 rounded mb-4" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-ui)', color: 'var(--text-secondary)' }}>
        {loaderType === 'filesystem'
          ? '// FileSystem: loads YAML from disk, watches for changes, caches parsed policy'
          : '// InMemory: policy registered programmatically, no file I/O, ideal for testing'}
      </div>

      <div className="grid grid-cols-2 gap-4">
        {/* version timeline */}
        <div>
          <div className="font-mono text-[9px] mb-2" style={{ color: 'var(--text-secondary)' }}>↳ Version Timeline</div>
          <div className="space-y-1">
            {VERSIONS.map(v => (
              <button
                key={v.version}
                onClick={() => setSelectedVersion(v.version)}
                className="w-full text-left rounded p-2.5 transition-colors"
                style={{
                  background: selectedVersion === v.version ? 'rgba(15,98,254,0.18)' : 'var(--bg-surface)',
                  border: `1px solid ${selectedVersion === v.version ? 'rgba(15,98,254,0.3)' : 'var(--border-ui)'}`,
                }}
              >
                <div className="flex items-center gap-2 mb-0.5">
                  <span className="font-mono text-[9px]" style={{ color: 'var(--ibm-cyan-30)' }}>v{v.version}</span>
                  <span className="font-mono text-[8px]" style={{ color: 'var(--text-secondary)' }}>{v.date}</span>
                  {v.version === '2.1' && <StatusBadge status="PASS" />}
                </div>
                <div className="font-mono text-[8px]" style={{ color: 'var(--text-secondary)' }}>{v.changes}</div>
              </button>
            ))}
          </div>
        </div>

        {/* policy view */}
        <div>
          <div className="font-mono text-[9px] mb-2" style={{ color: 'var(--text-secondary)' }}>↳ Policy v{selectedVersion}</div>
          <CodeBlock code={POLICY_SAMPLES[selectedVersion]} label={`medical_ai_v${selectedVersion}.yaml`} />
        </div>
      </div>
    </div>
  )
}
