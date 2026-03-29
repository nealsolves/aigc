import { useState } from 'react'
import StatusBadge from '@/components/shared/StatusBadge'
import CodeBlock from '@/components/shared/CodeBlock'
import MetricCard from '@/components/shared/MetricCard'
import { getScenario } from '@/mock/scenarios'

// Deterministic mock HMAC — not cryptographically secure, for demo only
function mockSign(payload: string, key: string): string {
  let hash = 0
  const str = payload + key
  for (let i = 0; i < str.length; i++) {
    hash = ((hash << 5) - hash + str.charCodeAt(i)) | 0
  }
  return Math.abs(hash).toString(16).padStart(8, '0').repeat(8).slice(0, 64)
}

export default function Lab2Signing() {
  const [signed, setSigned] = useState(false)
  const [tampered, setTampered] = useState(false)
  const [sigKey, setSigKey] = useState('demo-key-v1')
  const scenario = getScenario('signing_basic')
  const payload = JSON.stringify({ result: scenario.output.result, role: 'doctor' })
  const signature = mockSign(payload, sigKey)
  const verifyPayload = tampered ? payload.replace('allergies', 'TAMPERED') : payload
  const valid = mockSign(verifyPayload, sigKey) === signature

  return (
    <div className="p-4 max-w-4xl mx-auto">
      <p className="font-mono text-xs mb-4" style={{ color: 'var(--text-secondary)' }}>
        // HMAC-SHA256 artifact signing and tamper detection
      </p>

      <div className="grid grid-cols-2 gap-4 mb-4">
        <div className="space-y-3">
          <div className="font-mono text-xs" style={{ color: 'var(--text-secondary)' }}>↳ Signing Key</div>
          <input
            value={sigKey}
            onChange={e => { setSigKey(e.target.value); setSigned(false) }}
            className="w-full font-mono text-[13px] px-3 py-2 rounded outline-none"
            style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-ui)', color: 'var(--text-primary)' }}
          />
          <CodeBlock code={payload} label="payload" />
          <button
            onClick={() => setSigned(true)}
            className="w-full font-mono text-sm py-2 rounded"
            style={{ background: 'var(--ibm-blue-60)', color: '#fff' }}
          >
            Sign Artifact →
          </button>
        </div>

        <div className="space-y-3">
          <div className="font-mono text-xs" style={{ color: 'var(--text-secondary)' }}>↳ Verification</div>
          {signed ? (
            <>
              <CodeBlock code={signature} label="signature (HMAC-SHA256)" />
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setTampered(t => !t)}
                  className="font-mono text-xs px-3 py-1.5 rounded transition-colors"
                  style={
                    tampered
                      ? { background: 'rgba(255,126,182,0.15)', color: 'var(--ibm-magenta-40)', border: '1px solid rgba(255,126,182,0.3)' }
                      : { color: 'var(--text-secondary)', border: '1px solid var(--border-ui)' }
                  }
                >
                  {tampered ? '⚡ tampered' : 'tamper payload'}
                </button>
                <StatusBadge status={valid ? 'PASS' : 'FAIL'} />
              </div>
              <div className="grid grid-cols-2 gap-2">
                <MetricCard value={signed ? '✓' : '—'} label="SIGNED" color="var(--ibm-teal-30)" />
                <MetricCard value={valid ? 'VALID' : 'INVALID'} label="SIGNATURE" color={valid ? 'var(--ibm-teal-30)' : 'var(--ibm-magenta-40)'} />
              </div>
              {!valid && (
                <div className="font-mono text-xs px-3 py-2 rounded" style={{ background: 'rgba(255,126,182,0.08)', border: '1px solid rgba(255,126,182,0.2)', color: 'var(--ibm-magenta-40)' }}>
                  // signature mismatch — payload was modified after signing
                </div>
              )}
            </>
          ) : (
            <div className="font-mono text-xs px-3 py-2 rounded" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-ui)', color: 'var(--text-secondary)' }}>
              // sign an artifact first
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
