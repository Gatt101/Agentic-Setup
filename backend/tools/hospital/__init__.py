from tools.hospital.details import get_hospital_details
from tools.hospital.emergency import get_emergency_contacts
from tools.hospital.finder import find_nearby_hospitals

HOSPITAL_TOOLS = [
    find_nearby_hospitals,
    get_hospital_details,
    get_emergency_contacts,
]

__all__ = ["HOSPITAL_TOOLS"]
