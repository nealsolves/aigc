import { render, screen, fireEvent } from '@testing-library/react'
import HelpDrawer from './HelpDrawer'
import { ThemeProvider } from '@/theme/ThemeContext'

function renderDrawer(isOpen: boolean, onClose = vi.fn()) {
  return render(
    <ThemeProvider>
      <HelpDrawer labId={1} isOpen={isOpen} onClose={onClose} />
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

  it('shows at least one step title', () => {
    renderDrawer(true)
    expect(screen.getByText('Choose a preset scenario')).toBeInTheDocument()
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
})
