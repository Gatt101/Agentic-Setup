"""Simplified doctor report — same readability as patient report but with clinical fields.

For doctors who want a quick summary without full technical depth.
Sections: Patient & Doctor Info, Findings, Triage, Recommendations, Images, Disclaimer.
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
def validate_simple_doctor_report(diagnosis: dict, triage: dict, metadata: dict) -> None:
    missing = []
    if not diagnosis or not (diagnosis.get("finding") or diagnosis.get("primary_diagnosis")):
        missing.append("clinical diagnosis")
    if not triage or not (triage.get("level") or triage.get("triage_level")):
        missing.append("triage assessment")
    if not metadata or not metadata.get("patient_id"):
        missing.append("patient_id in metadata")
    if missing:
        raise ValueError(
            f"Cannot generate simplified doctor report — missing: {', '.join(missing)}."
        )


# ── Builder ───────────────────────────────────────────────────────────────────
def _build_simple_doctor_report(
    report_id: str,
    diagnosis: dict[str, Any],
    triage: dict[str, Any],
    metadata: dict[str, Any],
    recommendations: list[str],
    image_base64: str | None,
    annotated_image_base64: str | None,
) -> bytes:
    styles = build_styles()
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=50, leftMargin=50, topMargin=50, bottomMargin=44)

    raw_pid = str(metadata.get("patient_id") or "unknown")
    pt_id = human_readable_patient_id(raw_pid)
    doctor_name = str(metadata.get("doctor_name") or metadata.get("actor_name") or "Not provided")
    exam_date = datetime.now(UTC).strftime("%d %b %Y")
    triage_level = str(triage.get("level") or triage.get("triage_level") or "N/A").upper()
    body_part = str(metadata.get("body_part") or "N/A")
    patient_name = str(metadata.get("patient_name") or "Not provided")
    patient_age = str(metadata.get("patient_age") or "N/A")
    patient_gender = str(metadata.get("patient_gender") or "N/A").capitalize()

    story: list = []
    story += build_branded_header("Physician Summary Report", report_id, styles)

    # ── 1. Patient & Physician Info ──────────────────────────────────────────
    story += section_heading("Patient & Physician Information", styles, "1")
    story.append(info_grid([
        ["Patient ID", pt_id, "Patient Name", patient_name],
        ["Age", patient_age, "Gender", patient_gender],
        ["Body Part", body_part, "Exam Date", exam_date],
        ["Study ID", str(metadata.get("study_id") or report_id[:12]), "Report Type", "Physician Summary"],
        ["Reviewing Physician", doctor_name, "", ""],
    ]))
    story.append(Spacer(1, 10))

    # ── 2. Clinical Findings ─────────────────────────────────────────────────
    story += section_heading("Clinical Findings", styles, "2")
    primary = str(diagnosis.get("primary_diagnosis") or diagnosis.get("finding") or "N/A")
    severity = str(diagnosis.get("severity") or "N/A")
    icd = str(diagnosis.get("icd_code") or "N/A")

    story.append(Paragraph(f"<b>Primary Diagnosis:</b> {primary}", styles["Body"]))
    story.append(Paragraph(f"<b>Severity:</b> {severity.capitalize()}", styles["Body"]))
    story.append(Paragraph(f"<b>ICD-10:</b> {icd}", styles["Body"]))
    if diagnosis.get("notes") or diagnosis.get("clinical_notes"):
        story.append(Paragraph(
            f"<b>Notes:</b> {diagnosis.get('notes') or diagnosis.get('clinical_notes')}",
            styles["Body"],
        ))
    story.append(Spacer(1, 8))

    # ── 3. Triage ────────────────────────────────────────────────────────────
    story += section_heading("Triage Assessment", styles, "3")
    story.append(triage_badge_table(triage_level, styles))
    timeframe = str(triage.get("recommended_timeframe") or "")
    urgency_score = triage.get("urgency_score")
    if timeframe:
        story.append(Paragraph(f"<b>Recommended timeframe:</b> {timeframe}", styles["Body"]))
    if urgency_score is not None:
        story.append(Paragraph(f"<b>Urgency score:</b> {float(urgency_score):.3f}", styles["Body"]))
    if triage.get("rationale"):
        story.append(Paragraph(f"<b>Rationale:</b> {triage['rationale']}", styles["Body"]))
    story.append(Spacer(1, 8))

    # ── 4. Recommendations ───────────────────────────────────────────────────
    story += section_heading("Recommended Actions", styles, "4")
    for action in (recommendations or ["Follow clinical protocol appropriate to triage level."]):
        story.append(Paragraph(f"• {action}", styles["Body"]))
    story.append(Spacer(1, 8))

    # ── 5. Imaging Evidence ──────────────────────────────────────────────────
    orig_img = pdf_image_from_base64(image_base64)
    ann_img = pdf_image_from_base64(annotated_image_base64)
    if orig_img or ann_img:
        story += section_heading("Imaging Evidence", styles, "5")
        img_table = Table(
            [["Original X-ray", "AI-Annotated X-ray"],
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

    # ── 6. Disclaimer ────────────────────────────────────────────────────────
    story += section_heading("Legal Disclaimer", styles, "6")
    story.append(Paragraph(DISCLAIMER_TEXT, styles["Disclaimer"]))
    story.append(Spacer(1, 6))
    story.append(HRFlowable(width="100%", thickness=0.5, color=TEAL))
    story.append(Paragraph(
        "OrthoAssist  •  AI Clinical Decision Support  •  CONFIDENTIAL — PHYSICIAN COPY",
        styles["FooterText"],
    ))

    doc.build(story)
    output = buffer.getvalue()
    buffer.close()
    return output


# ── Public impl ───────────────────────────────────────────────────────────────
async def generate_clinician_simple_pdf_impl(
    diagnosis: dict,
    triage: dict,
    metadata: dict,
    recommendations: list[str] | None = None,
    image_base64: str | None = None,
    detections: list[dict] | None = None,
    annotated_image_base64: str | None = None,
) -> dict:
    """Generate a simplified physician summary PDF (no raw detection tables)."""
    metadata = metadata or {}
    detections = detections or []
    recommendations = recommendations or []

    validate_simple_doctor_report(diagnosis, triage, metadata)

    if not annotated_image_base64 and image_base64 and detections:
        try:
            ann = await annotate_xray_image_impl(image_base64=image_base64, detections=detections)
            maybe = ann.get("annotated_image_base64")
            if maybe:
                annotated_image_base64 = maybe
        except Exception as exc:
            logger.warning("Annotate failed in doctor simple PDF: {}", exc)

    report_id = uuid4().hex
    patient_id = str(metadata.get("patient_id") or "unknown")

    pdf_bytes = _build_simple_doctor_report(
        report_id=report_id, diagnosis=diagnosis, triage=triage,
        metadata=metadata, recommendations=recommendations,
        image_base64=image_base64, annotated_image_base64=annotated_image_base64,
    )

    saved = await storage_service.save_bytes(pdf_bytes, f"{report_id}.pdf", subdir="reports")
    pdf_url = saved["public_url"]

    await storage_service.save_report(
        report_data={"diagnosis": diagnosis, "triage": triage, "metadata": metadata,
                     "recommendations": recommendations, "detections": detections},
        patient_id=patient_id, report_type="clinician_simple_pdf", pdf_url=pdf_url, report_id=report_id,
    )

    return {"pdf_base64": base64.b64encode(pdf_bytes).decode("ascii"), "pdf_url": pdf_url, "report_id": report_id}


@tool("report_generate_clinician_simple_pdf")
async def generate_clinician_simple_pdf(
    diagnosis: dict,
    triage: dict,
    metadata: dict,
    recommendations: list[str] | None = None,
    image_base64: str | None = None,
    detections: list[dict] | None = None,
    annotated_image_base64: str | None = None,
) -> dict:
    """Generate a simplified physician summary report (no raw detection tables). Use when doctor wants a quick summary."""
    return await generate_clinician_simple_pdf_impl(
        diagnosis=diagnosis, triage=triage, metadata=metadata,
        recommendations=recommendations, image_base64=image_base64,
        detections=detections, annotated_image_base64=annotated_image_base64,
    )


__all__ = ["generate_clinician_simple_pdf", "generate_clinician_simple_pdf_impl"]
