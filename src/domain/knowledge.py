from typing import Any


CLINIC_KNOWLEDGE: dict[str, Any] = {
    "clinic_name": "Clínica Sonrisas S.A.S.",
    "timezone": "America/Bogota",
    "services": {
        "Valoración general": {
            "price_cop": 80000,
            "duration_minutes": 45,
            "description": "Evaluación inicial y definición del plan de atención.",
        },
        "Limpieza dental": {
            "price_cop": 140000,
            "duration_minutes": 60,
            "description": "Profilaxis y remoción de placa y cálculo según valoración.",
        },
        "Blanqueamiento": {
            "price_cop": 520000,
            "duration_minutes": 90,
            "description": "Tratamiento estético sujeto a valoración previa.",
        },
        "Ortodoncia - valoración": {
            "price_cop": 100000,
            "duration_minutes": 60,
            "description": "Valoración para determinar alternativas de ortodoncia.",
        },
    },
    "business_hours": {
        "monday_friday": "08:00-17:00",
        "saturday": "08:00-12:00",
        "sunday": "closed",
    },
    "rules": [
        "Las citas deben confirmarse con nombre, teléfono, servicio, fecha y hora.",
        "Los precios son informativos y pueden cambiar después de una valoración.",
        "La cancelación o reprogramación debe solicitarse con al menos 4 horas de anticipación.",
        "No se deben emitir diagnósticos clínicos por chat.",
        "Síntomas graves, sangrado abundante, dificultad para respirar o reacciones alérgicas deben escalarse de inmediato.",
        "Solo pueden enviarse campañas a pacientes con consentimiento de comunicaciones.",
    ],
}


def clinic_context_text() -> str:
    services = "\n".join(
        f"- {name}: ${data['price_cop']:,} COP; {data['duration_minutes']} min; {data['description']}"
        for name, data in CLINIC_KNOWLEDGE["services"].items()
    )
    rules = "\n".join(f"- {rule}" for rule in CLINIC_KNOWLEDGE["rules"])
    return (
        f"Clínica: {CLINIC_KNOWLEDGE['clinic_name']}\n"
        f"Horarios: {CLINIC_KNOWLEDGE['business_hours']}\n"
        f"Servicios:\n{services}\n"
        f"Reglas:\n{rules}"
    )
