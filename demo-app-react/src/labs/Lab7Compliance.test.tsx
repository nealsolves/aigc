import { useEffect } from 'react'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import Lab7Compliance from '@/labs/Lab7Compliance'
import { AigcProvider, useAigc } from '@/context/AigcContext'
import type { Artifact } from '@/types/artifact'

const API_SHAPED_ARTIFACT: Artifact = {
  enforcement_result: 'PASS',
  model_provider: 'mock',
  model_identifier: 'mock-model',
  role: 'doctor',
  policy_file: 'medical_ai.yaml',
  timestamp: 1775323506, // epoch seconds
  checksum: 'abcdef1234567890',
  metadata: {
    risk_scoring: {
      score: 0.42,
      threshold: 0.7,
      mode: 'strict',
    },
  },
}

function SeedAudit({ artifact }: { artifact: Artifact }) {
  const { addAudit } = useAigc()
  useEffect(() => {
    addAudit(artifact)
    // Seed once; this helper is only for test setup.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
  return null
}

const FAIL_ARTIFACT_WITH_RISK: Artifact = {
  enforcement_result: 'FAIL',
  model_provider: 'mock',
  model_identifier: 'mock-model',
  role: 'nurse',
  policy_file: 'high_risk.yaml',
  timestamp: 1775323600,
  checksum: 'deadbeef01234567',
  metadata: {
    // Mirrors the new enforcement.py FAIL path: fail_metadata["risk_scoring"] = exc.details
    risk_scoring: { score: 0.91, threshold: 0.7, mode: 'strict' },
    gates_evaluated: ['pre_authorization'],
  },
}

describe('Lab7Compliance', () => {
  it('renders session audit records when artifact timestamp is numeric epoch', () => {
    render(
      <AigcProvider>
        <SeedAudit artifact={API_SHAPED_ARTIFACT} />
        <Lab7Compliance />
      </AigcProvider>,
    )

    expect(screen.queryByText('Load Sample Data')).not.toBeInTheDocument()
    expect(screen.getByText('medical_ai.yaml')).toBeInTheDocument()
    expect(screen.getByText('abcdef')).toBeInTheDocument()
  })

  it('renders FAIL artifact with risk_scoring metadata without crashing', () => {
    // Covers the enforcement.py FAIL path where fail_metadata["risk_scoring"] = exc.details
    render(
      <AigcProvider>
        <SeedAudit artifact={FAIL_ARTIFACT_WITH_RISK} />
        <Lab7Compliance />
      </AigcProvider>,
    )

    expect(screen.queryByText('Load Sample Data')).not.toBeInTheDocument()
    expect(screen.getByText('high_risk.yaml')).toBeInTheDocument()
    // risk score 0.91 → normalizeRiskScore → toFixed(2) → '0.91'
    // appears in both AVG RISK metric card and table row
    expect(screen.getAllByText('0.91').length).toBeGreaterThanOrEqual(1)
  })

  it('shows the guide-aligned compliance controls for filtering and export', async () => {
    const user = userEvent.setup()

    render(
      <AigcProvider>
        <SeedAudit artifact={API_SHAPED_ARTIFACT} />
        <SeedAudit artifact={FAIL_ARTIFACT_WITH_RISK} />
        <Lab7Compliance />
      </AigcProvider>,
    )

    expect(screen.getByRole('button', { name: 'ALL' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'PASS' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'FAIL' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /json/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /csv/i })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'FAIL' }))
    const table = screen.getByRole('table')
    expect(within(table).getByText('high_risk.yaml')).toBeInTheDocument()
    expect(within(table).queryByText('medical_ai.yaml')).not.toBeInTheDocument()
  })
})
