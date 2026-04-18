from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable

from tools.clinical.diagnosis import generate_diagnosis_impl
from tools.clinical.history import get_patient_history_impl
from tools.clinical.multi_study import analyze_multiple_studies_impl
from tools.clinical.symptoms import analyze_patient_symptoms_impl
from tools.clinical.triage import assess_triage_impl
from tools.ct.appendicular_segmentation import ct_analyze_appendicular_impl
from tools.ct.bone_segmentation import ct_analyze_full_body_impl
from tools.ct.spine_segmentation import ct_analyze_spine_impl
from tools.hospital.details import get_hospital_details_impl
from tools.hospital.emergency import get_emergency_contacts_impl
from tools.hospital.finder import find_nearby_hospitals_impl
from tools.knowledge.anatomy import get_anatomical_reference_impl
from tools.knowledge.condition_lookup import lookup_orthopedic_condition_impl
from tools.knowledge.fracture_classifier import classify_fracture_type_impl
from tools.knowledge.ortho_knowledge import get_orthopedic_knowledge_impl
from tools.knowledge.treatment import get_treatment_recommendations_impl
from tools.modality.detect_modality import detect_imaging_modality_impl
from tools.modality.dicom_parser import extract_mid_slice_impl, parse_dicom_impl
from tools.mri.knee_segmentation import mri_analyze_knee_impl
from tools.mri.spine_segmentation import mri_analyze_spine_impl
from tools.report.clinician_pdf import generate_clinician_pdf_impl
from tools.report.patient_pdf import generate_patient_pdf_impl
from tools.report.retrieve_report import retrieve_report_impl
from tools.report.save_report import save_report_to_storage_impl
from tools.vision.annotator import annotate_xray_image_impl
from tools.vision.body_part_detector import detect_body_part_impl
from tools.vision.hand_detector import detect_hand_fracture_impl
from tools.vision.leg_detector import detect_leg_fracture_impl
from tools.vision.uploader import upload_image_to_storage_impl


ToolHandler = Callable[..., Awaitable[dict]]


@dataclass(frozen=True)
class MCPToolRegistration:
    name: str
    handler: ToolHandler
    description: str


MCP_TOOL_REGISTRY: list[MCPToolRegistration] = [
    MCPToolRegistration("modality_detect_imaging_modality", detect_imaging_modality_impl, "Detect imaging modality."),
    MCPToolRegistration("modality_parse_dicom", parse_dicom_impl, "Parse DICOM metadata."),
    MCPToolRegistration("modality_extract_mid_slice", extract_mid_slice_impl, "Extract middle slice preview from a volume."),
    MCPToolRegistration("vision_detect_body_part", detect_body_part_impl, "Detect body part from X-ray."),
    MCPToolRegistration("vision_detect_hand_fracture", detect_hand_fracture_impl, "Detect hand fractures."),
    MCPToolRegistration("vision_detect_leg_fracture", detect_leg_fracture_impl, "Detect leg fractures."),
    MCPToolRegistration("vision_annotate_xray_image", annotate_xray_image_impl, "Annotate X-ray with detections."),
    MCPToolRegistration("vision_upload_image_to_storage", upload_image_to_storage_impl, "Store source image."),
    MCPToolRegistration("ct_analyze_full_body", ct_analyze_full_body_impl, "Segment CT bones using TotalSegmentator."),
    MCPToolRegistration("ct_analyze_spine", ct_analyze_spine_impl, "Segment spine CT using VerSe or TotalSegmentator."),
    MCPToolRegistration("ct_analyze_appendicular", ct_analyze_appendicular_impl, "Segment appendicular CT structures."),
    MCPToolRegistration("mri_analyze_knee", mri_analyze_knee_impl, "Segment knee MRI structures."),
    MCPToolRegistration("mri_analyze_spine", mri_analyze_spine_impl, "Segment spine MRI vertebrae."),
    MCPToolRegistration("clinical_generate_diagnosis", generate_diagnosis_impl, "Generate diagnosis summary."),
    MCPToolRegistration("clinical_assess_triage", assess_triage_impl, "Assess triage level."),
    MCPToolRegistration(
        "clinical_analyze_patient_symptoms",
        analyze_patient_symptoms_impl,
        "Analyze patient symptoms.",
    ),
    MCPToolRegistration(
        "clinical_analyze_multiple_studies",
        analyze_multiple_studies_impl,
        "Analyze multi-study trends.",
    ),
    MCPToolRegistration("clinical_get_patient_history", get_patient_history_impl, "Fetch patient history."),
    MCPToolRegistration(
        "knowledge_lookup_orthopedic_condition",
        lookup_orthopedic_condition_impl,
        "Look up orthopedic condition.",
    ),
    MCPToolRegistration(
        "knowledge_get_treatment_recommendations",
        get_treatment_recommendations_impl,
        "Get treatment recommendations.",
    ),
    MCPToolRegistration("knowledge_get_anatomical_reference", get_anatomical_reference_impl, "Get anatomy notes."),
    MCPToolRegistration(
        "knowledge_classify_fracture_type",
        classify_fracture_type_impl,
        "Classify fracture type.",
    ),
    MCPToolRegistration(
        "knowledge_get_orthopedic_knowledge",
        get_orthopedic_knowledge_impl,
        "Answer orthopedic knowledge query.",
    ),
    MCPToolRegistration("report_generate_patient_pdf", generate_patient_pdf_impl, "Generate patient PDF report."),
    MCPToolRegistration(
        "report_generate_clinician_pdf",
        generate_clinician_pdf_impl,
        "Generate clinician PDF report.",
    ),
    MCPToolRegistration("report_save_report_to_storage", save_report_to_storage_impl, "Save report record."),
    MCPToolRegistration("report_retrieve_report", retrieve_report_impl, "Retrieve report by id."),
    MCPToolRegistration("hospital_find_nearby_hospitals", find_nearby_hospitals_impl, "Find nearby hospitals."),
    MCPToolRegistration("hospital_get_hospital_details", get_hospital_details_impl, "Get hospital details."),
    MCPToolRegistration("hospital_get_emergency_contacts", get_emergency_contacts_impl, "Get emergency numbers."),
]


__all__ = ["MCPToolRegistration", "MCP_TOOL_REGISTRY"]
