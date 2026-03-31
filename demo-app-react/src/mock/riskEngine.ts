export interface RiskFactor {
  name: string
  weight: number
  triggered: boolean
  contribution?: number
}

export type RiskMode = 'strict' | 'risk_scored' | 'warn_only'

export interface RiskResult {
  score: number
  threshold: number
  mode: RiskMode
  factors: RiskFactor[]
  breached: boolean
  enforcement: 'PASS' | 'FAIL' | 'WARN'
}

export function calculateRiskScore(factors: RiskFactor[]): number {
  return factors.reduce((sum, f) => sum + (f.triggered ? f.weight : 0), 0)
}

export function evaluateRisk(
  factors: RiskFactor[],
  threshold: number,
  mode: RiskMode,
): RiskResult {
  const score = calculateRiskScore(factors)
  const breached = score > threshold
  const withContributions = factors.map(f => ({
    ...f,
    contribution: f.triggered ? f.weight : 0,
  }))
  let enforcement: 'PASS' | 'FAIL' | 'WARN'
  if (!breached) {
    enforcement = 'PASS'
  } else if (mode === 'strict') {
    enforcement = 'FAIL'
  } else if (mode === 'warn_only') {
    enforcement = 'WARN'
  } else {
    enforcement = 'PASS' // risk_scored: recorded but not blocked
  }
  return { score, threshold, mode, factors: withContributions, breached, enforcement }
}

export function resultMessage(result: RiskResult): string {
  const score = result.score.toFixed(2)
  const threshold = result.threshold.toFixed(2)

  if (!result.breached) {
    return `risk score ${score} within threshold`
  }
  if (result.mode === 'strict') {
    return `risk score ${score} exceeds threshold ${threshold} in strict mode`
  }
  if (result.mode === 'warn_only') {
    return `risk score ${score} exceeds threshold ${threshold} (warn_only mode — logged, not blocked)`
  }
  // risk_scored
  return `risk score ${score} exceeds threshold ${threshold} (non-blocking in risk_scored mode — recorded in audit artifact)`
}

// Pre-built factor sets matching Python source (demo-app-streamlit/labs/lab1_risk_scoring.py)
export const MEDICAL_FACTORS: Record<string, RiskFactor[]> = {
  low_risk: [
    { name: 'no_output_schema', weight: 0.15, triggered: false },
    { name: 'broad_roles',      weight: 0.15, triggered: false },
    { name: 'missing_guards',   weight: 0.20, triggered: false },
    { name: 'external_model',   weight: 0.30, triggered: false },
    { name: 'no_preconditions', weight: 0.20, triggered: false },
  ],
  medium_risk: [
    { name: 'no_output_schema', weight: 0.15, triggered: false },
    { name: 'broad_roles',      weight: 0.15, triggered: true  },
    { name: 'missing_guards',   weight: 0.20, triggered: true  },
    { name: 'external_model',   weight: 0.30, triggered: true  },
    { name: 'no_preconditions', weight: 0.20, triggered: false },
  ],
  high_risk: [
    { name: 'no_output_schema', weight: 0.15, triggered: true },
    { name: 'broad_roles',      weight: 0.15, triggered: true },
    { name: 'missing_guards',   weight: 0.20, triggered: true },
    { name: 'external_model',   weight: 0.30, triggered: true },
    { name: 'no_preconditions', weight: 0.20, triggered: true },
  ],
}
