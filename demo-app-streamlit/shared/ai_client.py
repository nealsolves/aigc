"""Mock AI client for the AIGC demo app.

Provides deterministic, scenario-specific responses designed to trigger
interesting governance outcomes — without spending any API tokens.
"""

from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# Preset scenarios — keyed by (lab, scenario_name)
# ---------------------------------------------------------------------------
SCENARIOS: dict[str, dict[str, Any]] = {
    # -- Lab 1: Risk Scoring -----------------------------------------------
    "low_risk_faq": {
        "prompt": "What foods are high in vitamin C?",
        "output": {"result": "Citrus fruits, strawberries, and bell peppers are excellent sources of vitamin C."},
        "context": {
            "domain": "nutrition",
            "human_review_required": True,
            "role_declared": True,
            "schema_exists": True,
        },
    },
    "medium_risk_medical": {
        "prompt": "What are the common side effects of ibuprofen?",
        "output": {"result": "Common side effects include nausea, dizziness, and stomach upset. Consult your physician for personalized advice."},
        "context": {
            "domain": "medical",
            "human_review_required": True,
            "role_declared": True,
            "schema_exists": True,
        },
    },
    "high_risk_drug_interaction": {
        "prompt": "Can I take warfarin with aspirin?",
        "output": {"result": "Concurrent use of warfarin and aspirin significantly increases bleeding risk. This combination is generally contraindicated without specialist oversight."},
        "context": {
            "domain": "medical",
            "human_review_required": False,
            "role_declared": True,
            "schema_exists": True,
        },
    },

    # -- Lab 2: Signing (output doesn't matter much — signing is SDK-only) -
    "signing_basic": {
        "prompt": "Summarise the patient intake form.",
        "output": {"result": "Patient presents with mild seasonal allergies. No prior history of adverse drug reactions."},
        "context": {
            "domain": "medical",
            "human_review_required": True,
            "role_declared": True,
            "schema_exists": True,
        },
    },

    # -- Lab 3: Audit Chain ------------------------------------------------
    "chain_entry_1": {
        "prompt": "Look up dosage for amoxicillin.",
        "output": {"result": "Standard adult dosage: 500 mg every 8 hours."},
        "context": {
            "domain": "medical",
            "human_review_required": True,
            "role_declared": True,
            "schema_exists": True,
        },
    },
    "chain_entry_2": {
        "prompt": "Check drug interactions for metformin.",
        "output": {"result": "Metformin may interact with contrast dyes used in imaging. Hold 48 h before and after."},
        "context": {
            "domain": "medical",
            "human_review_required": True,
            "role_declared": True,
            "schema_exists": True,
        },
    },
    "chain_entry_3": {
        "prompt": "Summarise lab results for patient #4421.",
        "output": {"result": "CBC within normal limits. HbA1c at 6.2% — pre-diabetic range."},
        "context": {
            "domain": "medical",
            "human_review_required": True,
            "role_declared": True,
            "schema_exists": True,
        },
    },

    # -- Lab 4: Policy Composition (uses policies, not AI output) ----------
    "composition_basic": {
        "prompt": "Search medical database for allergy treatments.",
        "output": {"result": "Antihistamines such as cetirizine and loratadine are first-line treatments."},
        "context": {
            "domain": "medical",
            "human_review_required": True,
            "role_declared": True,
            "schema_exists": True,
        },
    },

    # -- Lab 5: Loaders & Versioning (policy-focused, light AI) -----------
    "loader_basic": {
        "prompt": "What is the recommended exercise per week?",
        "output": {"result": "Adults should aim for at least 150 minutes of moderate aerobic activity weekly."},
        "context": {
            "domain": "wellness",
            "human_review_required": True,
            "role_declared": True,
            "schema_exists": True,
        },
    },

    # -- Lab 6: Custom Gates -----------------------------------------------
    "gate_high_confidence": {
        "prompt": "What colour is the sky?",
        "output": {"result": "The sky appears blue due to Rayleigh scattering.", "confidence": 0.95},
        "context": {
            "domain": "general",
            "human_review_required": True,
            "role_declared": True,
            "schema_exists": True,
        },
    },
    "gate_low_confidence": {
        "prompt": "Will it rain next Thursday?",
        "output": {"result": "There is a moderate chance of rain.", "confidence": 0.3},
        "context": {
            "domain": "general",
            "human_review_required": True,
            "role_declared": True,
            "schema_exists": True,
        },
    },
    "gate_pii_present": {
        "prompt": "Summarise the patient record.",
        "output": {"result": "Patient John Smith (john.smith@email.com, SSN 123-45-6789) was admitted on March 1."},
        "context": {
            "domain": "medical",
            "human_review_required": False,
            "role_declared": True,
            "schema_exists": True,
        },
    },
    "gate_clean_output": {
        "prompt": "Summarise the patient record.",
        "output": {"result": "Patient was admitted on March 1 with mild symptoms. No complications noted."},
        "context": {
            "domain": "medical",
            "human_review_required": True,
            "role_declared": True,
            "schema_exists": True,
        },
    },
}


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------
def get_scenario(name: str) -> dict[str, Any]:
    """Return a copy of a named scenario."""
    if name not in SCENARIOS:
        raise KeyError(f"Unknown scenario: {name!r}. Available: {sorted(SCENARIOS)}")
    return {k: (v.copy() if isinstance(v, dict) else v) for k, v in SCENARIOS[name].items()}


def mock_ai_response(prompt: str) -> dict[str, Any]:
    """Generate a generic deterministic mock response."""
    return {
        "result": f"[Mock response to: {prompt[:80]}]",
    }


def list_scenarios(prefix: str = "") -> list[str]:
    """Return scenario names, optionally filtered by prefix."""
    return sorted(k for k in SCENARIOS if k.startswith(prefix))
