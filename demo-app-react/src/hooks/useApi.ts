import { useState, useCallback } from 'react'
import { useAigc } from '@/context/AigcContext'
import type { Artifact } from '@/types/artifact'

export function useApi<T = unknown>() {
  const { apiUrl, addAudit } = useAigc()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const call = useCallback(async (path: string, body?: unknown): Promise<T | null> => {
    setLoading(true)
    setError(null)
    try {
      const isGet = body === undefined
      const res = await fetch(`${apiUrl}${path}`, {
        method: isGet ? 'GET' : 'POST',
        headers: isGet ? {} : { 'Content-Type': 'application/json' },
        body: isGet ? undefined : JSON.stringify(body),
      })
      if (!res.ok) throw new Error(`API error: ${res.status} ${res.statusText}`)
      const data = await res.json() as T
      if (data && typeof data === 'object' && 'artifact' in (data as object)) {
        const artifact = (data as unknown as { artifact: Artifact | null }).artifact
        if (artifact) addAudit(artifact)
      }
      return data
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
      return null
    } finally {
      setLoading(false)
    }
  }, [apiUrl, addAudit])

  return { call, loading, error }
}
