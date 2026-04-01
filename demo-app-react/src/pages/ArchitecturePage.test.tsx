import { render, screen } from '@testing-library/react'
import { ThemeProvider } from '@/theme/ThemeContext'
import ArchitecturePage from './ArchitecturePage'

function renderPage() {
  return render(
    <ThemeProvider>
      <ArchitecturePage />
    </ThemeProvider>
  )
}

describe('ArchitecturePage', () => {
  it('renders the Component View section', () => {
    renderPage()
    expect(screen.getByText('Component View')).toBeInTheDocument()
  })

  it('renders the Enforcement Pipeline section', () => {
    renderPage()
    expect(screen.getByText('Enforcement Pipeline')).toBeInTheDocument()
  })

  it('renders the Key Boundaries section', () => {
    renderPage()
    expect(screen.getByText('Key Boundaries')).toBeInTheDocument()
  })

  it('renders all four Key Boundary note cards', () => {
    renderPage()
    expect(screen.getByText('Post-Call Governance')).toBeInTheDocument()
    expect(screen.getByText('Audit Chain')).toBeInTheDocument()
    expect(screen.getByText('Compliance Export')).toBeInTheDocument()
    expect(screen.getByText('Pre-Pipeline Failures')).toBeInTheDocument()
  })

  it('renders diagram images', () => {
    renderPage()
    expect(screen.getByAltText('AIGC Component View')).toBeInTheDocument()
    expect(screen.getByAltText('AIGC Enforcement Pipeline')).toBeInTheDocument()
  })
})
