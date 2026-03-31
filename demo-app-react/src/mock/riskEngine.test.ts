import { calculateRiskScore, resultMessage, MEDICAL_FACTORS, type RiskFactor, type RiskResult } from './riskEngine'

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

function makeResult(overrides: Partial<RiskResult>): RiskResult {
  return {
    score: 0.5,
    threshold: 0.7,
    mode: 'strict',
    factors: [],
    breached: false,
    enforcement: 'PASS',
    ...overrides,
  }
}

describe('resultMessage', () => {
  it('not breached — any mode — returns within threshold message', () => {
    const msg = resultMessage(makeResult({ score: 0.5, breached: false, mode: 'strict' }))
    expect(msg).toContain('within threshold')
  })

  it('strict + breached → mentions strict mode', () => {
    const msg = resultMessage(makeResult({ score: 1.0, threshold: 0.7, breached: true, mode: 'strict' }))
    expect(msg).toContain('strict mode')
    expect(msg).toContain('1.00')
  })

  it('risk_scored + breached → mentions non-blocking', () => {
    const msg = resultMessage(makeResult({ score: 1.0, threshold: 0.7, breached: true, mode: 'risk_scored' }))
    expect(msg).toContain('non-blocking')
    expect(msg).toContain('risk_scored')
  })

  it('warn_only + breached → mentions warn_only mode', () => {
    const msg = resultMessage(makeResult({ score: 1.0, threshold: 0.7, breached: true, mode: 'warn_only' }))
    expect(msg).toContain('warn_only mode')
  })
})
