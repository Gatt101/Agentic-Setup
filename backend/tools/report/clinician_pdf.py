"""Clinical-depth report for doctors — full technical detail.

Sections: Patient & Study Info, Technical Detections, Clinical Diagnosis,
Differential Diagnoses, Triage Assessment, Knowledge Context (treatment / anatomy),
Imaging Evidence, Physician Sign-off, Legal Disclaimer.
"""
from __future__ import annotations

import base64
from datetime import UTC, datetime
from io import BytesIO
from typing import Any
from uuid import uuid4

from langchain_core.tools import tool
from loguru import logger
from reportlab.lib import colors
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
def validate_clinician_report_inputs(
    detections: list[dict],
    triage: dict,
    diagnosis: dict,
    metadata: dict,
) -> None:
    # Empty detections is a soft warning — the PDF handles it gracefully.
    if not detections:
        logger.warning("Clinician PDF: no detections — report will omit detection table.")

    hard_missing = []
    if not diagnosis or not (diagnosis.get("finding") or diagnosis.get("primary_diagnosis")):
        hard_missing.append("clinical diagnosis")
    if not triage or not (triage.get("level") or triage.get("triage_level")):
        hard_missing.append("triage assessment")
    if hard_missing:
        raise ValueError(
            f"Cannot generate clinical report — missing: {', '.join(hard_missing)}. "
            "Complete the full diagnostic pipeline first."
        )


# ── Builder ───────────────────────────────────────────────────────────────────
def _build_clinical_report(
    report_id: str,
    detections: list[dict],
    diagnosis: dict[str, Any],
    triage: dict[str, Any],
    knowledge_context: dict[str, Any],
    images: dict[str, Any],
    metadata: dict[str, Any],
) -> bytes:
    styles = build_styles()
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=50, leftMargin=50, topMargin=50, bottomMargin=44)

    raw_pid = str(metadata.get("patient_id") or "unknown")
    pt_id = human_readable_patient_id(raw_pid)
    doctor_name = str(metadata.get("doctor_name") or metadata.get("actor_name") or "Not provided")
    exam_date = datetime.now(UTC).strftime("%d %b %Y  %H:%M UTC")
    triage_level = str(triage.get("level") or triage.get("triage_level") or "N/A").upper()
    body_part = str(metadata.get("body_part") or "N/A")

    story: list = []

    # ── Header ──────────────────────────────────────────────────────────────
    story += build_branded_header("Clinical Depth Report — Physician Copy", report_id, styles)

    # ── 1. Patient & Study Information ──────────────────────────────────────
    story += section_heading("Patient & Study Information", styles, "1")
    story.append(info_grid([
        ["Patient ID", pt_id, "Exam Date", exam_date],
        ["Body Part", body_part, "Study ID", str(metadata.get("study_id") or report_id[:12])],
        ["Ordering Physician", doctor_name, "Report Type", "AI-Assisted Clinical Depth"],
        ["Institution", str(metadata.get("institution") or "OrthoAssist Platform"), "Modality", "Digital X-ray"],
    ]))
    story.append(Spacer(1, 10))

    # ── 2. AI Vision — Technical Detections ─────────────────────────────────
    story += section_heading("AI Vision Analysis — Technical Detections", styles, "2")
    story.append(Paragraph(
        f"Model detected <b>{len(detections)}</b> finding(s) on the submitted image. "
        "Full bounding-box coordinates and confidence scores are listed below.",
        styles["Body"],
    ))
    story.append(Spacer(1, 4))

    if detections:
        det_rows = [["#", "Label / Finding", "Confidence", "Bounding Box (x1,y1,x2,y2)"]]
        for i, det in enumerate(detections, 1):
            bbox = det.get("bbox") or det.get("box") or []
            if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
                bbox_str = f"[{', '.join(f'{v:.1f}' for v in bbox)}]"
            else:
                bbox_str = str(bbox)
            det_rows.append([
                str(i),
                str(det.get("label") or det.get("class") or "Finding"),
                f"{float(det.get('score') or det.get('confidence') or 0):.3f}",
                bbox_str,
            ])
        det_table = Table(det_rows, colWidths=[0.4 * inch, 2.4 * inch, 1.2 * inch, 3.2 * inch])
        det_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), NAVY),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("BACKGROUND", (0, 1), (-1, -1), LIGHT_BLUE),
            ("GRID", (0, 0), (-1, -1), 0.5, BORDER),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(det_table)
    else:
        story.append(Paragraph("No detections returned by the vision model.", styles["Body"]))
    story.append(Spacer(1, 10))

    # ── 3. Clinical Diagnosis ────────────────────────────────────────────────
    story += section_heading("Clinical Diagnosis", styles, "3")
    primary = str(diagnosis.get("primary_diagnosis") or diagnosis.get("finding") or "N/A")
    severity = str(diagnosis.get("severity") or "N/A")
    icd = str(diagnosis.get("icd_code") or "N/A")
    confidence = diagnosis.get("confidence") or diagnosis.get("ai_confidence")

    story.append(info_grid([
        ["Primary Diagnosis", primary, "Severity", severity.capitalize()],
        ["ICD-10 Code", icd, "AI Confidence", f"{float(confidence):.1%}" if confidence else "N/A"],
    ]))
    story.append(Spacer(1, 6))

    if diagnosis.get("notes") or diagnosis.get("clinical_notes"):
        story.append(Paragraph(
            f"<b>Clinical Notes:</b> {diagnosis.get('notes') or diagnosis.get('clinical_notes')}",
            styles["Body"],
        ))

    differentials = diagnosis.get("differential_diagnoses") or diagnosis.get("differentials") or []
    if differentials:
        story.append(Paragraph("<b>Differential Diagnoses:</b>", styles["BodyBold"]))
        for d in differentials:
            if isinstance(d, dict):
                story.append(Paragraph(f"• {d.get('diagnosis', d)} — probability: {d.get('probability', 'N/A')}", styles["Body"]))
            else:
                story.append(Paragraph(f"• {d}", styles["Body"]))
    story.append(Spacer(1, 10))

    # ── 4. Triage Assessment ─────────────────────────────────────────────────
    story += section_heading("Triage Assessment", styles, "4")
    story.append(triage_badge_table(triage_level, styles))
    story.append(Spacer(1, 6))
    story.append(info_grid([
        ["Urgency Score", str(triage.get("urgency_score") or "N/A"), "Recommended Timeframe", str(triage.get("recommended_timeframe") or "N/A")],
        ["Rationale", str(triage.get("rationale") or "N/A"), "Escalation Required", "Yes" if triage_level == "RED" else "No"],
    ], col_widths=[1.5 * inch, 2.0 * inch, 2.0 * inch, 1.7 * inch]))
    story.append(Spacer(1, 10))

    # ── 5. Knowledge Context ─────────────────────────────────────────────────
    if knowledge_context:
        story += section_heading("Knowledge Context — Treatment & Anatomy", styles, "5")
        for tool_name, payload in knowledge_context.items():
            if not isinstance(payload, dict):
                continue
            section_title = tool_name.replace("_", " ").title()
            story.append(Paragraph(f"<b>{section_title}</b>", styles["BodyBold"]))
            for k, v in payload.items():
                if isinstance(v, list):
                    story.append(Paragraph(f"<b>{k}:</b>", styles["Body"]))
                    for item in v:
                        story.append(Paragraph(f"  • {item}", styles["Body"]))
                else:
                    story.append(Paragraph(f"<b>{k}:</b> {v}", styles["Body"]))
            story.append(Spacer(1, 5))
        story.append(Spacer(1, 5))

    # ── 6. Imaging Evidence ──────────────────────────────────────────────────
    orig_img = pdf_image_from_base64(images.get("original_image_base64") or images.get("image_base64"))
    ann_img = pdf_image_from_base64(images.get("annotated_image_base64"))
    if orig_img or ann_img:
        story += section_heading("Imaging Evidence", styles, "6")
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

    # ── 7. Physician Sign-off ────────────────────────────────────────────────
    story += section_heading("Physician Review & Sign-off", styles, "7")
    signoff_table = Table([
        ["Reviewing Physician:", "_" * 40, "Date:", "_" * 20],
        ["Signature:", "_" * 40, "Licence No:", "_" * 20],
        ["Clinical Override:", "☐  Accept AI findings as preliminary      ☐  Override — see addendum", "", ""],
    ], colWidths=[1.5 * inch, 3.2 * inch, 0.9 * inch, 1.6 * inch])
    signoff_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("SPAN", (1, 2), (3, 2)),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.4, BORDER),
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT_BLUE),
    ]))
    story.append(signoff_table)
    story.append(Spacer(1, 10))

    # ── 8. Disclaimer ────────────────────────────────────────────────────────
    story += section_heading("Legal & Clinical Disclaimer", styles, "8")
    story.append(Paragraph(DISCLAIMER_TEXT, styles["Disclaimer"]))
    story.append(Spacer(1, 6))
    story.append(HRFlowable(width="100%", thickness=0.5, color=TEAL))
    story.append(Paragraph(
        "OrthoAssist  •  AI Clinical Decision Support  •  CONFIDENTIAL — FOR CLINICIAN USE ONLY",
        styles["FooterText"],
    ))

    doc.build(story)
    output = buffer.getvalue()
    buffer.close()
    return output


# ── Public impl ───────────────────────────────────────────────────────────────
async def generate_clinician_pdf_impl(
    detections: list[dict],
    triage: dict,
    images: dict,
    metadata: dict,
    diagnosis: dict | None = None,
    knowledge_context: dict | None = None,
) -> dict:
    """Generate a full clinical-depth physician report PDF."""
    detections = detections or []
    diagnosis = diagnosis or {}
    knowledge_context = knowledge_context or {}
    images = images or {}
    metadata = metadata or {}

    validate_clinician_report_inputs(detections, triage, diagnosis, metadata)

    # Auto-build annotated image if missing
    image_b64 = images.get("image_base64") or images.get("original_image_base64")
    if not images.get("annotated_image_base64") and image_b64 and detections:
        try:
            ann = await annotate_xray_image_impl(image_base64=image_b64, detections=detections)
            maybe = ann.get("annotated_image_base64")
            if maybe:
                images = {**images, "annotated_image_base64": maybe}
        except Exception as exc:
            logger.warning("Annotate failed in clinician PDF: {}", exc)

    report_id = uuid4().hex
    patient_id = str(metadata.get("patient_id") or "unknown")

    pdf_bytes = _build_clinical_report(
        report_id=report_id, detections=detections, diagnosis=diagnosis,
        triage=triage, knowledge_context=knowledge_context, images=images, metadata=metadata,
    )

    saved = await storage_service.save_bytes(pdf_bytes, f"{report_id}.pdf", subdir="reports")
    pdf_url = saved["public_url"]

    await storage_service.save_report(
        report_data={"detections": detections, "triage": triage, "diagnosis": diagnosis,
                     "knowledge_context": knowledge_context, "images": images, "metadata": metadata},
        patient_id=patient_id, report_type="clinician_depth_pdf", pdf_url=pdf_url, report_id=report_id,
    )

    return {"pdf_base64": base64.b64encode(pdf_bytes).decode("ascii"), "pdf_url": pdf_url, "report_id": report_id}


@tool("report_generate_clinician_pdf")
async def generate_clinician_pdf(
    detections: list[dict],
    triage: dict,
    images: dict,
    metadata: dict,
    diagnosis: dict | None = None,
    knowledge_context: dict | None = None,
) -> dict:
    """Generate a full clinical-depth physician report with detections, diagnosis, triage, knowledge context, and sign-off block."""
    return await generate_clinician_pdf_impl(
        detections=detections, triage=triage, images=images, metadata=metadata,
        diagnosis=diagnosis, knowledge_context=knowledge_context,
    )


__all__ = ["generate_clinician_pdf", "generate_clinician_pdf_impl"]


