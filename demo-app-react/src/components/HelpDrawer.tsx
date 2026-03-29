import { useEffect, useRef, useState } from 'react'
import { useTheme } from '@/theme/ThemeContext'
import { helpContent } from '@/help/helpContent'

interface Props {
  labId: number
  isOpen: boolean
  onClose: () => void
}

export default function HelpDrawer({ labId, isOpen, onClose }: Props) {
  const { theme } = useTheme()
  const closeButtonRef = useRef<HTMLButtonElement>(null)
  const [glossaryOpen, setGlossaryOpen] = useState(false)

  const lab = helpContent[labId] ?? helpContent[1]
  const isDark = theme === 'dark'

  // Focus close button on open; handle Escape
  useEffect(() => {
    if (!isOpen) return

    const prevFocus = document.activeElement as HTMLElement | null
    closeButtonRef.current?.focus()

    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handleKey)

    return () => {
      document.removeEventListener('keydown', handleKey)
      prevFocus?.focus()
    }
  }, [isOpen, onClose])

  // Reset glossary when lab changes
  useEffect(() => {
    setGlossaryOpen(false)
  }, [labId])

  if (!isOpen) return null

  // Theme-aware colour values
  const drawerBg    = isDark ? '#161622' : '#ffffff'
  const headerBg    = isDark ? '#0d0d1a' : '#f2f4f8'
  const borderColor = isDark ? 'rgba(255,255,255,0.1)' : '#c1c7cd'
  const labelColor  = isDark ? '#78a9ff' : '#0f62fe'
  const titleColor  = isDark ? '#f2f4f8' : '#161616'
  const overviewColor = isDark ? '#c1c7cd' : '#393939'
  const stepTitleColor = isDark ? '#f2f4f8' : '#161616'
  const stepTextColor  = isDark ? '#8d8d9e' : '#393939'
  const stepNumBg   = isDark ? 'rgba(15,98,254,0.15)' : '#e8f0fe'
  const stepNumBorder = isDark ? 'rgba(15,98,254,0.4)' : '#0f62fe'
  const stepNumColor  = isDark ? '#78a9ff' : '#0f62fe'
  const tipBg     = isDark ? 'rgba(61,219,217,0.06)' : '#f0fafa'
  const tipBorder = isDark ? 'rgba(61,219,217,0.4)' : '#007d79'
  const tipColor  = isDark ? '#3ddbd9' : '#007d79'
  const glossaryBtnBg = isDark ? 'rgba(255,255,255,0.04)' : '#f2f4f8'
  const glossaryBodyBorder = borderColor
  const glossaryTermColor = isDark ? '#78a9ff' : '#0f62fe'
  const footerBg = isDark ? '#0d0d1a' : '#f2f4f8'
  const footerColor = isDark ? '#4b5563' : '#525252'
  const closeBtnBg = isDark ? 'rgba(255,255,255,0.06)' : '#ffffff'
  const closeBtnColor = isDark ? '#8d8d9e' : '#525252'
  const backdropBg = isDark ? 'rgba(0,0,0,0.55)' : 'rgba(22,22,22,0.45)'

  const LABS_LABEL = [
    '', 'Lab 1 — Risk Scoring', 'Lab 2 — Signing', 'Lab 3 — Audit Chain',
    'Lab 4 — Composition', 'Lab 5 — Loaders', 'Lab 6 — Custom Gates', 'Lab 7 — Compliance',
  ]

  return (
    <>
      {/* Backdrop */}
      <div
        data-testid="help-backdrop"
        onClick={onClose}
        style={{
          position: 'fixed',
          inset: 0,
          background: backdropBg,
          zIndex: 200,
        }}
      />

      {/* Drawer */}
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Lab guide"
        style={{
          position: 'fixed',
          top: 0,
          right: 0,
          bottom: 0,
          width: 'min(22rem, 90vw)',
          background: drawerBg,
          borderLeft: `1px solid ${borderColor}`,
          boxShadow: isDark ? 'none' : '-4px 0 24px rgba(22,22,22,0.12)',
          zIndex: 300,
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
        }}
      >
        {/* Header */}
        <div
          style={{
            background: headerBg,
            padding: '1.25rem 1.5rem',
            display: 'flex',
            alignItems: 'flex-start',
            justifyContent: 'space-between',
            gap: '1rem',
            borderBottom: `1px solid ${borderColor}`,
            flexShrink: 0,
          }}
        >
          <div>
            <div
              style={{
                fontSize: '0.75rem',
                color: labelColor,
                textTransform: 'uppercase',
                letterSpacing: '0.1em',
                marginBottom: '0.25rem',
                fontWeight: 600,
                fontFamily: "'IBM Plex Sans', sans-serif",
              }}
            >
              {LABS_LABEL[labId] ?? `Lab ${labId}`}
            </div>
            <div
              style={{
                fontFamily: "'IBM Plex Mono', monospace",
                fontSize: '1.0625rem',
                color: titleColor,
                fontWeight: 600,
                lineHeight: 1.4,
              }}
            >
              {lab.title}
            </div>
          </div>

          <button
            ref={closeButtonRef}
            onClick={onClose}
            aria-label="Close guide"
            style={{
              background: closeBtnBg,
              border: `1px solid ${borderColor}`,
              color: closeBtnColor,
              borderRadius: '4px',
              width: '2rem',
              height: '2rem',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              cursor: 'pointer',
              fontSize: '1rem',
              flexShrink: 0,
              marginTop: '2px',
              fontFamily: "'IBM Plex Sans', sans-serif",
            }}
          >
            ✕
          </button>
        </div>

        {/* Body */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '1.5rem' }}>
          {/* Overview */}
          <p
            style={{
              fontSize: '1rem',
              lineHeight: 1.6,
              color: overviewColor,
              marginBottom: '2rem',
              letterSpacing: '0.012em',
              wordSpacing: '0.016em',
            }}
          >
            {lab.overview}
          </p>

          {/* Steps label */}
          <div
            style={{
              fontSize: '0.75rem',
              fontWeight: 600,
              letterSpacing: '0.1em',
              color: '#6b7280',
              textTransform: 'uppercase',
              marginBottom: '1rem',
              fontFamily: "'IBM Plex Sans', sans-serif",
            }}
          >
            Steps
          </div>

          {/* Steps */}
          {lab.steps.map((step, i) => (
            <div
              key={i}
              style={{ display: 'flex', gap: '1rem', marginBottom: '1.75rem' }}
            >
              {/* Step number */}
              <div
                aria-hidden="true"
                style={{
                  width: '1.75rem',
                  height: '1.75rem',
                  borderRadius: '50%',
                  background: stepNumBg,
                  border: `1.5px solid ${stepNumBorder}`,
                  color: stepNumColor,
                  fontSize: '0.875rem',
                  fontWeight: 700,
                  fontFamily: "'IBM Plex Mono', monospace",
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0,
                  marginTop: '0.125rem',
                }}
              >
                {i + 1}
              </div>

              {/* Step content */}
              <div>
                <div
                  style={{
                    fontSize: '1rem',
                    fontWeight: 600,
                    color: stepTitleColor,
                    lineHeight: 1.5,
                    marginBottom: '0.375rem',
                    letterSpacing: '0.012em',
                    fontFamily: "'IBM Plex Sans', sans-serif",
                  }}
                >
                  {step.title}
                </div>
                <div
                  style={{
                    fontSize: '1rem',
                    lineHeight: 1.6,
                    color: stepTextColor,
                    marginBottom: step.tip ? '0.5rem' : 0,
                    letterSpacing: '0.012em',
                    wordSpacing: '0.016em',
                    fontFamily: "'IBM Plex Sans', sans-serif",
                  }}
                >
                  {step.instruction}
                </div>
                {step.tip && (
                  <div
                    style={{
                      fontSize: '0.9375rem',
                      lineHeight: 1.6,
                      color: tipColor,
                      background: tipBg,
                      borderLeft: `2px solid ${tipBorder}`,
                      padding: '0.5rem 0.75rem',
                      borderRadius: '0 4px 4px 0',
                      letterSpacing: '0.012em',
                      fontFamily: "'IBM Plex Sans', sans-serif",
                    }}
                  >
                    {'💡 '}{step.tip}
                  </div>
                )}
              </div>
            </div>
          ))}

          {/* Glossary */}
          {lab.glossary && lab.glossary.length > 0 && (
            <div style={{ marginTop: '0.5rem' }}>
              <button
                aria-label="Glossary"
                aria-expanded={glossaryOpen}
                onClick={() => setGlossaryOpen(v => !v)}
                style={{
                  width: '100%',
                  background: glossaryBtnBg,
                  border: `1px solid ${borderColor}`,
                  borderRadius: glossaryOpen ? '4px 4px 0 0' : '4px',
                  padding: '0.875rem 1rem',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  cursor: 'pointer',
                  color: titleColor,
                  fontSize: '1rem',
                  fontFamily: "'IBM Plex Sans', sans-serif",
                  fontWeight: 500,
                  letterSpacing: '0.012em',
                  textAlign: 'left',
                }}
              >
                <span>Glossary</span>
                <span aria-hidden="true" style={{ fontSize: '0.75rem', color: stepTextColor }}>
                  {glossaryOpen ? '▲' : '▼'}
                </span>
              </button>

              {glossaryOpen && (
                <div
                  style={{
                    border: `1px solid ${glossaryBodyBorder}`,
                    borderTop: 'none',
                    borderRadius: '0 0 4px 4px',
                    overflow: 'hidden',
                  }}
                >
                  {lab.glossary.map((item, i) => (
                    <dl
                      key={i}
                      style={{
                        padding: '0.875rem 1rem',
                        borderBottom: i < lab.glossary!.length - 1 ? `1px solid ${borderColor}` : 'none',
                        margin: 0,
                        background: isDark ? 'rgba(255,255,255,0.02)' : '#ffffff',
                      }}
                    >
                      <dt
                        style={{
                          fontWeight: 600,
                          color: glossaryTermColor,
                          lineHeight: 1.5,
                          marginBottom: '0.25rem',
                          fontSize: '1rem',
                          letterSpacing: '0.012em',
                          fontFamily: "'IBM Plex Sans', sans-serif",
                        }}
                      >
                        {item.term}
                      </dt>
                      <dd
                        style={{
                          color: stepTextColor,
                          lineHeight: 1.6,
                          fontSize: '1rem',
                          wordSpacing: '0.016em',
                          letterSpacing: '0.012em',
                          margin: 0,
                          fontFamily: "'IBM Plex Sans', sans-serif",
                        }}
                      >
                        {item.definition}
                      </dd>
                    </dl>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div
          style={{
            padding: '1rem 1.5rem',
            borderTop: `1px solid ${borderColor}`,
            background: footerBg,
            fontSize: '0.875rem',
            color: footerColor,
            lineHeight: 1.5,
            flexShrink: 0,
            letterSpacing: '0.012em',
            fontFamily: "'IBM Plex Sans', sans-serif",
          }}
        >
          Press{' '}
          <kbd
            style={{
              background: isDark ? 'rgba(255,255,255,0.1)' : '#e5e9f0',
              border: isDark ? '1px solid rgba(255,255,255,0.15)' : '1px solid #c1c7cd',
              padding: '1px 5px',
              borderRadius: '3px',
              fontSize: '0.8125rem',
              color: isDark ? '#c1c7cd' : '#161616',
              fontFamily: "'IBM Plex Mono', monospace",
            }}
          >
            Esc
          </kbd>{' '}
          or click outside to close
        </div>
      </div>
    </>
  )
}
