interface Props {
  value: string
  label: string
  color: string
}

export default function MetricCard({ value, label, color }: Props) {
  return (
    <div
      className="rounded p-2.5"
      style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-ui)' }}
    >
      <div className="font-mono font-light text-lg leading-none" style={{ color }}>
        {value}
      </div>
      <div className="font-mono text-sm tracking-wider mt-1" style={{ color: 'var(--text-secondary)' }}>
        {label}
      </div>
    </div>
  )
}
