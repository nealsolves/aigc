import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import Lab10SplitEnforcementExplorer from './Lab10SplitEnforcementExplorer'

vi.mock('@/context/AigcContext', () => ({
  useAigc: () => ({ apiUrl: 'http://localhost:8000', addAudit: vi.fn(), auditHistory: [] }),
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
})
