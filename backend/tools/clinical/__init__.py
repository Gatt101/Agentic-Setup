from tools.clinical.diagnosis import generate_diagnosis
from tools.clinical.history import get_patient_history
from tools.clinical.multi_study import analyze_multiple_studies
from tools.clinical.symptoms import analyze_patient_symptoms
from tools.clinical.triage import assess_triage

CLINICAL_TOOLS = [
    generate_diagnosis,
    assess_triage,
    analyze_patient_symptoms,
    analyze_multiple_studies,
    get_patient_history,
]

__all__ = ["CLINICAL_TOOLS"]
