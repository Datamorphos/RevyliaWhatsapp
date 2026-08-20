from src.agents.safety import apply_clinical_claim_guard, detect_critical_risk


def test_detect_critical_risk():
    assert detect_critical_risk("Tengo dificultad para respirar")
    assert not detect_critical_risk("Quiero una limpieza")


def test_diagnosis_guard():
    response, blocked = apply_clinical_claim_guard("Parece una infección")
    assert blocked
    assert "No puedo determinar un diagnóstico" in response
