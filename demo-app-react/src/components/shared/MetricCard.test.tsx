import { render, screen } from '@testing-library/react'
import MetricCard from './MetricCard'

describe('MetricCard', () => {
  it('renders value and label', () => {
    render(<MetricCard value="0.82" label="RISK SCORE" color="#78a9ff" />)
    expect(screen.getByText('0.82')).toBeInTheDocument()
    expect(screen.getByText('RISK SCORE')).toBeInTheDocument()
  })
})
