interface Props {
  isOpen: boolean
  onOpen: () => void
}

export default function HelpButton({ isOpen, onOpen }: Props) {
  return (
    <button
      onClick={onOpen}
      aria-label="Open lab guide"
      aria-expanded={isOpen}
      style={{
        position: 'fixed',
        bottom: '1.5rem',
        right: '1.5rem',
        zIndex: 100,
        display: 'flex',
        alignItems: 'center',
        gap: '0.5rem',
        padding: '0.625rem 1.125rem',
        borderRadius: '2rem',
        border: 'none',
        background: 'var(--ibm-blue-60)',
        color: '#ffffff',
        fontFamily: "'IBM Plex Sans', sans-serif",
        fontSize: '0.9375rem',
        fontWeight: 500,
        lineHeight: 1.5,
        letterSpacing: '0.012em',
        cursor: 'pointer',
        boxShadow: '0 4px 12px rgba(15,98,254,0.35)',
      }}
    >
      <span
        style={{
          width: '1.25rem',
          height: '1.25rem',
          borderRadius: '50%',
          border: '2px solid rgba(255,255,255,0.75)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: '0.75rem',
          fontWeight: 700,
          lineHeight: 1,
          flexShrink: 0,
        }}
        aria-hidden="true"
      >
        ?
      </span>
      Guide
    </button>
  )
}
