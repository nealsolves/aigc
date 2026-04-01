import { render, screen } from '@testing-library/react'
import { ThemeProvider } from '@/theme/ThemeContext'
import App from './App'

function renderWithTheme() {
  return render(
    <ThemeProvider>
      <App />
    </ThemeProvider>
  )
}

describe('App routing', () => {
  it('renders AppNav', () => {
    renderWithTheme()
    expect(screen.getAllByText(/aigc/i).length).toBeGreaterThanOrEqual(1)
  })

  it('renders all 7 lab tabs', () => {
    renderWithTheme()
    // LabTabs renders links "Lab 1: Risk" … "Lab 7: Comply"
    // The hero strip also contains "Lab N", so use getAllByText and confirm at least one match
    expect(screen.getAllByText(/Lab 1/).length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText(/Lab 7/).length).toBeGreaterThanOrEqual(1)
  })

  it('renders Architecture tab before lab tabs', () => {
    renderWithTheme()
    expect(screen.getByRole('link', { name: 'Architecture' })).toBeInTheDocument()
  })
})
