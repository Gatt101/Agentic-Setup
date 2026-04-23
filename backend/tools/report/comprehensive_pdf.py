"""Comprehensive report PDF — used by the PDF Generation Agent.

Properly handles all patient info fields, both original and annotated images,
and care-plan outputs (treatment, rehabilitation, education, appointments).
Works for both doctor and patient roles.
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
    NAVY,
    SLATE,
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


# ── Patient field extraction ──────────────────────────────────────────────────

def _safe_str(value: Any, default: str = "Not provided") -> str:
    s = str(value or "").strip()
    return s if s and s.lower() not in {"none", "null", "nan", "not provided"} else default


def _extract_patient_fields(
    patient_info: dict,
    metadata: dict | None = None,
) -> dict[str, str]:
    """Pull patient fields from patient_info with metadata as fallback.

    patient_info keys: name, age, gender, doctor, body_part, patient_id, actor_id
    metadata keys:     patient_name, patient_age, patient_gender, doctor_name, actor_name, body_part, patient_id
    """
    meta = metadata or {}

    name = _safe_str(
        patient_info.get("name")
        or meta.get("patient_name")
        or patient_info.get("patient_name"),
    )
    age = _safe_str(
        patient_info.get("age")
        or meta.get("patient_age"),
    )
    gender = _safe_str(
        patient_info.get("gender")
        or meta.get("patient_gender"),
    )
    doctor = _safe_str(
        patient_info.get("doctor")
        or meta.get("doctor_name")
        or meta.get("actor_name")
        or patient_info.get("actor_name"),
    )
    body_part = _safe_str(
        patient_info.get("body_part")
        or meta.get("body_part"),
    )
    raw_pid = str(
        patient_info.get("patient_id")
        or meta.get("patient_id")
        or patient_info.get("actor_id")
        or "unknown"
    )
    return {
        "patient_id": human_readable_patient_id(raw_pid),
        "name": name,
        "age": age,
        "gender": gender,
        "doctor": doctor,
        "body_part": body_part,
    }


# ── Section counter helper ─────────────────────────────────────────────────────

class _SectionCounter:
    def __init__(self):
        self._n = 0

    def next(self) -> str:
        self._n += 1
        return str(self._n)


# ── PDF builder ───────────────────────────────────────────────────────────────

def _build_comprehensive_report(
    report_id: str,
    actor_role: str,
    diagnosis: dict[str, Any],
    triage: dict[str, Any],
    patient_fields: dict[str, str],
    image_base64: str | None,
    annotated_image_base64: str | None,
    recommendations: list[str],
    treatment_plan: dict[str, Any] | None,
    rehabilitation_plan: dict[str, Any] | None,
    patient_education: dict[str, Any] | None,
    appointment_schedule: dict[str, Any] | None,
) -> bytes:
    styles = build_styles()
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=50, leftMargin=50, topMargin=50, bottomMargin=44,
    )

    is_doctor = str(actor_role).lower() == "doctor"
    report_type = "Clinical Analysis Report" if is_doctor else "Patient Summary Report"
    triage_level = str(triage.get("level") or triage.get("triage_level") or "N/A").upper()
    exam_date = datetime.now(UTC).strftime("%d %b %Y")
    sec = _SectionCounter()

    story: list = []
    story += build_branded_header(report_type, report_id, styles)

    # ── 1. Patient Information ──────────────────────────────────────────────
    story += section_heading("Patient Information", styles, sec.next())
    story.append(info_grid([
        ["Patient ID",          patient_fields["patient_id"],  "Exam Date",   exam_date],
        ["Patient Name",        patient_fields["name"],        "Age",         patient_fields["age"]],
        ["Gender",              patient_fields["gender"],      "Body Part",   patient_fields["body_part"]],
        ["Referring Physician", patient_fields["doctor"],      "Report Type", report_type],
    ]))
    story.append(Spacer(1, 10))

    # ── 2. Clinical Findings ────────────────────────────────────────────────
    story += section_heading(
        "Clinical Findings" if is_doctor else "What We Found", styles, sec.next()
    )
    primary = str(
        diagnosis.get("primary_diagnosis")
        or diagnosis.get("finding")
        or "No findings recorded."
    )
    severity = str(diagnosis.get("severity") or "Not specified")
    story.append(Paragraph(f"<b>Finding:</b> {primary}", styles["Body"]))
    story.append(Paragraph(f"<b>Severity:</b> {severity.capitalize()}", styles["Body"]))
    if is_doctor:
        icd = str(diagnosis.get("icd_code") or "")
        if icd:
            story.append(Paragraph(f"<b>ICD-10:</b> {icd}", styles["Body"]))
    notes = diagnosis.get("notes") or diagnosis.get("clinical_notes")
    if notes:
        story.append(Paragraph(f"<b>Notes:</b> {notes}", styles["Body"]))
    story.append(Spacer(1, 8))

    # ── 3. Triage Assessment ────────────────────────────────────────────────
    story += section_heading("Triage Assessment", styles, sec.next())
    story.append(triage_badge_table(triage_level, styles))
    timeframe = str(triage.get("recommended_timeframe") or "")
    if timeframe:
        story.append(Paragraph(f"<b>Recommended timeframe:</b> {timeframe}", styles["Body"]))
    if is_doctor:
        urgency = triage.get("urgency_score")
        if urgency is not None:
            story.append(Paragraph(f"<b>Urgency score:</b> {float(urgency):.3f}", styles["Body"]))
    if triage.get("rationale"):
        story.append(Paragraph(f"<b>Rationale:</b> {triage['rationale']}", styles["Body"]))
    story.append(Spacer(1, 8))

    # ── 4. Recommended Actions ──────────────────────────────────────────────
    story += section_heading(
        "Recommended Actions" if is_doctor else "What To Do Next", styles, sec.next()
    )
    for action in (recommendations or ["Follow clinical protocol appropriate to triage level."]):
        story.append(Paragraph(f"• {action}", styles["Body"]))
    story.append(Spacer(1, 8))

    # ── 5. Treatment Plan ───────────────────────────────────────────────────
    if treatment_plan and isinstance(treatment_plan, dict):
        story += section_heading(
            "Treatment Plan" if is_doctor else "Your Treatment Plan", styles, sec.next()
        )
        approach = str(treatment_plan.get("approach", "conservative")).capitalize()
        story.append(Paragraph(f"<b>Approach:</b> {approach}", styles["Body"]))

        for label, key in [
            ("Immediate Steps", "immediate_steps"),
            ("Long-term Plan",  "long_term_plan"),
            ("Medications",     "medications"),
            ("Restrictions",    "restrictions"),
        ]:
            items = treatment_plan.get(key, [])
            if items:
                story.append(Paragraph(f"<b>{label}:</b>", styles["Body"]))
                for item in items:
                    story.append(Paragraph(f"  • {item}", styles["Body"]))
        story.append(Spacer(1, 8))

    # ── 6. Rehabilitation Plan ──────────────────────────────────────────────
    if rehabilitation_plan and isinstance(rehabilitation_plan, dict):
        story += section_heading(
            "Rehabilitation Protocol" if is_doctor else "Your Recovery Plan", styles, sec.next()
        )
        phases = rehabilitation_plan.get("phases") or rehabilitation_plan.get("phase_plan") or []
        if phases:
            for phase in phases:
                if isinstance(phase, dict):
                    pname = str(phase.get("phase") or phase.get("name") or "")
                    pdesc = str(phase.get("description") or phase.get("activities") or "")
                    story.append(Paragraph(f"<b>{pname}:</b> {pdesc}", styles["Body"]))
                else:
                    story.append(Paragraph(f"• {phase}", styles["Body"]))
        else:
            for k, v in rehabilitation_plan.items():
                if v and k not in ("success", "confidence", "error"):
                    story.append(Paragraph(
                        f"<b>{k.replace('_', ' ').title()}:</b> {v}", styles["Body"]
                    ))
        story.append(Spacer(1, 8))

    # ── 7. Patient Education ────────────────────────────────────────────────
    if patient_education and isinstance(patient_education, dict):
        story += section_heading("Patient Education", styles, sec.next())
        for k, v in patient_education.items():
            if v and k not in ("success", "confidence", "error"):
                story.append(Paragraph(
                    f"<b>{k.replace('_', ' ').title()}:</b> {v}", styles["Body"]
                ))
        story.append(Spacer(1, 8))

    # ── 8. Appointment Schedule ─────────────────────────────────────────────
    if appointment_schedule and isinstance(appointment_schedule, dict):
        story += section_heading(
            "Appointment Schedule" if is_doctor else "Your Follow-up Appointments",
            styles, sec.next(),
        )
        appointments = (
            appointment_schedule.get("appointments")
            or appointment_schedule.get("schedule")
            or []
        )
        if appointments:
            for appt in appointments:
                if isinstance(appt, dict):
                    appt_str = (
                        f"{appt.get('timing', '')} — "
                        f"{appt.get('type') or appt.get('description', '')}"
                    )
                    story.append(Paragraph(f"• {appt_str}", styles["Body"]))
                else:
                    story.append(Paragraph(f"• {appt}", styles["Body"]))
        else:
            for k, v in appointment_schedule.items():
                if v and k not in ("success", "confidence", "error"):
                    story.append(Paragraph(
                        f"<b>{k.replace('_', ' ').title()}:</b> {v}", styles["Body"]
                    ))
        story.append(Spacer(1, 8))

    # ── 9. Imaging Evidence ─────────────────────────────────────────────────
    orig_img = pdf_image_from_base64(image_base64)
    ann_img = pdf_image_from_base64(annotated_image_base64)
    if orig_img or ann_img:
        story += section_heading(
            "Imaging Evidence" if is_doctor else "Your X-ray Images", styles, sec.next()
        )
        img_table = Table(
            [
                ["Original X-ray", "AI-Annotated X-ray"],
                [
                    orig_img or Paragraph("Not available", styles["Small"]),
                    ann_img or Paragraph("Not available", styles["Small"]),
                ],
            ],
            colWidths=[3.1 * inch, 3.1 * inch],
        )
        img_table.setStyle(TableStyle([
            ("FONTNAME",       (0, 0), (-1,  0), "Helvetica-Bold"),
            ("FONTSIZE",       (0, 0), (-1,  0), 9),
            ("BACKGROUND",     (0, 0), (-1,  0), LIGHT_BLUE),
            ("ALIGN",          (0, 0), (-1, -1), "CENTER"),
            ("VALIGN",         (0, 0), (-1, -1), "MIDDLE"),
            ("GRID",           (0, 0), (-1, -1), 0.7, BORDER),
            ("TOPPADDING",     (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING",  (0, 0), (-1, -1), 8),
        ]))
        story.append(img_table)
        story.append(Spacer(1, 10))

    # ── 10. Legal Disclaimer ────────────────────────────────────────────────
    story += section_heading("Legal Disclaimer", styles, sec.next())
    story.append(Paragraph(DISCLAIMER_TEXT, styles["Disclaimer"]))
    story.append(Spacer(1, 6))
    story.append(HRFlowable(width="100%", thickness=0.5, color=TEAL))
    footer = (
        "OrthoAssist  •  AI Clinical Decision Support  •  CONFIDENTIAL — PHYSICIAN COPY"
        if is_doctor
        else "OrthoAssist  •  AI Clinical Decision Support  •  Confidential Patient Document"
    )
    story.append(Paragraph(footer, styles["FooterText"]))

    doc.build(story)
    output = buffer.getvalue()
    buffer.close()
    return output


# ── Public impl ───────────────────────────────────────────────────────────────

async def generate_comprehensive_pdf_impl(
    diagnosis: dict,
    triage: dict,
    patient_info: dict,
    actor_role: str = "doctor",
    image_base64: str | None = None,
    annotated_image_base64: str | None = None,
    detections: list[dict] | None = None,
    recommendations: list[str] | None = None,
    metadata: dict | None = None,
    treatment_plan: dict | None = None,
    rehabilitation_plan: dict | None = None,
    patient_education: dict | None = None,
    appointment_schedule: dict | None = None,
) -> dict:
    """Generate a comprehensive PDF with all patient info, both images, and care plan data."""
    patient_info = patient_info or {}
    metadata = metadata or {}
    detections = detections or []
    recommendations = recommendations or []

    if not diagnosis or not (diagnosis.get("finding") or diagnosis.get("primary_diagnosis")):
        return {"error": "Missing clinical diagnosis", "pdf_url": None}
    if not triage or not (triage.get("level") or triage.get("triage_level")):
        return {"error": "Missing triage assessment", "pdf_url": None}

    # Auto-annotate if annotated image is absent but we have original + detections
    if not annotated_image_base64 and image_base64 and detections:
        try:
            ann = await annotate_xray_image_impl(image_base64=image_base64, detections=detections)
            maybe = ann.get("annotated_image_base64")
            if isinstance(maybe, str) and maybe:
                annotated_image_base64 = maybe
        except Exception as exc:
            logger.warning("Auto-annotate failed in comprehensive PDF: {}", exc)

    patient_fields = _extract_patient_fields(patient_info, metadata)
    report_id = uuid4().hex
    patient_id = str(
        patient_info.get("patient_id")
        or metadata.get("patient_id")
        or patient_info.get("actor_id")
        or "unknown"
    )

    pdf_bytes = _build_comprehensive_report(
        report_id=report_id,
        actor_role=actor_role,
        diagnosis=diagnosis,
        triage=triage,
        patient_fields=patient_fields,
        image_base64=image_base64,
        annotated_image_base64=annotated_image_base64,
        recommendations=recommendations,
        treatment_plan=treatment_plan,
        rehabilitation_plan=rehabilitation_plan,
        patient_education=patient_education,
        appointment_schedule=appointment_schedule,
    )

    saved = await storage_service.save_bytes(pdf_bytes, f"{report_id}.pdf", subdir="reports")
    pdf_url = saved["public_url"]

    await storage_service.save_report(
        report_data={
            "diagnosis": diagnosis,
            "triage": triage,
            "patient_info": patient_info,
            "recommendations": recommendations,
            "detections": detections,
        },
        patient_id=patient_id,
        report_type="comprehensive_pdf",
        pdf_url=pdf_url,
        report_id=report_id,
    )

    logger.info(
        "Comprehensive PDF generated: report_id={} patient={} role={}",
        report_id, patient_fields["name"], actor_role,
    )
    return {
        "pdf_base64": base64.b64encode(pdf_bytes).decode("ascii"),
        "pdf_url": pdf_url,
        "report_id": report_id,
    }


@tool("report_generate_comprehensive_pdf")
async def generate_comprehensive_pdf(
    diagnosis: dict,
    triage: dict,
    patient_info: dict,
    actor_role: str = "doctor",
    image_base64: str | None = None,
    annotated_image_base64: str | None = None,
    detections: list[dict] | None = None,
    recommendations: list[str] | None = None,
    metadata: dict | None = None,
    treatment_plan: dict | None = None,
    rehabilitation_plan: dict | None = None,
    patient_education: dict | None = None,
    appointment_schedule: dict | None = None,
) -> dict:
    """Generate a comprehensive PDF report with correct patient name/age/gender,
    both original and AI-annotated images side-by-side, and full care plan
    (treatment, rehabilitation, patient education, appointments)."""
    return await generate_comprehensive_pdf_impl(
        diagnosis=diagnosis,
        triage=triage,
        patient_info=patient_info,
        actor_role=actor_role,
        image_base64=image_base64,
        annotated_image_base64=annotated_image_base64,
        detections=detections,
        recommendations=recommendations,
        metadata=metadata,
        treatment_plan=treatment_plan,
        rehabilitation_plan=rehabilitation_plan,
        patient_education=patient_education,
        appointment_schedule=appointment_schedule,
    )


__all__ = ["generate_comprehensive_pdf", "generate_comprehensive_pdf_impl"]
