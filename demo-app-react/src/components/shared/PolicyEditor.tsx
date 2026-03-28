import { useState } from 'react'

interface Props {
  initialYaml: string
  label?: string
  onChange?: (yaml: string) => void
}

export default function PolicyEditor({ initialYaml, label = 'policy.yaml', onChange }: Props) {
  const [value, setValue] = useState(initialYaml)

  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setValue(e.target.value)
    onChange?.(e.target.value)
  }

  return (
    <div className="rounded" style={{ border: '1px solid var(--border-ui)' }}>
      <div
        className="px-3 py-1.5 font-mono text-[9px] tracking-wide flex items-center gap-2"
        style={{ color: 'var(--text-secondary)', borderBottom: '1px solid var(--border-ui)', background: 'var(--bg-surface)' }}
      >
        <span style={{ color: 'var(--ibm-blue-60)' }}>↳</span> {label}
      </div>
      <textarea
        value={value}
        onChange={handleChange}
        className="w-full font-mono text-[10px] leading-relaxed px-3 py-2.5 resize-y outline-none"
        style={{
          background: 'var(--bg-base)',
          color: 'var(--text-primary)',
          minHeight: 160,
          border: 'none',
        }}
        spellCheck={false}
      />
    </div>
  )
}
