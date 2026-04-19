import { useState, useCallback, useEffect, useRef } from 'react'
import { useAigc } from '@/context/AigcContext'
import type { Artifact } from '@/types/artifact'

export function useApi<T = unknown>() {
  const { apiUrl, addAudit } = useAigc()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const requestGeneration = useRef(0)
  const isMounted = useRef(true)

  useEffect(() => {
    return () => {
      isMounted.current = false
    }
  }, [])

  const call = useCallback(async (path: string, body?: unknown): Promise<T | null> => {
    const generation = ++requestGeneration.current
    if (isMounted.current) {
      setLoading(true)
      setError(null)
    }
    try {
      const isGet = body === undefined
      const res = await fetch(`${apiUrl}${path}`, {
        method: isGet ? 'GET' : 'POST',
        headers: isGet ? {} : { 'Content-Type': 'application/json' },
        body: isGet ? undefined : JSON.stringify(body),
      })
      if (!res.ok) throw new Error(`API error: ${res.status} ${res.statusText}`)
      const data = await res.json() as T
      if (!isMounted.current || generation !== requestGeneration.current) {
        return null
      }
      if (data && typeof data === 'object' && 'artifact' in (data as object)) {
        const artifact = (data as unknown as { artifact: Artifact | null }).artifact
        // Only add invocation audit artifacts (those with enforcement_result).
        // Workflow artifacts from /api/workflow/v090/run have a different shape
        // (status/steps) and must not be mixed into the invocation audit history.
        if (artifact && 'enforcement_result' in artifact) addAudit(artifact)
      }
      return data
    } catch (err) {
      if (isMounted.current && generation === requestGeneration.current) {
        setError(err instanceof Error ? err.message : String(err))
      }
      return null
    } finally {
      if (isMounted.current && generation === requestGeneration.current) {
        setLoading(false)
      }
    }
  }, [apiUrl, addAudit])

  return { call, loading, error }
}
