import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import Lab11WorkflowLab from './Lab11WorkflowLab'

vi.mock('@/context/AigcContext', () => ({
  useAigc: () => ({ apiUrl: 'http://localhost:8000', addAudit: vi.fn(), auditHistory: [] }),
}))

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
})
