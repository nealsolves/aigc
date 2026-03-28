interface Props {
  code: string
  language?: string
  label?: string
}

export default function CodeBlock({ code, label }: Props) {
  return (
    <div className="rounded" style={{ border: '1px solid var(--border-ui)' }}>
      {label && (
        <div
          className="px-3 py-1.5 font-mono text-[9px] tracking-wide"
          style={{
            color: 'var(--text-secondary)',
            borderBottom: '1px solid var(--border-ui)',
            background: 'var(--bg-surface)',
          }}
        >
          {label}
        </div>
      )}
      <pre
        className="px-3 py-2.5 overflow-x-auto font-mono text-[10px] leading-relaxed"
        style={{ background: 'var(--bg-base)', color: 'var(--text-primary)' }}
      >
        <code>{code}</code>
      </pre>
    </div>
  )
}
