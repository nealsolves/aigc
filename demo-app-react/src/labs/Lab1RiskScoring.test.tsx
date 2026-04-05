import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi } from 'vitest'
import Lab1RiskScoring from '@/labs/Lab1RiskScoring'
import { AigcProvider } from '@/context/AigcContext'

function mockJson(data: unknown) {
  return Promise.resolve({
    ok: true,
    json: async () => data,
  })
}

describe('Lab1RiskScoring', () => {
  it('renders split Phase A evidence for the dedicated split demo scenario', async () => {
    expect.assertions(5)
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)

      if (url.includes('/api/scenarios/medium_risk_medical')) {
        return mockJson({
          prompt: 'What are the common side effects of ibuprofen?',
          context: { domain: 'medical', human_review_required: true, role_declared: true, schema_exists: true },
          policy: 'medical_ai.yaml',
          model_provider: 'mock',
          model_id: 'mock-model',
          role: 'doctor',
        })
      }

      if (url.includes('/api/scenarios/split_precall_block')) {
        return mockJson({
          prompt: 'Draft discharge instructions for patient #9812.',
          context: { domain: 'medical', human_review_required: true, schema_exists: true },
          policy: 'medical_ai.yaml',
          model_provider: 'mock',
          model_id: 'mock-model',
          role: 'doctor',
        })
      }

      if (url.includes('/api/enforce')) {
        const body = JSON.parse(String(init?.body ?? '{}'))
        expect(body.flow).toBe('split')
        expect(body.scenario_key).toBe('split_precall_block')
        return mockJson({
          artifact: {
            enforcement_result: 'FAIL',
            model_provider: 'mock',
            model_identifier: 'mock-model',
            role: 'doctor',
            policy_file: 'medical_ai.yaml',
            metadata: {
              enforcement_mode: 'split_pre_call_only',
              pre_call_gates_evaluated: ['guard_evaluation', 'role_validation', 'precondition_validation'],
            },
          },
          error: 'Missing required precondition: role_declared',
        })
      }

      throw new Error(`Unhandled fetch in test: ${url}`)
    }))

    const user = userEvent.setup()

    render(
      <AigcProvider>
        <Lab1RiskScoring />
      </AigcProvider>,
    )

    await user.click(screen.getByRole('button', { name: /Split Demo: Missing Role Declaration/i }))
    await user.click(screen.getByRole('button', { name: /Phase A authorizes before the model call/i }))
    await user.click(screen.getByRole('button', { name: /Run Enforcement/i }))

    expect(await screen.findByText(/Phase A blocked before the model call/i)).toBeInTheDocument()
    expect(screen.getByText('split_pre_call_only')).toBeInTheDocument()
    expect(screen.getByText('precondition_validation')).toBeInTheDocument()

    vi.unstubAllGlobals()
  })
})
