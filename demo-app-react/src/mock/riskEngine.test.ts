import { calculateRiskScore, MEDICAL_FACTORS, type RiskFactor } from './riskEngine'

describe('calculateRiskScore', () => {
  it('returns 0 when no factors trigger', () => {
    const factors: RiskFactor[] = [
      { name: 'no_output_schema', weight: 0.15, triggered: false },
      { name: 'broad_roles',      weight: 0.15, triggered: false },
    ]
    expect(calculateRiskScore(factors)).toBe(0)
  })

  it('sums weights of triggered factors', () => {
    const factors: RiskFactor[] = [
      { name: 'no_output_schema', weight: 0.15, triggered: true },
      { name: 'broad_roles',      weight: 0.15, triggered: true },
      { name: 'missing_guards',   weight: 0.20, triggered: false },
    ]
    expect(calculateRiskScore(factors)).toBeCloseTo(0.30)
  })

  it('low_risk scenario scores 0', () => {
    const factors = MEDICAL_FACTORS.low_risk
    expect(calculateRiskScore(factors)).toBe(0)
  })

  it('medium_risk scenario scores ~0.65', () => {
    const factors = MEDICAL_FACTORS.medium_risk
    expect(calculateRiskScore(factors)).toBeCloseTo(0.65)
  })

  it('high_risk scenario scores 1.0', () => {
    const factors = MEDICAL_FACTORS.high_risk
    expect(calculateRiskScore(factors)).toBeCloseTo(1.0)
  })
})
