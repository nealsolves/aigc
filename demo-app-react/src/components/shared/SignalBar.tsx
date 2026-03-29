interface Props {
  name: string
  contribution: number  // 0–1
  color: string
}

export default function SignalBar({ name, contribution, color }: Props) {
  const pct = Math.min(100, contribution * 100)
  return (
    <div className="flex items-center gap-2 mb-1.5">
      <span className="font-mono text-xs flex-1" style={{ color: 'var(--text-secondary)' }}>
        {name}
      </span>
      <div
        className="flex-[2] h-1 rounded-full overflow-hidden"
        style={{ background: 'var(--gauge-track)' }}
      >
        <div className="h-full rounded-full" style={{ width: `${pct}%`, background: color }} />
      </div>
      <span className="font-mono text-xs w-8 text-right" style={{ color: 'var(--text-secondary)' }}>
        +{contribution.toFixed(2)}
      </span>
    </div>
  )
}
