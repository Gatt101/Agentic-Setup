from __future__ import annotations

import base64
from datetime import UTC, datetime
from io import BytesIO
from typing import Any
from uuid import uuid4

from langchain_core.tools import tool
from loguru import logger
from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from services.storage import storage_service
from tools.vision.annotator import annotate_xray_image_impl


def _strip_data_url(value: str) -> str:
    if value.strip().startswith("data:") and "," in value:
        return value.split(",", 1)[1]
    return value


def _pdf_image_from_base64(value: str | None, max_width: float = 2.6 * inch, max_height: float = 2.1 * inch) -> Image | None:
    if not value or not isinstance(value, str):
        return None

    try:
        payload = _strip_data_url(value)
        image_bytes = base64.b64decode(payload)
        image_stream = BytesIO(image_bytes)

        with PILImage.open(image_stream) as pil_image:
            if pil_image.mode not in {"RGB", "L"}:
                pil_image = pil_image.convert("RGB")

            width, height = pil_image.size
            width_ratio = max_width / max(width, 1)
            height_ratio = max_height / max(height, 1)
            scale = min(width_ratio, height_ratio, 1.0)
            draw_width = width * scale
            draw_height = height * scale

            normalized = BytesIO()
            pil_image.save(normalized, format="JPEG", quality=88)
            normalized.seek(0)
            return Image(normalized, width=draw_width, height=draw_height)
    except Exception:
        return None


class PDFReportAgent:
    """Generates patient-facing medical assessment PDF reports."""

    def __init__(self) -> None:
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _setup_custom_styles(self) -> None:
        self.styles.add(
            ParagraphStyle(
                name="ReportTitle",
                parent=self.styles["Title"],
                fontSize=18,
                spaceAfter=16,
                alignment=TA_CENTER,
                fontName="Helvetica-Bold",
                textColor=colors.HexColor("#1F3A5B"),
            )
        )
        self.styles.add(
            ParagraphStyle(
                name="SectionHeader",
                parent=self.styles["Heading2"],
                fontSize=12,
                spaceAfter=6,
                spaceBefore=10,
                fontName="Helvetica-Bold",
                textColor=colors.HexColor("#2A4E78"),
            )
        )
        self.styles.add(
            ParagraphStyle(
                name="ReportBody",
                parent=self.styles["Normal"],
                fontSize=10,
                leading=14,
                spaceAfter=6,
                fontName="Helvetica",
            )
        )
        self.styles.add(
            ParagraphStyle(
                name="Disclaimer",
                parent=self.styles["Normal"],
                fontSize=8.5,
                leading=12,
                textColor=colors.HexColor("#6B7280"),
                fontName="Helvetica-Oblique",
            )
        )

    def _build_header(self, report_id: str) -> list:
        return [
            Paragraph("OrthoAssist - AI Triage Assessment Report", self.styles["ReportTitle"]),
            Paragraph(f"Report ID: {report_id}", self.styles["ReportBody"]),
            Spacer(1, 8),
        ]

    def _build_patient_info(self, patient_info: dict[str, Any]) -> list:
        patient_id = str(patient_info.get("patient_id") or "unknown")
        name = str(patient_info.get("name") or "Not provided")
        age = str(patient_info.get("age") or "Not provided")
        gender = str(patient_info.get("gender") or "Not provided")

        table = Table(
            [
                ["Patient ID", patient_id, "Exam Date", datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")],
                ["Name", name, "Age", age],
                ["Gender", gender, "Referring Doctor", str(patient_info.get("doctor") or "Not provided")],
            ],
            colWidths=[1.2 * inch, 2.1 * inch, 1.3 * inch, 2.2 * inch],
        )
        table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9.5),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EFF6FF")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#1E3A5F")),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )

        return [Paragraph("1. Patient and Study Information", self.styles["SectionHeader"]), table, Spacer(1, 8)]

    def _build_findings(self, diagnosis: dict[str, Any], triage: dict[str, Any], recommendations: list[str]) -> list:
        lines = [
            f"<b>Finding:</b> {diagnosis.get('finding', 'N/A')}",
            f"<b>Severity:</b> {diagnosis.get('severity', 'N/A')}",
            f"<b>Triage Level:</b> {triage.get('level', 'N/A')}",
            f"<b>Recommended timeframe:</b> {triage.get('recommended_timeframe', 'N/A')}",
        ]

        elements: list = [Paragraph("2. AI Clinical Summary", self.styles["SectionHeader"])]
        for line in lines:
            elements.append(Paragraph(line, self.styles["ReportBody"]))

        elements.append(Paragraph("<b>Recommended Actions:</b>", self.styles["ReportBody"]))
        for action in recommendations or ["Follow physician guidance."]:
            elements.append(Paragraph(f"- {action}", self.styles["ReportBody"]))

        elements.append(Spacer(1, 8))
        return elements

    def _build_images(self, original_image_base64: str | None, annotated_image_base64: str | None) -> list:
        original = _pdf_image_from_base64(original_image_base64)
        annotated = _pdf_image_from_base64(annotated_image_base64)

        original_cell = original if original else Paragraph("Original image not available", self.styles["ReportBody"])
        annotated_cell = annotated if annotated else Paragraph("Annotated image not available", self.styles["ReportBody"])

        table = Table(
            [
                ["Original X-ray", "Annotated X-ray"],
                [original_cell, annotated_cell],
            ],
            colWidths=[3.0 * inch, 3.0 * inch],
        )
        table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 10),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F1F5F9")),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("GRID", (0, 0), (-1, -1), 0.7, colors.HexColor("#CBD5E1")),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )

        return [Paragraph("3. Imaging Evidence", self.styles["SectionHeader"]), table, Spacer(1, 8)]

    def _build_disclaimer(self) -> list:
        return [
            Paragraph("4. Legal Disclaimer", self.styles["SectionHeader"]),
            Paragraph(
                "This report is AI-generated for preliminary triage support only and does not replace a licensed clinical diagnosis.",
                self.styles["Disclaimer"],
            ),
        ]

    def generate_report(
        self,
        report_id: str,
        diagnosis: dict[str, Any],
        triage: dict[str, Any],
        patient_info: dict[str, Any],
        recommendations: list[str],
        image_base64: str | None,
        annotated_image_base64: str | None,
    ) -> bytes:
        buffer = BytesIO()
        document = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=52,
            leftMargin=52,
            topMargin=52,
            bottomMargin=44,
        )

        story: list = []
        story.extend(self._build_header(report_id))
        story.extend(self._build_patient_info(patient_info))
        story.extend(self._build_findings(diagnosis, triage, recommendations))
        story.extend(self._build_images(image_base64, annotated_image_base64))
        story.extend(self._build_disclaimer())
        document.build(story)

        output = buffer.getvalue()
        buffer.close()
        return output


pdf_report_agent = PDFReportAgent()


async def generate_patient_pdf_impl(
    diagnosis: dict,
    triage: dict,
    patient_info: dict,
    recommendations: list[str],
    image_base64: str | None = None,
    detections: list[dict] | None = None,
    annotated_image_base64: str | None = None,
) -> dict:
    """Generate a patient-facing PDF report with original and annotated images."""
    report_id = uuid4().hex
    patient_info = patient_info or {}
    patient_id = str(patient_info.get("patient_id") or "unknown")
    detections = detections or []

    if not annotated_image_base64 and image_base64 and detections:
        try:
            annotation = await annotate_xray_image_impl(image_base64=image_base64, detections=detections)
            maybe = annotation.get("annotated_image_base64")
            if isinstance(maybe, str) and maybe:
                annotated_image_base64 = maybe
        except Exception as exc:
            logger.warning("Failed to auto-generate annotated image for report {}: {}", report_id, exc)

    pdf_bytes = pdf_report_agent.generate_report(
        report_id=report_id,
        diagnosis=diagnosis,
        triage=triage,
        patient_info=patient_info,
        recommendations=recommendations,
        image_base64=image_base64,
        annotated_image_base64=annotated_image_base64,
    )

    saved_pdf = await storage_service.save_bytes(pdf_bytes, f"{report_id}.pdf", subdir="reports")
    pdf_url = saved_pdf["public_url"]

    await storage_service.save_report(
        report_data={
            "diagnosis": diagnosis,
            "triage": triage,
            "patient_info": patient_info,
            "recommendations": recommendations,
            "detections": detections,
            "has_original_image": bool(image_base64),
            "has_annotated_image": bool(annotated_image_base64),
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
    image_base64: str | None = None,
    detections: list[dict] | None = None,
    annotated_image_base64: str | None = None,
) -> dict:
    """Generate a styled patient report PDF and return base64 + URL."""
    return await generate_patient_pdf_impl(
        diagnosis=diagnosis,
        triage=triage,
        patient_info=patient_info,
        recommendations=recommendations,
        image_base64=image_base64,
        detections=detections,
        annotated_image_base64=annotated_image_base64,
    )


__all__ = ["generate_patient_pdf", "generate_patient_pdf_impl"]
