import { useState, type ReactNode } from 'react'
import { useTheme } from '@/theme/ThemeContext'

export default function ArchitecturePage() {
  const { theme } = useTheme()

  const base = import.meta.env.BASE_URL
  const componentSvg = theme === 'dark'
    ? `${base}diagrams/aigc_architecture_component.svg`
    : `${base}diagrams/aigc_architecture_component_light.svg`

  const pipelineSvg = theme === 'dark'
    ? `${base}diagrams/aigc_architecture_pipeline.svg`
    : `${base}diagrams/aigc_architecture_pipeline_light.svg`

  return (
    <div style={{ maxWidth: 1200, margin: '0 auto', padding: '48px 40px' }}>
      <div
        className="font-mono font-light text-xs tracking-widest mb-1"
        style={{ color: 'var(--ibm-cyan-30)', textTransform: 'uppercase' }}
      >
        AIGC v0.3.2
      </div>
      <div
        className="font-mono font-light text-xs mb-14"
        style={{ color: 'var(--text-secondary)' }}
      >
        Runtime Architecture Diagrams
      </div>

      <DiagramSection
        num="01"
        title="Component View"
        description="How the host application, SDK enforcement core, policy layer, and operational utilities connect at runtime."
        src={componentSvg}
        alt="AIGC Component View"
      />

      <DiagramSection
        num="02"
        title="Enforcement Pipeline"
        description="The current runtime boundary for v0.3.2. Phase A runs before the model call in split mode, Phase B runs after output exists, and unified mode keeps the same ordered gates inside one call."
        src={pipelineSvg}
        alt="AIGC Enforcement Pipeline"
      />

      <div>
        <SectionHeader num="03" title="Key Boundaries" />
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: '1fr 1fr',
            gap: 16,
            marginTop: 20,
          }}
        >
          <NoteCard label="Decorator Modes">
            <Code>@governed</Code> defaults to unified post-call enforcement for backward compatibility. Set <Code>pre_call_enforcement=True</Code> to run Phase A before the wrapped function and Phase B after it returns.
          </NoteCard>
          <NoteCard label="Phase A / Phase B">
            Split mode moves the model call boundary between <Code>post_authorization</Code> and <Code>pre_output</Code>. Unified mode still evaluates the same ordered gates in one enforcement call.
          </NoteCard>
          <NoteCard label="Audit Chain">
            <Code>AuditChain</Code> is not part of the automatic enforcement pipeline. It is an opt-in utility the host applies to artifacts after enforcement.
          </NoteCard>
          <NoteCard label="Compliance Export">
            <Code>aigc compliance export</Code> is an offline analysis step over stored audit artifacts, not a live runtime gate.
          </NoteCard>
          <NoteCard label="Pre-Pipeline Failures">
            Pre-pipeline failures produce schema-valid FAIL artifacts with <Code>policy_version: &quot;unknown&quot;</Code>, but bypass the core gate sequence.
          </NoteCard>
          <NoteCard label="Async + Instance APIs">
            <Code>enforce_invocation_async</Code>, <Code>enforce_pre_call_async</Code>, <Code>enforce_post_call_async</Code>, and the matching <Code>AIGC</Code> instance methods ship in the v0.3.2 runtime.
          </NoteCard>
        </div>
      </div>
    </div>
  )
}

function DiagramSection({ num, title, description, src, alt }: {
  num: string
  title: string
  description: string
  src: string
  alt: string
}) {
  const [imgError, setImgError] = useState(false)

  return (
    <div className="mb-16">
      <SectionHeader num={num} title={title} />
      <p
        className="text-xs mb-5"
        style={{ color: 'var(--text-secondary)', marginLeft: 40 }}
      >
        {description}
      </p>
      <div
        style={{
          background: 'var(--bg-base)',
          border: '1px solid var(--border-ui)',
          borderRadius: 12,
          padding: 16,
          overflowX: 'auto',
        }}
      >
        {imgError ? (
          <div
            style={{
              padding: 32,
              textAlign: 'center',
              color: 'var(--text-secondary)',
              fontFamily: '"IBM Plex Mono", monospace',
              fontSize: 12,
              border: '1px dashed var(--border-ui)',
              borderRadius: 8,
            }}
          >
            {alt} unavailable
          </div>
        ) : (
          <img
            src={src}
            alt={alt}
            style={{ width: '100%', height: 'auto', display: 'block' }}
            onError={() => setImgError(true)}
          />
        )}
      </div>
    </div>
  )
}

function SectionHeader({ num, title }: { num: string; title: string }) {
  return (
    <div
      className="flex items-baseline gap-4 mb-6 pb-4"
      style={{ borderBottom: '1px solid var(--border-ui)' }}
    >
      <span
        className="font-mono font-bold text-[11px] tracking-widest"
        style={{ color: 'var(--ibm-cyan-30)', minWidth: 24 }}
      >
        {num}
      </span>
      <span className="text-xl font-semibold" style={{ color: 'var(--text-primary)' }}>
        {title}
      </span>
    </div>
  )
}

function NoteCard({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div
      style={{
        background: 'var(--bg-surface)',
        border: '1px solid var(--border-ui)',
        borderRadius: 8,
        padding: '20px 24px',
      }}
    >
      <div
        className="font-mono font-bold text-[11px] tracking-widest uppercase mb-2"
        style={{ color: 'var(--ibm-cyan-30)' }}
      >
        {label}
      </div>
      <p className="text-[13px] leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
        {children}
      </p>
    </div>
  )
}

function Code({ children }: { children: ReactNode }) {
  return (
    <code
      className="font-mono text-[12px]"
      style={{
        color: 'var(--ibm-cyan-30)',
        background: 'rgba(130,207,255,0.1)',
        padding: '1px 5px',
        borderRadius: 3,
      }}
    >
      {children}
    </code>
  )
}
