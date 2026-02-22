from tools.report.clinician_pdf import generate_clinician_pdf
from tools.report.patient_pdf import generate_patient_pdf
from tools.report.retrieve_report import retrieve_report
from tools.report.save_report import save_report_to_storage

REPORT_TOOLS = [
    generate_patient_pdf,
    generate_clinician_pdf,
    save_report_to_storage,
    retrieve_report,
]

__all__ = ["REPORT_TOOLS"]
