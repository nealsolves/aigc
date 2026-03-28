type Status = 'PASS' | 'FAIL' | 'WARN'

const STYLES: Record<Status, { bg: string; color: string; label: string }> = {
  PASS: { bg: 'rgba(61,219,217,0.12)', color: 'var(--ibm-teal-30)',    label: '✓ PASS' },
  FAIL: { bg: 'rgba(255,126,182,0.12)', color: 'var(--ibm-magenta-40)', label: '✗ FAIL' },
  WARN: { bg: 'rgba(255,198,0,0.12)',   color: '#ffc600',               label: '⚠ WARN' },
}

export default function StatusBadge({ status }: { status: Status }) {
  const s = STYLES[status]
  return (
    <span
      className="inline-flex items-center gap-1 font-mono font-light text-[9px] px-2 py-0.5 rounded"
      style={{ background: s.bg, color: s.color }}
    >
      {s.label}
    </span>
  )
}
