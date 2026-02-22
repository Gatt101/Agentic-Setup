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
        y -= 18
        if y < 60:
            pdf.showPage()
            y = 760


async def generate_patient_pdf_impl(
    diagnosis: dict,
    triage: dict,
    patient_info: dict,
    recommendations: list[str],
) -> dict:
    """Generate a patient-friendly PDF and store it."""
    report_id = uuid4().hex
    patient_id = str(patient_info.get("patient_id", "unknown"))

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=LETTER)
    pdf.setTitle(f"OrthoAssist Patient Report {report_id}")
    lines = [
        "OrthoAssist - Patient Report",
        f"Patient ID: {patient_id}",
        f"Finding: {diagnosis.get('finding', 'N/A')}",
        f"Severity: {diagnosis.get('severity', 'N/A')}",
        f"Triage: {triage.get('level', 'N/A')}",
        f"Recommended timeframe: {triage.get('recommended_timeframe', 'N/A')}",
        "",
        "Recommendations:",
    ]
    lines.extend([f"- {item}" for item in recommendations] or ["- Follow physician guidance."])
    lines.append("")
    lines.append("This report is AI-assisted and does not replace physician diagnosis.")
    _draw_lines(pdf, lines)
    pdf.save()

    pdf_bytes = buffer.getvalue()
    saved_pdf = await storage_service.save_bytes(pdf_bytes, f"{report_id}.pdf", subdir="reports")
    pdf_url = saved_pdf["public_url"]

    await storage_service.save_report(
        report_data={
            "diagnosis": diagnosis,
            "triage": triage,
            "patient_info": patient_info,
            "recommendations": recommendations,
        },
        patient_id=patient_id,
        report_type="patient_pdf",
        pdf_url=pdf_url,
        report_id=report_id,
    )

    return {
        "pdf_base64": base64.b64encode(pdf_bytes).decode("ascii"),
        "pdf_url": pdf_url,
        "report_id": report_id,
    }


@tool("report_generate_patient_pdf")
async def generate_patient_pdf(
    diagnosis: dict,
    triage: dict,
    patient_info: dict,
    recommendations: list[str],
) -> dict:
    """Generate a patient-facing report PDF and return base64 + URL."""
    return await generate_patient_pdf_impl(diagnosis, triage, patient_info, recommendations)


__all__ = ["generate_patient_pdf", "generate_patient_pdf_impl"]
