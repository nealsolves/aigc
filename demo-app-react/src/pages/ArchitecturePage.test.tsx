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

  it('renders the current v0.3.3 boundary notes', () => {
    renderPage()
    expect(screen.getByText('Decorator Modes')).toBeInTheDocument()
    expect(screen.getByText('Phase A / Phase B')).toBeInTheDocument()
    expect(screen.getAllByText('ProvenanceGate').length).toBeGreaterThan(0)
    expect(screen.getByText('Artifact Provenance')).toBeInTheDocument()
    expect(screen.getByText('Audit Chain')).toBeInTheDocument()
    expect(screen.getByText('Lineage Analysis')).toBeInTheDocument()
    expect(screen.getByText('Pre-Pipeline Failures')).toBeInTheDocument()
    expect(screen.getByText('Risk History')).toBeInTheDocument()
    expect(screen.getByText('Async + Instance APIs')).toBeInTheDocument()
  })

  it('labels the page as v0.3.3', () => {
    renderPage()
    expect(screen.getByText('AIGC v0.3.3')).toBeInTheDocument()
  })

  it('renders diagram images', () => {
    renderPage()
    expect(screen.getByAltText('AIGC Component View')).toBeInTheDocument()
    expect(screen.getByAltText('AIGC Enforcement Pipeline')).toBeInTheDocument()
  })
})
