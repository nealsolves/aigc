import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import Lab8GovernedKnowledgeBase from './Lab8GovernedKnowledgeBase'

vi.mock('@/context/AigcContext', () => ({
  useAigc: () => ({ apiUrl: 'http://localhost:8000', addAudit: vi.fn(), auditHistory: [] }),
}))

describe('Lab8GovernedKnowledgeBase', () => {
  it('renders the lab comment line', () => {
    render(<Lab8GovernedKnowledgeBase />)
    expect(screen.getByText(/governed knowledge base/i)).toBeInTheDocument()
  })

  it('renders the scenario selector', () => {
    render(<Lab8GovernedKnowledgeBase />)
    expect(screen.getByRole('combobox')).toBeInTheDocument()
  })

  it('renders the Run KB Query button', () => {
    render(<Lab8GovernedKnowledgeBase />)
    expect(screen.getByRole('button', { name: /run kb query/i })).toBeInTheDocument()
  })
})
