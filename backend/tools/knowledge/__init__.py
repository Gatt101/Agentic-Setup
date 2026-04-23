from tools.knowledge.anatomy import get_anatomical_reference
from tools.knowledge.condition_lookup import lookup_orthopedic_condition
from tools.knowledge.fracture_classifier import classify_fracture_type
from tools.knowledge.ortho_knowledge import get_orthopedic_knowledge
from tools.knowledge.treatment import get_treatment_recommendations
from tools.knowledge.rehabilitation import get_rehabilitation_plan
from tools.knowledge.patient_education import get_patient_education
from tools.knowledge.appointment import get_appointment_schedule

KNOWLEDGE_TOOLS = [
    lookup_orthopedic_condition,
    get_treatment_recommendations,
    get_anatomical_reference,
    classify_fracture_type,
    get_orthopedic_knowledge,
    get_rehabilitation_plan,
    get_patient_education,
    get_appointment_schedule,
]

__all__ = ["KNOWLEDGE_TOOLS"]
