import { render, screen, fireEvent } from '@testing-library/react'
import HelpDrawer from './HelpDrawer'
import { ThemeProvider } from '@/theme/ThemeContext'

function renderDrawer(isOpen: boolean, onClose = vi.fn(), labId = 1) {
  return render(
    <ThemeProvider>
      <HelpDrawer labId={labId} isOpen={isOpen} onClose={onClose} />
    </ThemeProvider>
  )
}

describe('HelpDrawer', () => {
  it('is not in the document when isOpen is false', () => {
    renderDrawer(false)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('renders when isOpen is true', () => {
    renderDrawer(true)
    expect(screen.getByRole('dialog')).toBeInTheDocument()
  })

  it('shows the Lab 1 title from helpContent', () => {
    renderDrawer(true)
    expect(screen.getByText('Risk Scoring Guide')).toBeInTheDocument()
  })

  it('uses the current lab labels for renamed guides', () => {
    renderDrawer(true, vi.fn(), 2)
    expect(screen.getByText('Lab 2 — Signing & Verification')).toBeInTheDocument()

    renderDrawer(true, vi.fn(), 7)
    expect(screen.getByText('Lab 7 — Compliance Dashboard')).toBeInTheDocument()

    renderDrawer(true, vi.fn(), 8)
    expect(screen.getByText('Lab 8 — Governed Knowledge Base')).toBeInTheDocument()

    renderDrawer(true, vi.fn(), 10)
    expect(screen.getByText('Lab 10 — Split Enforcement Explorer')).toBeInTheDocument()
  })

  it('shows at least one step title', () => {
    renderDrawer(true)
    expect(screen.getByText('Choose a preset scenario')).toBeInTheDocument()
  })

  it('renders the narrative framework sections for first-time users', () => {
    renderDrawer(true)
    expect(screen.getByText('Why This Matters')).toBeInTheDocument()
    expect(screen.getByText('What This Lab Shows')).toBeInTheDocument()
    expect(screen.getByText('How To Navigate')).toBeInTheDocument()
    expect(screen.getByText('Key Takeaway')).toBeInTheDocument()
  })

  it('calls onClose when the close button is clicked', () => {
    const onClose = vi.fn()
    renderDrawer(true, onClose)
    fireEvent.click(screen.getByRole('button', { name: /close guide/i }))
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('calls onClose when Escape is pressed', () => {
    const onClose = vi.fn()
    renderDrawer(true, onClose)
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('calls onClose when the backdrop is clicked', () => {
    const onClose = vi.fn()
    renderDrawer(true, onClose)
    fireEvent.click(screen.getByTestId('help-backdrop'))
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('renders a glossary toggle when helpContent has glossary', () => {
    renderDrawer(true)
    expect(screen.getByRole('button', { name: /glossary/i })).toBeInTheDocument()
  })

  it('shows a glossary term on toggle open and hides it on toggle close', () => {
    renderDrawer(true)
    const glossaryBtn = screen.getByRole('button', { name: /glossary/i })

    // Term should not be visible before opening
    expect(screen.queryByText('Risk Mode')).not.toBeInTheDocument()

    // Click to open
    fireEvent.click(glossaryBtn)
    expect(screen.getByText('Risk Mode')).toBeInTheDocument()

    // Click to close
    fireEvent.click(glossaryBtn)
    expect(screen.queryByText('Risk Mode')).not.toBeInTheDocument()
  })

  it('renders without crashing when given an invalid labId (falls back to Lab 1)', () => {
    renderDrawer(true, vi.fn(), 99)
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(screen.getByText('Risk Scoring Guide')).toBeInTheDocument()
  })
})
