"""Patient-facing simplified PDF report.

Language is plain, non-clinical. Shows: what was found, how urgent, what to do.
"""
from __future__ import annotations

import base64
from datetime import UTC, datetime
from io import BytesIO
from typing import Any
from uuid import uuid4

from langchain_core.tools import tool
from loguru import logger
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from services.storage import storage_service
from tools.report.pdf_engine import (
    BORDER,
    DISCLAIMER_TEXT,
    LIGHT_BLUE,
    TEAL,
    build_branded_header,
    build_styles,
    human_readable_patient_id,
    info_grid,
    pdf_image_from_base64,
    section_heading,
    triage_badge_table,
)
from tools.vision.annotator import annotate_xray_image_impl


# ── Validation ────────────────────────────────────────────────────────────────
class ReportValidationError(ValueError):
    pass


def validate_patient_report_inputs(
    diagnosis: dict,
    triage: dict,
    patient_info: dict,
) -> None:
    missing = []
    if not diagnosis or not diagnosis.get("finding"):
        missing.append("clinical diagnosis (finding)")
    if not triage or not (triage.get("level") or triage.get("triage_level")):
        missing.append("triage assessment (level)")
    if not patient_info or not (patient_info.get("patient_id") or patient_info.get("name")):
        missing.append("patient information (patient_id or name)")
    if missing:
        raise ReportValidationError(
            f"Cannot generate report — missing required data: {', '.join(missing)}. "
            "Please ensure vision analysis and clinical assessment have been completed first."
        )



# ── Builder ───────────────────────────────────────────────────────────────────
def _build_patient_report(
    report_id: str,
    diagnosis: dict[str, Any],
    triage: dict[str, Any],
    patient_info: dict[str, Any],
    recommendations: list[str],
    image_base64: str | None,
    annotated_image_base64: str | None,
) -> bytes:
    styles = build_styles()
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=50, leftMargin=50, topMargin=50, bottomMargin=44)

    raw_pid = str(patient_info.get("patient_id") or patient_info.get("actor_id") or "unknown")
    pt_id = human_readable_patient_id(raw_pid)
    name = str(patient_info.get("name") or "Not provided")
    age = str(patient_info.get("age") or "Not provided")
    gender = str(patient_info.get("gender") or "Not provided")
    doctor = str(patient_info.get("doctor") or "Not provided")
    exam_date = datetime.now(UTC).strftime("%d %b %Y")
    triage_level = str(triage.get("level") or triage.get("triage_level") or "N/A").upper()

    story: list = []
    story += build_branded_header("Patient Summary Report", report_id, styles)

    story += section_heading("Your Information", styles, "1")
    story.append(info_grid([
        ["Patient ID", pt_id, "Exam Date", exam_date],
        ["Name", name, "Age / Gender", f"{age} / {gender}"],
        ["Referring Doctor", doctor, "Body Part", str(patient_info.get("body_part") or "N/A")],
    ]))
    story.append(Spacer(1, 10))

    story += section_heading("What We Found", styles, "2")
    finding = str(diagnosis.get("finding") or diagnosis.get("primary_diagnosis") or "No findings recorded.")
    severity = str(diagnosis.get("severity") or "Not specified")
    story.append(Paragraph(f"<b>Finding:</b> {finding}", styles["Body"]))
    story.append(Paragraph(f"<b>Severity:</b> {severity.capitalize()}", styles["Body"]))
    if diagnosis.get("notes"):
        story.append(Paragraph(f"<b>Notes:</b> {diagnosis['notes']}", styles["Body"]))
    story.append(Spacer(1, 8))

    story += section_heading("Triage Assessment", styles, "3")
    story.append(triage_badge_table(triage_level, styles))
    timeframe = str(triage.get("recommended_timeframe") or "")
    if timeframe:
        story.append(Paragraph(timeframe, styles["Body"]))
    story.append(Spacer(1, 8))

    story += section_heading("Recommended Next Steps", styles, "4")
    for action in (recommendations or ["Please consult your treating physician."]):
        story.append(Paragraph(f"• {action}", styles["Body"]))
    story.append(Spacer(1, 8))

    orig_img = pdf_image_from_base64(image_base64)
    ann_img = pdf_image_from_base64(annotated_image_base64)
    if orig_img or ann_img:
        story += section_heading("Your X-ray Images", styles, "5")
        img_table = Table(
            [["Original X-ray", "Annotated X-ray"],
             [orig_img or Paragraph("Not available", styles["Small"]),
              ann_img or Paragraph("Not available", styles["Small"])]],
            colWidths=[3.1 * inch, 3.1 * inch],
        )
        img_table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 9),
            ("BACKGROUND", (0, 0), (-1, 0), LIGHT_BLUE),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.7, BORDER),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ]))
        story.append(img_table)
        story.append(Spacer(1, 10))

    story += section_heading("Important Notice", styles, "6")
    story.append(Paragraph(DISCLAIMER_TEXT, styles["Disclaimer"]))
    story.append(Spacer(1, 6))
    story.append(HRFlowable(width="100%", thickness=0.5, color=TEAL))
    story.append(Paragraph("OrthoAssist  •  AI Clinical Decision Support  •  Confidential Patient Document", styles["FooterText"]))

    doc.build(story)
    output = buffer.getvalue()
    buffer.close()
    return output



# ── Public impl ───────────────────────────────────────────────────────────────
async def generate_patient_pdf_impl(
    diagnosis: dict,
    triage: dict,
    patient_info: dict,
    recommendations: list[str],
    image_base64: str | None = None,
    detections: list[dict] | None = None,
    annotated_image_base64: str | None = None,
) -> dict:
    """Generate a patient-facing PDF report."""
    patient_info = patient_info or {}
    detections = detections or []

    validate_patient_report_inputs(diagnosis, triage, patient_info)

    if not annotated_image_base64 and image_base64 and detections:
        try:
            annotation = await annotate_xray_image_impl(image_base64=image_base64, detections=detections)
            maybe = annotation.get("annotated_image_base64")
            if isinstance(maybe, str) and maybe:
                annotated_image_base64 = maybe
        except Exception as exc:
            logger.warning("Auto-annotate failed: {}", exc)

    report_id = uuid4().hex
    patient_id = str(patient_info.get("patient_id") or "unknown")

    pdf_bytes = _build_patient_report(
        report_id=report_id, diagnosis=diagnosis, triage=triage,
        patient_info=patient_info, recommendations=recommendations,
        image_base64=image_base64, annotated_image_base64=annotated_image_base64,
    )

    saved = await storage_service.save_bytes(pdf_bytes, f"{report_id}.pdf", subdir="reports")
    pdf_url = saved["public_url"]

    await storage_service.save_report(
        report_data={"diagnosis": diagnosis, "triage": triage, "patient_info": patient_info,
                     "recommendations": recommendations, "detections": detections},
        patient_id=patient_id, report_type="patient_pdf", pdf_url=pdf_url, report_id=report_id,
    )

    return {"pdf_base64": base64.b64encode(pdf_bytes).decode("ascii"), "pdf_url": pdf_url, "report_id": report_id}


@tool("report_generate_patient_pdf")
async def generate_patient_pdf(
    diagnosis: dict,
    triage: dict,
    patient_info: dict,
    recommendations: list[str],
    image_base64: str | None = None,
    detections: list[dict] | None = None,
    annotated_image_base64: str | None = None,
) -> dict:
    """Generate a simplified patient-facing PDF report with findings and next steps."""
    return await generate_patient_pdf_impl(
        diagnosis=diagnosis, triage=triage, patient_info=patient_info,
        recommendations=recommendations, image_base64=image_base64,
        detections=detections, annotated_image_base64=annotated_image_base64,
    )


__all__ = ["generate_patient_pdf", "generate_patient_pdf_impl"]
