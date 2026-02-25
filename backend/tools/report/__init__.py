from tools.report.clinician_pdf import generate_clinician_pdf
from tools.report.clinician_simple_pdf import generate_clinician_simple_pdf
from tools.report.patient_pdf import generate_patient_pdf
from tools.report.retrieve_report import retrieve_report
from tools.report.save_report import save_report_to_storage

REPORT_TOOLS = [
    generate_patient_pdf,           # for patients — simplified
    generate_clinician_simple_pdf,  # for doctors — quick summary
    generate_clinician_pdf,         # for doctors — full clinical depth
    save_report_to_storage,
    retrieve_report,
]

__all__ = ["REPORT_TOOLS"]
