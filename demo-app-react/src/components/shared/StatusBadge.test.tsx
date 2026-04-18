import { render, screen } from '@testing-library/react'
import StatusBadge from './StatusBadge'

describe('StatusBadge', () => {
  it('renders "Pass" (mixed-case) not "PASS"', () => {
    render(<StatusBadge status="PASS" />)
    expect(screen.getByText(/Pass/)).toBeInTheDocument()
    expect(screen.queryByText('PASS')).not.toBeInTheDocument()
  })

  it('renders "Fail" (mixed-case) not "FAIL"', () => {
    render(<StatusBadge status="FAIL" />)
    expect(screen.getByText(/Fail/)).toBeInTheDocument()
    expect(screen.queryByText('FAIL')).not.toBeInTheDocument()
  })

  it('renders "Warn" (mixed-case) not "WARN"', () => {
    render(<StatusBadge status="WARN" />)
    expect(screen.getByText(/Warn/)).toBeInTheDocument()
    expect(screen.queryByText('WARN')).not.toBeInTheDocument()
  })

  it('renders workflow COMPLETED as "Completed"', () => {
    render(<StatusBadge status="COMPLETED" />)
    expect(screen.getByText(/Completed/)).toBeInTheDocument()
    expect(screen.queryByText('COMPLETED')).not.toBeInTheDocument()
  })

  it('renders workflow FAILED as "Failed"', () => {
    render(<StatusBadge status="FAILED" />)
    expect(screen.getByText(/Failed/)).toBeInTheDocument()
    expect(screen.queryByText('FAILED')).not.toBeInTheDocument()
  })
})
