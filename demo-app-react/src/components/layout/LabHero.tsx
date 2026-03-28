import { useTheme } from '@/theme/ThemeContext'
import { LAB_COLORS, IBM_COLORS } from '@/theme/tokens'

// Dark-mode overrides for labs whose base color is too dark on a navy bg
const LAB_COLORS_DARK: Record<number, string> = {
  1: IBM_COLORS.blue40,   // blue60 → blue40 (#78a9ff)
  6: IBM_COLORS.teal30,   // teal60 → teal30 (#3ddbd9)
}

interface Props { labNum: number; title: string }

export default function LabHero({ labNum, title }: Props) {
  const { theme } = useTheme()
  const accentColor = theme === 'dark'
    ? (LAB_COLORS_DARK[labNum] ?? LAB_COLORS[labNum] ?? 'var(--ibm-blue-40)')
    : (LAB_COLORS[labNum] ?? 'var(--ibm-blue-60)')

  if (theme === 'dark') {
    return (
      <div
        className="relative overflow-hidden px-4 py-3 font-mono font-light text-sm"
        style={{
          background: 'linear-gradient(135deg, var(--bg-hero) 0%, var(--bg-hero-end) 100%)',
          borderBottom: '1px solid rgba(15,98,254,0.2)',
          color: 'var(--text-on-hero)',
        }}
      >
        {/* left accent bar */}
        <div
          className="absolute left-0 top-0 bottom-0 w-[3px]"
          style={{ background: `linear-gradient(180deg, var(--ibm-blue-60), var(--ibm-teal-30))` }}
        />
        {/* glow orbs */}
        <div className="absolute -top-5 -right-5 w-24 h-24 rounded-full pointer-events-none"
          style={{ background: 'radial-gradient(circle, rgba(15,98,254,0.35) 0%, transparent 70%)' }} />
        <div className="absolute -bottom-4 pointer-events-none"
          style={{ left: '60%', width: 64, height: 64, background: 'radial-gradient(circle, rgba(61,219,217,0.15) 0%, transparent 70%)', borderRadius: '50%' }} />
        <span className="relative z-10">
          Lab {labNum} — <span style={{ color: accentColor }}>
            {title}↓
          </span>
        </span>
      </div>
    )
  }

  return (
    <div
      className="relative overflow-hidden px-4 py-3 font-mono font-light text-sm"
      style={{ background: 'var(--ibm-blue-60)', color: 'var(--text-on-hero)' }}
    >
      <div className="absolute -right-2.5 top-1/2 -translate-y-1/2 w-[70px] h-[70px] rounded-full pointer-events-none"
        style={{ background: 'rgba(130,207,255,0.15)' }} />
      <span className="relative z-10">
        Lab {labNum} — <span style={{ color: 'var(--ibm-cyan-30)' }}>
          {title}↓
        </span>
      </span>
    </div>
  )
}
