import { useTheme } from '@/theme/ThemeContext'
import { Moon, Sun, ExternalLink } from 'lucide-react'

export default function AppNav() {
  const { theme, toggleTheme } = useTheme()
  return (
    <nav
      className="flex items-center gap-3 px-4 py-2.5 border-b"
      style={{ background: 'var(--bg-nav)', borderColor: 'rgba(255,255,255,0.07)' }}
    >
      <span className="font-mono font-light text-xs tracking-widest" style={{ color: 'var(--ibm-cyan-30)' }}>
        aigc <span style={{ color: 'rgba(255,255,255,0.3)' }}>//</span> sdk
      </span>
      <div className="flex-1" />
      <a
        href="https://github.com/nealsolves/aigc"
        target="_blank"
        rel="noopener noreferrer"
        className="text-text-2 hover:text-text-1 transition-colors"
        aria-label="GitHub repository"
      >
        <ExternalLink size={16} />
      </a>
      <button
        onClick={toggleTheme}
        className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-mono font-light transition-colors"
        style={{
          background: 'rgba(255,255,255,0.06)',
          border: '1px solid rgba(255,255,255,0.12)',
          color: 'var(--text-on-nav)',
        }}
        aria-label={`Switch to ${theme === 'light' ? 'dark' : 'light'} mode`}
      >
        {theme === 'dark' ? <Moon size={12} /> : <Sun size={12} />}
        {theme === 'dark' ? 'dark' : 'light'}
      </button>
    </nav>
  )
}
