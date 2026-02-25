"""Shared PDF engine utilities: branding, styles, logo, and patient ID helpers."""
from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    Image,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

# ── Brand colours ─────────────────────────────────────────────────────────────
NAVY = colors.HexColor("#0F2952")
TEAL = colors.HexColor("#0B7EA3")
LIGHT_BLUE = colors.HexColor("#EFF6FF")
MID_BLUE = colors.HexColor("#2A4E78")
SLATE = colors.HexColor("#64748B")
BORDER = colors.HexColor("#CBD5E1")
WHITE = colors.white
RED_BADGE = colors.HexColor("#DC2626")
AMBER_BADGE = colors.HexColor("#D97706")
GREEN_BADGE = colors.HexColor("#16A34A")
RED_BG = colors.HexColor("#FEF2F2")
AMBER_BG = colors.HexColor("#FFFBEB")
GREEN_BG = colors.HexColor("#F0FDF4")

TRIAGE_COLOR = {"RED": RED_BADGE, "AMBER": AMBER_BADGE, "GREEN": GREEN_BADGE}
TRIAGE_BG = {"RED": RED_BG, "AMBER": AMBER_BG, "GREEN": GREEN_BG}

LOGO_PATH = Path(__file__).resolve().parents[2] / "assets" / "ortho_icon_report.png"
# Fallbacks: frontend icons dir, then frontend public dir
_LOGO_FALLBACK_ICONS = Path(__file__).resolve().parents[3] / "frontend" / "icons" / "ortho_icon_report.png"
_LOGO_FALLBACK_PUBLIC = Path(__file__).resolve().parents[3] / "frontend" / "public" / "ortho_icon_report.png"


# ── Human-readable patient ID ─────────────────────────────────────────────────
def human_readable_patient_id(raw_id: str) -> str:
    """Deterministically map any raw ID (MongoDB ObjectId, UUID, etc.) to PT-YYYY-XXXXXX."""
    raw = str(raw_id or "").strip().upper()
    if re.fullmatch(r"PT-\d{4}-[A-F0-9]{6}", raw):
        return raw

    clean = re.sub(r"[^a-zA-Z0-9]", "", str(raw_id))
    hash_suffix = hashlib.md5(clean.encode()).hexdigest()[:6].upper()
    year = datetime.now(UTC).year
    return f"PT-{year}-{hash_suffix}"


# ── Logo helper ───────────────────────────────────────────────────────────────
def get_logo(width: float = 0.45 * inch, height: float = 0.45 * inch) -> Image | None:
    """Return a ReportLab Image from the brand logo, or None if not found."""
    for candidate in (LOGO_PATH, _LOGO_FALLBACK_ICONS, _LOGO_FALLBACK_PUBLIC):
        try:
            if candidate.exists():
                return Image(str(candidate), width=width, height=height)
        except Exception:
            continue
    return None


# ── Triage badge ──────────────────────────────────────────────────────────────
def triage_badge_table(level: str, styles: Any) -> Table:
    """Return a coloured triage-level badge table cell."""
    lvl = str(level).upper()
    badge_color = TRIAGE_COLOR.get(lvl, SLATE)
    bg_color = TRIAGE_BG.get(lvl, colors.HexColor("#F8FAFC"))
    label = {
        "RED": "IMMEDIATE  —  HIGH RISK",
        "AMBER": "URGENT  —  MODERATE RISK",
        "GREEN": "ROUTINE  —  LOW RISK",
    }.get(lvl, lvl)

    badge_style = ParagraphStyle(
        f"BadgeText_{lvl}",
        parent=styles["BadgeText"],
        textColor=badge_color,
        fontSize=11,
        fontName="Helvetica-Bold",
        leading=16,
        alignment=TA_CENTER,
    )

    badge = Table([[Paragraph(label, badge_style)]], colWidths=[5.5 * inch])
    badge.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), bg_color),
                ("BOX", (0, 0), (-1, -1), 2, badge_color),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("LEFTPADDING", (0, 0), (-1, -1), 16),
                ("RIGHTPADDING", (0, 0), (-1, -1), 16),
            ]
        )
    )
    return badge


# ── PDF image from base64 ─────────────────────────────────────────────────────
def pdf_image_from_base64(
    value: str | None,
    max_width: float = 2.8 * inch,
    max_height: float = 2.3 * inch,
) -> Image | None:
    """Decode a base64 image string into a ReportLab Image flowable."""
    if not value or not isinstance(value, str):
        return None
    try:
        from io import BytesIO as _BytesIO

        import base64 as _b64

        from PIL import Image as PILImage

        payload = value.split(",", 1)[1] if value.strip().startswith("data:") and "," in value else value
        raw = _b64.b64decode(payload)
        stream = _BytesIO(raw)
        with PILImage.open(stream) as pil:
            if pil.mode not in {"RGB", "L"}:
                pil = pil.convert("RGB")
            w, h = pil.size
            scale = min(max_width / max(w, 1), max_height / max(h, 1), 1.0)
            out = _BytesIO()
            pil.save(out, format="JPEG", quality=88)
            out.seek(0)
            return Image(out, width=w * scale, height=h * scale)
    except Exception:
        return None


# ── Shared style factory ──────────────────────────────────────────────────────
def build_styles() -> Any:
    """Return a stylesheet with all shared OrthoAssist report styles."""
    base = getSampleStyleSheet()

    defs = [
        ParagraphStyle("ReportTitle", parent=base["Title"],
                       fontSize=17, spaceAfter=4, alignment=TA_LEFT,
                       fontName="Helvetica-Bold", textColor=NAVY),
        ParagraphStyle("ReportSubtitle", parent=base["Normal"],
                       fontSize=9, spaceAfter=2, alignment=TA_LEFT,
                       fontName="Helvetica", textColor=SLATE),
        ParagraphStyle("SectionHeader", parent=base["Normal"],
                       fontSize=11, spaceAfter=5, spaceBefore=12,
                       fontName="Helvetica-Bold", textColor=MID_BLUE),
        ParagraphStyle("FieldLabel", parent=base["Normal"],
                       fontSize=9, fontName="Helvetica-Bold", textColor=NAVY),
        ParagraphStyle("FieldValue", parent=base["Normal"],
                       fontSize=9.5, fontName="Helvetica", leading=13),
        ParagraphStyle("Body", parent=base["Normal"],
                       fontSize=9.5, leading=14, spaceAfter=5, fontName="Helvetica"),
        ParagraphStyle("BodyBold", parent=base["Normal"],
                       fontSize=9.5, leading=14, fontName="Helvetica-Bold"),
        ParagraphStyle("Small", parent=base["Normal"],
                       fontSize=8.5, leading=12, textColor=SLATE, fontName="Helvetica"),
        ParagraphStyle("Disclaimer", parent=base["Normal"],
                       fontSize=8, leading=11, textColor=SLATE,
                       fontName="Helvetica-Oblique"),
        ParagraphStyle("BadgeText", parent=base["Normal"],
                       fontSize=11, fontName="Helvetica-Bold", alignment=TA_CENTER),
        ParagraphStyle("FooterText", parent=base["Normal"],
                       fontSize=7.5, textColor=SLATE, fontName="Helvetica",
                       alignment=TA_CENTER),
        ParagraphStyle("Centered", parent=base["Normal"],
                       fontSize=9.5, alignment=TA_CENTER, fontName="Helvetica"),
        ParagraphStyle("RightAlign", parent=base["Normal"],
                       fontSize=8.5, alignment=TA_RIGHT, textColor=SLATE,
                       fontName="Helvetica"),
        ParagraphStyle("Detection", parent=base["Normal"],
                       fontSize=9, leading=13, fontName="Helvetica",
                       leftIndent=10),
    ]
    for style in defs:
        try:
            base.add(style)
        except KeyError:
            pass  # already registered (hot-reload safety)
    return base


# ── Branded page header (logo + title + divider) ─────────────────────────────
def build_branded_header(report_type: str, report_id: str, styles: Any) -> list:
    """Render the top-of-page logo + title block."""
    logo = get_logo()
    generated_at = datetime.now(UTC).strftime("%d %b %Y  %H:%M UTC")

    if logo:
        header_table = Table(
            [[logo, Paragraph("<b>OrthoAssist</b>", styles["ReportTitle"]),
              Paragraph(f"<font size=7.5>{generated_at}</font>", styles["RightAlign"])]],
            colWidths=[0.6 * inch, 4.6 * inch, 2.0 * inch],
        )
        header_table.setStyle(
            TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ])
        )
    else:
        header_table = Table(
            [[Paragraph("<b>OrthoAssist</b>", styles["ReportTitle"]),
              Paragraph(f"<font size=7.5>{generated_at}</font>", styles["RightAlign"])]],
            colWidths=[5.2 * inch, 2.0 * inch],
        )
        header_table.setStyle(
            TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 0)])
        )

    elements: list = [
        header_table,
        Paragraph(f"AI-Assisted Orthopedic {report_type}", styles["ReportSubtitle"]),
        Spacer(1, 4),
        HRFlowable(width="100%", thickness=2, color=TEAL, spaceAfter=6),
        Paragraph(
            f"<font size=8><b>Report ID:</b> {report_id}</font>",
            styles["Small"],
        ),
        Spacer(1, 8),
    ]
    return elements


# ── Info grid table helper ────────────────────────────────────────────────────
def info_grid(rows: list[list[str]], col_widths: list[float] | None = None) -> Table:
    """Two-column key-value grid with OrthoAssist styling."""
    col_widths = col_widths or [1.5 * inch, 2.2 * inch, 1.5 * inch, 2.0 * inch]
    t = Table(rows, colWidths=col_widths)
    t.setStyle(
        TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
            ("TEXTCOLOR", (0, 0), (0, -1), NAVY),
            ("TEXTCOLOR", (2, 0), (2, -1), NAVY),
            ("BACKGROUND", (0, 0), (-1, -1), LIGHT_BLUE),
            ("GRID", (0, 0), (-1, -1), 0.5, BORDER),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ])
    )
    return t


# ── Section header with underline ─────────────────────────────────────────────
def section_heading(title: str, styles: Any, number: str = "") -> list:
    label = f"{number}. {title}" if number else title
    return [
        Paragraph(label, styles["SectionHeader"]),
        HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceAfter=4),
    ]


# ── Legal disclaimer block ────────────────────────────────────────────────────
DISCLAIMER_TEXT = (
    "This report is generated by OrthoAssist, an AI-assisted clinical decision support tool. "
    "It is intended for preliminary triage and informational purposes only. "
    "It does not constitute a definitive medical diagnosis, and must be reviewed and validated "
    "by a qualified, licensed clinician before any clinical decisions are made. "
    "OrthoAssist assumes no liability for actions taken solely on the basis of this report."
)
