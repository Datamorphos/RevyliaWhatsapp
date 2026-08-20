import re


CRITICAL_RISK_TERMS = (
    "me cuesta respirar",
    "dificultad para respirar",
    "no puedo respirar",
    "sangrado abundante",
    "reacción alérgica",
    "reaccion alergica",
    "anafilaxia",
    "desmayo",
    "inconsciente",
)

DIAGNOSIS_CLAIM_PATTERNS = [
    r"\b(?:tienes|presentas|padeces)\s+(?:una\s+)?(caries|infección|infeccion|pulpitis|gingivitis)\b",
    r"\b(?:es|parece)\s+(?:una\s+)?(caries|infección|infeccion|pulpitis|gingivitis)\b",
    r"\btu diagnóstico es\b",
    r"\btu diagnostico es\b",
]


def detect_critical_risk(user_text: str) -> bool:
    text = user_text.lower()
    return any(term in text for term in CRITICAL_RISK_TERMS)


def apply_clinical_claim_guard(response: str) -> tuple[str, bool]:
    text = str(response or "")
    if any(re.search(pattern, text.lower()) for pattern in DIAGNOSIS_CLAIM_PATTERNS):
        return (
            "No puedo determinar un diagnóstico por este medio. "
            "Lo adecuado es una valoración con un profesional de la clínica. "
            "Si presentas dificultad para respirar, sangrado abundante o una reacción "
            "alérgica, busca atención de urgencias inmediatamente.",
            True,
        )
    return text, False
