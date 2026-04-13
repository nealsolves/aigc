import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import Lab10SplitEnforcementExplorer from './Lab10SplitEnforcementExplorer'
import { AigcProvider } from '@/context/AigcContext'

vi.mock('@/context/AigcContext', () => ({
  useAigc: () => ({ apiUrl: 'http://localhost:8000', addAudit: vi.fn(), auditHistory: [] }),
  AigcProvider: ({ children }: { children: React.ReactNode }) => children,
}))

describe('Lab10SplitEnforcementExplorer', () => {
  it('renders the lab comment line', () => {
    render(<Lab10SplitEnforcementExplorer />)
    expect(screen.getByText(/split enforcement/i)).toBeInTheDocument()
  })

  it('renders Phase A and Phase B labels', () => {
    render(<Lab10SplitEnforcementExplorer />)
    expect(screen.getAllByText(/phase a/i).length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText(/phase b/i).length).toBeGreaterThanOrEqual(1)
  })

  it('renders the Run Split Trace button', () => {
    render(<Lab10SplitEnforcementExplorer />)
    expect(screen.getByRole('button', { name: /run split trace/i })).toBeInTheDocument()
  })

  it('renders Phase A gate names from a successful split-trace response', async () => {
    const payload = {
      phase_a: {
        result: 'PASS',
        gates_evaluated: ['guard_evaluation', 'role_validation', 'precondition_validation'],
        failures: [],
        blocked: false,
      },
      phase_b: {
        result: 'PASS',
        gates_evaluated: ['schema_validation'],
        failures: [],
        blocked: false,
      },
      artifact: {
        enforcement_result: 'PASS',
        model_provider: 'mock',
        model_identifier: 'mock-model',
        role: 'user',
        metadata: {
          enforcement_mode: 'split',
          pre_call_gates_evaluated: ['guard_evaluation', 'role_validation', 'precondition_validation'],
          post_call_gates_evaluated: ['schema_validation'],
        },
      },
      combined_result: 'PASS',
      error: null,
    }

    vi.stubGlobal('fetch', vi.fn(() =>
      Promise.resolve({ ok: true, json: async () => payload }),
    ))

    const user = userEvent.setup()
    render(<AigcProvider><Lab10SplitEnforcementExplorer /></AigcProvider>)
    await user.click(screen.getByRole('button', { name: /run split trace/i }))

    expect(await screen.findByText(/→ guard_evaluation/)).toBeInTheDocument()
    expect(screen.getByText(/→ role_validation/)).toBeInTheDocument()
    expect(screen.getByText(/→ precondition_validation/)).toBeInTheDocument()

    vi.unstubAllGlobals()
  })
})
