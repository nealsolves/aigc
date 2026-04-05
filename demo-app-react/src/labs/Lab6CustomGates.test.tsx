import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi } from 'vitest'
import Lab6CustomGates from '@/labs/Lab6CustomGates'
import { AigcProvider } from '@/context/AigcContext'

function mockJson(data: unknown) {
  return Promise.resolve({
    ok: true,
    json: async () => data,
  })
}

describe('Lab6CustomGates', () => {
  it('surfaces authorization-phase gates and gate-specific scenarios', async () => {
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)

      if (url.includes('/api/gate/session_authorization_gate')) {
        return mockJson({
          name: 'session_authorization_gate',
          insertion_point: 'pre_authorization',
          description: 'Fails if the caller session is not marked authorized in context.',
          source: 'class SessionAuthorizationGate: ...',
        })
      }

      if (url.includes('/api/gate/domain_allowlist_gate')) {
        return mockJson({
          name: 'domain_allowlist_gate',
          insertion_point: 'post_authorization',
          description: 'Fails if context.domain is outside the demo allowlist.',
          source: 'class DomainAllowlistGate: ...',
        })
      }

      if (url.includes('/api/gate/run')) {
        const body = JSON.parse(String(init?.body ?? '{}'))
        expect(body.gate_name).toBe('domain_allowlist_gate')
        expect(body.scenario_key).toBe('gate_untrusted_domain')
        return mockJson({
          artifact: {
            enforcement_result: 'FAIL',
            model_provider: 'mock',
            model_identifier: 'mock-model',
            role: 'doctor',
            metadata: {
              gates_evaluated: ['guard_evaluation', 'role_validation', 'custom:domain_allowlist_gate'],
            },
          },
          gate_result: {
            name: 'domain_allowlist_gate',
            insertion_point: 'post_authorization',
            passed: false,
            failures: [{ gate: 'domain_allowlist_gate', message: "domain 'finance' is outside the allowlist" }],
            metadata: {},
          },
          error: null,
        })
      }

      throw new Error(`Unhandled fetch in test: ${url}`)
    }))

    const user = userEvent.setup()

    render(
      <AigcProvider>
        <Lab6CustomGates />
      </AigcProvider>,
    )

    expect(await screen.findByText('session_authorization_gate')).toBeInTheDocument()
    expect(screen.getAllByText('pre_authorization').length).toBeGreaterThanOrEqual(1)
    expect(screen.getByRole('button', { name: 'Unauthorized Session' })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'domain_allowlist_gate' }))

    expect((await screen.findAllByText('post_authorization')).length).toBeGreaterThanOrEqual(1)
    expect(screen.getByRole('button', { name: 'Allowed Domain' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Untrusted Domain' }))
    await user.click(screen.getByRole('button', { name: /Run Gate/i }))

    expect(await screen.findByText(/domain_allowlist_gate @ post_authorization/i)).toBeInTheDocument()
    expect(screen.getByText(/outside the allowlist/i)).toBeInTheDocument()

    vi.unstubAllGlobals()
  })
})
