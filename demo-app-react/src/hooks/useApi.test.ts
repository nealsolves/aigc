import { renderHook, act, waitFor } from '@testing-library/react'
import { vi } from 'vitest'
import { useApi } from '@/hooks/useApi'
import { AigcProvider } from '@/context/AigcContext'

describe('useApi', () => {
  it('starts idle', () => {
    const { result } = renderHook(() => useApi(), { wrapper: AigcProvider })
    expect(result.current.loading).toBe(false)
    expect(result.current.error).toBeNull()
  })

  it('returns data on success', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce({
      ok: true,
      json: async () => ({ status: 'ok' }),
    }))

    const { result } = renderHook(() => useApi<{ status: string }>(), { wrapper: AigcProvider })
    let data: { status: string } | null = null
    await act(async () => { data = await result.current.call('/health') })
    expect(data).toEqual({ status: 'ok' })
    expect(result.current.loading).toBe(false)
    vi.unstubAllGlobals()
  })

  it('sets error on fetch failure', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValueOnce(new Error('Network error')))

    const { result } = renderHook(() => useApi(), { wrapper: AigcProvider })
    await act(async () => { await result.current.call('/health') })
    await waitFor(() => expect(result.current.error).toBe('Network error'))
    vi.unstubAllGlobals()
  })
})
