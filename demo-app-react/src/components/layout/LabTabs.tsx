import { Link, useLocation } from 'react-router-dom'

interface LabMeta { num: number; short: string }

export default function LabTabs({ labs }: { labs: LabMeta[] }) {
  const { pathname } = useLocation()
  return (
    <div
      className="flex gap-1 px-2.5 py-2 overflow-x-auto"
      style={{ background: 'var(--bg-nav)', borderBottom: '1px solid rgba(255,255,255,0.06)' }}
    >
      {labs.map(lab => {
        const active = pathname === `/lab/${lab.num}`
        return (
          <Link
            key={lab.num}
            to={`/lab/${lab.num}`}
            className="whitespace-nowrap rounded px-2.5 py-1 font-mono font-light text-[9px] tracking-wide transition-colors"
            style={
              active
                ? { background: 'rgba(15,98,254,0.18)', color: 'var(--ibm-cyan-30)', border: '1px solid rgba(15,98,254,0.3)' }
                : { color: 'var(--text-secondary)', border: '1px solid transparent' }
            }
          >
            Lab {lab.num}: {lab.short}
          </Link>
        )
      })}
    </div>
  )
}
