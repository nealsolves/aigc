import { useState } from 'react'
import StatusBadge from '@/components/shared/StatusBadge'
import CodeBlock from '@/components/shared/CodeBlock'
import MetricCard from '@/components/shared/MetricCard'
import { useApi } from '@/hooks/useApi'
import type { Artifact } from '@/types/artifact'

interface KeyResponse   { key: string }
interface SignResponse   { artifact: Artifact | null; error: string | null }
interface VerifyResponse { valid: boolean }

export default function Lab2Signing() {
  const [sigKey, setSigKey]     = useState('')
  const [artifact, setArtifact] = useState<Artifact | null>(null)
  const [tampered, setTampered] = useState(false)
  const [verified, setVerified] = useState<boolean | null>(null)

  const { call: callKey,    loading: loadingKey }    = useApi<KeyResponse>()
  const { call: callSign,   loading: loadingSign }   = useApi<SignResponse>()
  const { call: callVerify, loading: loadingVerify } = useApi<VerifyResponse>()

  const generateKey = async () => {
    const res = await callKey('/api/sign/generate-key', {})
    if (res) { setSigKey(res.key); setArtifact(null); setVerified(null) }
  }

  const sign = async () => {
    if (!sigKey) return
    const res = await callSign('/api/sign/enforce', { scenario_key: 'signing_basic', key: sigKey })
    if (res?.artifact) { setArtifact(res.artifact); setTampered(false); setVerified(null) }
  }

  const verify = async () => {
    if (!artifact || !sigKey) return
    const payload = tampered
      ? { ...artifact, enforcement_result: artifact.enforcement_result === 'PASS' ? 'FAIL' : 'PASS' }
      : artifact
    const res = await callVerify('/api/sign/verify', { artifact: payload, key: sigKey })
    if (res !== null) setVerified(res.valid)
  }

  return (
    <div className="p-4 max-w-4xl mx-auto">
      <p className="font-mono text-xs mb-4" style={{ color: 'var(--text-secondary)' }}>
        // HMAC-SHA256 artifact signing and tamper detection
      </p>

      <div className="grid grid-cols-2 gap-4 mb-4">
        <div className="space-y-3">
          <div className="font-mono text-xs" style={{ color: 'var(--text-secondary)' }}>↳ Signing Key</div>
          <div className="flex gap-2">
            <input
              value={sigKey}
              onChange={e => { setSigKey(e.target.value); setArtifact(null); setVerified(null) }}
              placeholder="generate or paste hex key"
              className="flex-1 font-mono text-[13px] px-3 py-2 rounded outline-none"
              style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-ui)', color: 'var(--text-primary)' }}
            />
            <button
              onClick={generateKey}
              disabled={loadingKey}
              className="font-mono text-xs px-3 py-2 rounded"
              style={{ background: 'var(--ibm-teal-60)', color: '#fff', opacity: loadingKey ? 0.7 : 1 }}
            >
              {loadingKey ? '…' : 'Generate'}
            </button>
          </div>
          {sigKey && <CodeBlock code={`key: ${sigKey.slice(0, 16)}...`} label="signing_key (hex)" />}
          <button
            onClick={sign}
            disabled={!sigKey || loadingSign}
            className="w-full font-mono text-sm py-2 rounded"
            style={{ background: 'var(--ibm-blue-60)', color: '#fff', opacity: (!sigKey || loadingSign) ? 0.7 : 1 }}
          >
            {loadingSign ? 'Signing…' : 'Sign Artifact →'}
          </button>
        </div>

        <div className="space-y-3">
          <div className="font-mono text-xs" style={{ color: 'var(--text-secondary)' }}>↳ Verification</div>
          {artifact ? (
            <>
              <CodeBlock code={`signature: ${(artifact.signature ?? '').slice(0, 16)}...`} label="HMAC-SHA256 signature" />
              <div className="flex items-center gap-2">
                <button
                  onClick={() => { setTampered(t => !t); setVerified(null) }}
                  className="font-mono text-xs px-3 py-1.5 rounded transition-colors"
                  style={
                    tampered
                      ? { background: 'rgba(255,126,182,0.15)', color: 'var(--ibm-magenta-40)', border: '1px solid rgba(255,126,182,0.3)' }
                      : { color: 'var(--text-secondary)', border: '1px solid var(--border-ui)', background: 'var(--bg-surface)' }
                  }
                >
                  {tampered ? '⚡ tampered' : 'tamper payload'}
                </button>
                <button
                  onClick={verify}
                  disabled={loadingVerify}
                  className="font-mono text-xs px-3 py-1.5 rounded"
                  style={{ background: 'var(--ibm-blue-60)', color: '#fff', opacity: loadingVerify ? 0.7 : 1 }}
                >
                  Verify
                </button>
              </div>
              {verified !== null && <StatusBadge status={verified ? 'PASS' : 'FAIL'} />}
              <div className="grid grid-cols-2 gap-2">
                <MetricCard value="✓" label="SIGNED" color="var(--ibm-teal-30)" />
                <MetricCard
                  value={verified === null ? '—' : verified ? 'VALID' : 'INVALID'}
                  label="SIGNATURE"
                  color={verified === false ? 'var(--ibm-magenta-40)' : 'var(--ibm-teal-30)'}
                />
              </div>
              {verified === false && (
                <div className="font-mono text-xs px-3 py-2 rounded" style={{ background: 'rgba(255,126,182,0.08)', border: '1px solid rgba(255,126,182,0.2)', color: 'var(--ibm-magenta-40)' }}>
                  // signature mismatch — payload was modified after signing
                </div>
              )}
            </>
          ) : (
            <div className="font-mono text-xs px-3 py-2 rounded" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-ui)', color: 'var(--text-secondary)' }}>
              // generate a key and sign an artifact first
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
