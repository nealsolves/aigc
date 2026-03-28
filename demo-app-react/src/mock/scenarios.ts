// Ported from demo-app-streamlit/shared/ai_client.py

export interface Scenario {
  prompt: string
  output: { result: string; confidence?: number }
  context: {
    domain: string
    human_review_required: boolean
    role_declared: boolean
    schema_exists: boolean
  }
}

export const SCENARIOS: Record<string, Scenario> = {
  low_risk_faq: {
    prompt: 'What foods are high in vitamin C?',
    output: { result: 'Citrus fruits, strawberries, and bell peppers are excellent sources of vitamin C.' },
    context: { domain: 'nutrition', human_review_required: true, role_declared: true, schema_exists: true },
  },
  medium_risk_medical: {
    prompt: 'What are the common side effects of ibuprofen?',
    output: { result: 'Common side effects include nausea, dizziness, and stomach upset. Consult your physician for personalized advice.' },
    context: { domain: 'medical', human_review_required: true, role_declared: true, schema_exists: true },
  },
  high_risk_drug_interaction: {
    prompt: 'Can I take warfarin with aspirin?',
    output: { result: 'Concurrent use of warfarin and aspirin significantly increases bleeding risk. This combination is generally contraindicated without specialist oversight.' },
    context: { domain: 'medical', human_review_required: false, role_declared: true, schema_exists: true },
  },
  signing_basic: {
    prompt: 'Summarise the patient intake form.',
    output: { result: 'Patient presents with mild seasonal allergies. No prior history of adverse drug reactions.' },
    context: { domain: 'medical', human_review_required: true, role_declared: true, schema_exists: true },
  },
  chain_entry_1: {
    prompt: 'Look up dosage for amoxicillin.',
    output: { result: 'Standard adult dosage: 500 mg every 8 hours.' },
    context: { domain: 'medical', human_review_required: true, role_declared: true, schema_exists: true },
  },
  chain_entry_2: {
    prompt: 'Check drug interactions for metformin.',
    output: { result: 'Metformin may interact with contrast dyes used in imaging. Hold 48 h before and after.' },
    context: { domain: 'medical', human_review_required: true, role_declared: true, schema_exists: true },
  },
  chain_entry_3: {
    prompt: 'Summarise lab results for patient #4421.',
    output: { result: 'CBC within normal limits. HbA1c at 6.2% — pre-diabetic range.' },
    context: { domain: 'medical', human_review_required: true, role_declared: true, schema_exists: true },
  },
  gate_high_confidence: {
    prompt: 'What colour is the sky?',
    output: { result: 'The sky appears blue due to Rayleigh scattering.', confidence: 0.95 },
    context: { domain: 'general', human_review_required: true, role_declared: true, schema_exists: true },
  },
  gate_low_confidence: {
    prompt: 'Will it rain next Thursday?',
    output: { result: 'There is a moderate chance of rain.', confidence: 0.3 },
    context: { domain: 'general', human_review_required: true, role_declared: true, schema_exists: true },
  },
  gate_pii_present: {
    prompt: 'Summarise the patient record.',
    output: { result: 'Patient John Smith (john.smith@email.com, SSN 123-45-6789) was admitted on March 1.' },
    context: { domain: 'medical', human_review_required: false, role_declared: true, schema_exists: true },
  },
  gate_clean_output: {
    prompt: 'Summarise the patient record.',
    output: { result: 'Patient was admitted on March 1 with mild symptoms. No complications noted.' },
    context: { domain: 'medical', human_review_required: true, role_declared: true, schema_exists: true },
  },
}

export function getScenario(name: string): Scenario {
  const s = SCENARIOS[name]
  if (!s) throw new Error(`Unknown scenario: ${name}. Available: ${Object.keys(SCENARIOS).join(', ')}`)
  return { ...s, context: { ...s.context }, output: { ...s.output } }
}
