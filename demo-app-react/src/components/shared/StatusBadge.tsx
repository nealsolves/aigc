type KnownStatus = 'PASS' | 'FAIL' | 'WARN'

const STYLES: Record<KnownStatus, { bg: string; color: string; label: string }> = {
  PASS: { bg: 'rgba(61,219,217,0.12)',  color: 'var(--ibm-teal-30)',    label: '✓ Pass' },
  FAIL: { bg: 'rgba(255,126,182,0.12)', color: 'var(--ibm-magenta-40)', label: '✗ Fail' },
  WARN: { bg: 'rgba(255,198,0,0.12)',   color: '#ffc600',               label: '⚠ Warn' },
}

const FALLBACK_STYLE = { bg: 'rgba(128,128,128,0.12)', color: 'var(--text-secondary)' }

export default function StatusBadge({ status }: { status: string }) {
  const known = STYLES[status as KnownStatus]
  return (
    <span
      className="inline-flex items-center gap-1 font-mono font-light text-sm px-2 py-0.5 rounded"
      style={{
        background: known ? known.bg    : FALLBACK_STYLE.bg,
        color:      known ? known.color : FALLBACK_STYLE.color,
      }}
    >
      {known ? known.label : status}
    </span>
  )
}
