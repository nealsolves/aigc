import { renderHook, act } from '@testing-library/react'
import { AigcProvider, useAigc } from '@/context/AigcContext'
import type { Artifact } from '@/types/artifact'

const STUB: Artifact = {
  enforcement_result: 'PASS',
  model_provider: 'test',
  model_identifier: 'test-model',
  role: 'doctor',
}

describe('AigcContext', () => {
  it('starts with empty audit history', () => {
    const { result } = renderHook(() => useAigc(), { wrapper: AigcProvider })
    expect(result.current.auditHistory).toHaveLength(0)
  })

  it('addAudit appends an artifact', () => {
    const { result } = renderHook(() => useAigc(), { wrapper: AigcProvider })
    act(() => result.current.addAudit(STUB))
    expect(result.current.auditHistory).toHaveLength(1)
    expect(result.current.auditHistory[0].role).toBe('doctor')
  })

  it('clearHistory empties the list', () => {
    const { result } = renderHook(() => useAigc(), { wrapper: AigcProvider })
    act(() => result.current.addAudit(STUB))
    act(() => result.current.clearHistory())
    expect(result.current.auditHistory).toHaveLength(0)
  })

  it('apiUrl defaults to localhost:8000 when env var absent', () => {
    const { result } = renderHook(() => useAigc(), { wrapper: AigcProvider })
    expect(result.current.apiUrl).toBe('http://localhost:8000')
  })
})
