import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import Lab11WorkflowLab from './Lab11WorkflowLab'
import { useApi } from '@/hooks/useApi'

vi.mock('@/context/AigcContext', () => ({
  useAigc: () => ({ apiUrl: 'http://localhost:8000', addAudit: vi.fn(), auditHistory: [] }),
}))

vi.mock('@/hooks/useApi', () => ({
  useApi: vi.fn(),
}))

type ApiHookState = {
  call: (path: string, body?: unknown) => Promise<unknown>
  loading: boolean
  error: string | null
}

let useApiStates: ApiHookState[] = []
let useApiCallCount = 0

function buildApiState(overrides: Partial<ApiHookState> = {}): ApiHookState {
  return {
    call: async () => null,
    loading: false,
    error: null,
    ...overrides,
  }
}

function mockUseApiStates(states: ApiHookState[]) {
  useApiStates = states
  useApiCallCount = 0
  vi.mocked(useApi).mockImplementation(() => {
    const state = useApiStates[useApiCallCount % useApiStates.length]
    useApiCallCount += 1
    return state
  })
}

beforeEach(() => {
  mockUseApiStates([
    buildApiState(),
    buildApiState(),
    buildApiState(),
  ])
})

describe('Lab11WorkflowLab', () => {
  it('renders the lab comment line', () => {
    render(<Lab11WorkflowLab />)
    expect(screen.getByText(/workflow governance/i)).toBeInTheDocument()
  })

  it('renders Start Here tab button', () => {
    render(<Lab11WorkflowLab />)
    expect(screen.getByRole('button', { name: /start here/i })).toBeInTheDocument()
  })

  it('renders Failure & Fix tab button', () => {
    render(<Lab11WorkflowLab />)
    expect(screen.getByRole('button', { name: /failure.*fix/i })).toBeInTheDocument()
  })

  it('renders Governed vs Ungoverned tab button', () => {
    render(<Lab11WorkflowLab />)
    expect(screen.getByRole('button', { name: /governed vs ungoverned/i })).toBeInTheDocument()
  })

  it('renders Evidence View tab button', () => {
    render(<Lab11WorkflowLab />)
    expect(screen.getByRole('button', { name: /evidence view/i })).toBeInTheDocument()
  })

  it('renders Run Minimal button on Start Here tab', () => {
    render(<Lab11WorkflowLab />)
    expect(screen.getByRole('button', { name: /run minimal/i })).toBeInTheDocument()
  })

  it('disables diagnosis while a failure run is still in flight', () => {
    mockUseApiStates([
      buildApiState({ loading: true }),
      buildApiState(),
      buildApiState(),
    ])

    render(<Lab11WorkflowLab />)
    fireEvent.click(screen.getByRole('button', { name: /failure.*fix/i }))

    expect(screen.getByRole('button', { name: /run doctor diagnosis/i })).toBeDisabled()
  })

  it('shows guidance when doctor has no prior failure to diagnose', async () => {
    const diagnoseCall = vi.fn(async () => ({
      findings: [],
      source: 'no_prior_failure',
    }))

    mockUseApiStates([
      buildApiState(),
      buildApiState(),
      buildApiState({ call: diagnoseCall }),
    ])

    render(<Lab11WorkflowLab />)
    fireEvent.click(screen.getByRole('button', { name: /failure.*fix/i }))
    fireEvent.click(screen.getByRole('button', { name: /run doctor diagnosis/i }))

    expect(diagnoseCall).toHaveBeenCalledWith('/api/workflow/v090/diagnose')
    expect(await screen.findByText(/trigger failure first to generate a workflow run/i)).toBeInTheDocument()
  })
})
