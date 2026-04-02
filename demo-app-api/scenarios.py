SCENARIOS: dict[str, dict] = {
    "low_risk_faq": {
        "prompt": "What foods are high in vitamin C?",
        "output": {
            "result": (
                "Citrus fruits, strawberries, and bell peppers are excellent sources of vitamin C."
            ),
        },
        "context": {
            "domain": "nutrition",
            "human_review_required": True,
            "role_declared": True,
            "schema_exists": True,
        },
        "policy": "medical_ai_low_risk.yaml",
        "model_provider": "internal",
        "model_id": "internal-med-v1",
        "role": "doctor",
    },
    "medium_risk_medical": {
        "prompt": "What are the common side effects of ibuprofen?",
        "output": {
            "result": (
                "Common side effects include nausea, dizziness, and stomach upset."
                " Consult your physician."
            ),
        },
        "context": {
            "domain": "medical",
            "human_review_required": True,
            "role_declared": True,
            "schema_exists": True,
        },
        "policy": "medical_ai.yaml",
        "model_provider": "mock",
        "model_id": "mock-model",
        "role": "doctor",
    },
    "high_risk_drug_interaction": {
        "prompt": "Can I take warfarin with aspirin?",
        "output": {
            "result": (
                "Concurrent use significantly increases bleeding risk."
                " Contraindicated without oversight."
            ),
        },
        "context": {
            "domain": "medical",
            "human_review_required": False,
            "role_declared": True,
            "schema_exists": True,
        },
        "policy": "medical_ai_high_risk.yaml",
        "model_provider": "mock",
        "model_id": "mock-model",
        "role": "doctor",
    },
    "signing_basic": {
        "prompt": "Summarise the patient intake form.",
        "output": {
            "result": (
                "Patient presents with mild seasonal allergies."
                " No prior history of adverse drug reactions."
            ),
        },
        "context": {
            "domain": "medical",
            "human_review_required": True,
            "role_declared": True,
            "schema_exists": True,
        },
        "policy": "medical_ai.yaml",
        "model_provider": "mock",
        "model_id": "mock-model",
        "role": "doctor",
    },
    "chain_entry_1": {
        "prompt": "Look up dosage for amoxicillin.",
        "output": {
            "result": "Standard adult dosage: 500 mg every 8 hours.",
        },
        "context": {
            "domain": "medical",
            "human_review_required": True,
            "role_declared": True,
            "schema_exists": True,
        },
        "policy": "medical_ai.yaml",
        "model_provider": "mock",
        "model_id": "mock-model",
        "role": "doctor",
    },
    "chain_entry_2": {
        "prompt": "Check drug interactions for metformin.",
        "output": {
            "result": (
                "Metformin may interact with contrast dyes. Hold 48 h before and after imaging."
            ),
        },
        "context": {
            "domain": "medical",
            "human_review_required": True,
            "role_declared": True,
            "schema_exists": True,
        },
        "policy": "medical_ai.yaml",
        "model_provider": "mock",
        "model_id": "mock-model",
        "role": "doctor",
    },
    "chain_entry_3": {
        "prompt": "Summarise lab results for patient #4421.",
        "output": {
            "result": "CBC within normal limits. HbA1c at 6.2% — pre-diabetic range.",
        },
        "context": {
            "domain": "medical",
            "human_review_required": True,
            "role_declared": True,
            "schema_exists": True,
        },
        "policy": "medical_ai.yaml",
        "model_provider": "mock",
        "model_id": "mock-model",
        "role": "doctor",
    },
    "gate_high_confidence": {
        "prompt": "What colour is the sky?",
        "output": {
            "result": "The sky appears blue due to Rayleigh scattering.",
            "confidence": 0.95,
        },
        "context": {
            "domain": "general",
            "human_review_required": True,
            "role_declared": True,
            "schema_exists": True,
        },
        "policy": "medical_ai.yaml",
        "model_provider": "mock",
        "model_id": "mock-model",
        "role": "doctor",
    },
    "gate_low_confidence": {
        "prompt": "Will it rain next Thursday?",
        "output": {
            "result": "There is a moderate chance of rain.",
            "confidence": 0.3,
        },
        "context": {
            "domain": "general",
            "human_review_required": True,
            "role_declared": True,
            "schema_exists": True,
        },
        "policy": "medical_ai.yaml",
        "model_provider": "mock",
        "model_id": "mock-model",
        "role": "doctor",
    },
    "gate_pii_present": {
        "prompt": "Summarise the patient record.",
        "output": {
            "result": (
                "Patient John Smith (john.smith@email.com, SSN 123-45-6789)"
                " was admitted on March 1."
            ),
        },
        "context": {
            "domain": "medical",
            "human_review_required": False,
            "role_declared": True,
            "schema_exists": True,
        },
        "policy": "medical_ai.yaml",
        "model_provider": "mock",
        "model_id": "mock-model",
        "role": "doctor",
    },
    "gate_clean_output": {
        "prompt": "Summarise the patient record.",
        "output": {
            "result": "Patient was admitted on March 1 with mild symptoms. No complications noted.",
        },
        "context": {
            "domain": "medical",
            "human_review_required": True,
            "role_declared": True,
            "schema_exists": True,
        },
        "policy": "medical_ai.yaml",
        "model_provider": "mock",
        "model_id": "mock-model",
        "role": "doctor",
    },
}
