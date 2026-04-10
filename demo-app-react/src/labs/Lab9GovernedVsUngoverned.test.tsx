import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import Lab9GovernedVsUngoverned from './Lab9GovernedVsUngoverned'

vi.mock('@/context/AigcContext', () => ({
  useAigc: () => ({ apiUrl: 'http://localhost:8000', addAudit: vi.fn(), auditHistory: [] }),
}))

describe('Lab9GovernedVsUngoverned', () => {
  it('renders the lab comment line', () => {
    render(<Lab9GovernedVsUngoverned />)
    expect(screen.getByText(/governed vs.*ungoverned/i)).toBeInTheDocument()
  })

  it('renders governed and ungoverned panel labels', () => {
    render(<Lab9GovernedVsUngoverned />)
    expect(screen.getAllByText(/governed/i).length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText(/ungoverned/i).length).toBeGreaterThanOrEqual(1)
  })

  it('renders the Compare button', () => {
    render(<Lab9GovernedVsUngoverned />)
    expect(screen.getByRole('button', { name: /compare/i })).toBeInTheDocument()
  })
})
