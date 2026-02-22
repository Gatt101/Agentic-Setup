from __future__ import annotations

import base64
from io import BytesIO
from uuid import uuid4

from langchain_core.tools import tool
from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas

from services.storage import storage_service


def _draw_lines(pdf: canvas.Canvas, lines: list[str], start_y: int = 760) -> None:
    y = start_y
    for line in lines:
        pdf.drawString(56, y, line[:120])
        y -= 16
        if y < 60:
            pdf.showPage()
            y = 760


async def generate_clinician_pdf_impl(
    detections: list[dict],
    triage: dict,
    images: dict,
    metadata: dict,
) -> dict:
    """Generate clinician-focused PDF summary and persist report metadata."""
    report_id = uuid4().hex
    patient_id = str(metadata.get("patient_id", "unknown"))

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=LETTER)
    pdf.setTitle(f"OrthoAssist Clinician Report {report_id}")

    lines = [
        "OrthoAssist - Clinician Report",
        f"Patient ID: {patient_id}",
        f"Study ID: {metadata.get('study_id', 'N/A')}",
        f"Body Part: {metadata.get('body_part', 'N/A')}",
        f"Triage Level: {triage.get('level', 'N/A')}",
        f"Urgency Score: {triage.get('urgency_score', 'N/A')}",
        "",
        "Detections:",
    ]
    for detection in detections:
        lines.append(
            f"- {detection.get('label', 'finding')} score={detection.get('score', 0):.2f} bbox={detection.get('bbox', [])}"
        )
    if not detections:
        lines.append("- No detections returned.")

    if images.get("annotated_image_url"):
        lines.extend(["", f"Annotated image: {images['annotated_image_url']}"])

    lines.extend(["", "AI output for decision support only."])
    _draw_lines(pdf, lines)
    pdf.save()

    pdf_bytes = buffer.getvalue()
    saved_pdf = await storage_service.save_bytes(pdf_bytes, f"{report_id}.pdf", subdir="reports")
    pdf_url = saved_pdf["public_url"]

    await storage_service.save_report(
        report_data={
            "detections": detections,
            "triage": triage,
            "images": images,
            "metadata": metadata,
        },
        patient_id=patient_id,
        report_type="clinician_pdf",
        pdf_url=pdf_url,
        report_id=report_id,
    )

    return {
        "pdf_base64": base64.b64encode(pdf_bytes).decode("ascii"),
        "pdf_url": pdf_url,
        "report_id": report_id,
    }


@tool("report_generate_clinician_pdf")
async def generate_clinician_pdf(
    detections: list[dict],
    triage: dict,
    images: dict,
    metadata: dict,
) -> dict:
    """Generate a clinician-facing report PDF from structured analysis."""
    return await generate_clinician_pdf_impl(detections, triage, images, metadata)


__all__ = ["generate_clinician_pdf", "generate_clinician_pdf_impl"]
