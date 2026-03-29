interface Props {
  score: number      // 0–1
  threshold: number  // 0–1
}

export default function RiskGauge({ score, threshold }: Props) {
  const scorePct  = Math.min(100, Math.max(0, score * 100))
  const threshPct = Math.min(100, Math.max(0, threshold * 100))

  return (
    <div
      className="rounded p-2.5"
      style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-ui)' }}
    >
      <div className="font-mono text-xs mb-1.5" style={{ color: 'var(--text-secondary)' }}>
        // risk_score vs threshold
      </div>
      <div
        className="relative h-2 rounded-full overflow-hidden"
        style={{ background: 'var(--gauge-track)' }}
      >
        {/* fill */}
        <div
          className="absolute left-0 top-0 h-full rounded-full"
          style={{
            width: `${scorePct}%`,
            background: 'linear-gradient(90deg, var(--ibm-teal-30), var(--ibm-blue-40) 60%, var(--ibm-magenta-40))',
          }}
        />
        {/* threshold marker */}
        <div
          className="absolute top-0 h-full w-0.5"
          style={{ left: `${threshPct}%`, background: 'var(--text-primary)', opacity: 0.8 }}
        />
      </div>
      <div className="flex justify-between font-mono text-[11px] mt-1" style={{ color: 'var(--text-secondary)' }}>
        <span>0.0</span>
        <span>threshold: {threshold.toFixed(2)}</span>
        <span>1.0</span>
      </div>
    </div>
  )
}
