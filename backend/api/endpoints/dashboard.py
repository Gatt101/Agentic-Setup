from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from loguru import logger

from services.patient_store import patient_store

router = APIRouter(tags=["dashboard"])

TARGET_TURNAROUND_HOURS = 6.0

TRIAGE_COLORS: dict[str, str] = {
    "AMBER": "#d99525",
    "RED": "#4f5d95",
    "GREEN": "#6b8b73",
}


def _to_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, str) and value.strip():
        text = value.strip()
        if text.endswith("Z"):
            text = f"{text[:-1]}+00:00"
        try:
            parsed = datetime.fromisoformat(text)
            return parsed.astimezone(UTC) if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        except ValueError:
            return None
    return None


def _severity_from_value(value: object) -> str:
    raw = str(value or "").strip().upper()
    if raw in {"RED", "HIGH", "URGENT", "EMERGENCY"}:
        return "RED"
    if raw in {"AMBER", "YELLOW", "ORANGE", "MEDIUM", "MODERATE"}:
        return "AMBER"
    return "GREEN"


def _analysis_severity(analysis: dict[str, Any]) -> str:
    triage = analysis.get("triage")
    if isinstance(triage, dict):
        return _severity_from_value(triage.get("level") or triage.get("triage_level"))
    return "GREEN"


def _recent_month_starts(reference_time: datetime, count: int) -> list[datetime]:
    current = datetime(reference_time.year, reference_time.month, 1, tzinfo=UTC)
    months: list[datetime] = []
    for offset in range(count - 1, -1, -1):
        month = current.month - offset
        year = current.year
        while month <= 0:
            month += 12
            year -= 1
        months.append(datetime(year, month, 1, tzinfo=UTC))
    return months


def _format_vs_previous(current: int, previous: int) -> str:
    if previous <= 0:
        if current <= 0:
            return "No change vs last month"
        return f"+{current} new vs last month"
    delta_pct = ((current - previous) / previous) * 100
    sign = "+" if delta_pct >= 0 else ""
    return f"{sign}{delta_pct:.0f}% vs last month"


@router.get("/dashboard/doctor/overview")
async def get_doctor_dashboard_overview(
    actor_id: str = Query(..., description="Clerk user ID for doctor"),
    actor_role: str = Query("doctor", description="Expected role: doctor"),
) -> dict[str, Any]:
    role = actor_role.strip().lower()
    if role != "doctor":
        raise HTTPException(status_code=400, detail="actor_role must be 'doctor'.")

    now = datetime.now(UTC)
    month_starts = _recent_month_starts(now, count=6)
    month_keys = [f"{m.year}-{m.month:02d}" for m in month_starts]

    monthly_cases_map: dict[str, dict[str, Any]] = {
        key: {"month": month.strftime("%b"), "total": 0, "critical": 0}
        for key, month in zip(month_keys, month_starts, strict=True)
    }

    triage_counts: dict[str, int] = {"RED": 0, "AMBER": 0, "GREEN": 0}
    pending_reports_count = 0
    turnaround_by_week: list[list[float]] = [[], [], [], []]  # 0=current week, 3=oldest
    turnaround_all: list[float] = []
    analysis_timestamps_by_patient: dict[str, list[datetime]] = {}
    total_analyses = 0

    try:
        patients = await patient_store.list_by_doctor(actor_id, include_analyses=True)
        reports = await patient_store.list_reports_by_doctor(actor_id)
    except RuntimeError as exc:
        logger.warning("doctor dashboard overview unavailable (mongo): {}", exc)
        return {
            "alerts": [
                "Live data unavailable: MongoDB is not configured.",
                "Switch to MOCK mode or configure backend database connectivity.",
            ],
            "monthlyCases": [value for value in monthly_cases_map.values()],
            "reportTurnaround": [
                {"week": "W1", "avgHours": 0.0},
                {"week": "W2", "avgHours": 0.0},
                {"week": "W3", "avgHours": 0.0},
                {"week": "W4", "avgHours": 0.0},
            ],
            "summary": [
                {"label": "Cases Reviewed", "value": "0", "change": "No change vs last month"},
                {"label": "Critical Findings", "value": "0", "change": "No change vs last month"},
                {"label": "Reports In Progress", "value": "0", "change": "0 pending"},
                {"label": "Avg Turnaround", "value": "0.0h", "change": "Insufficient data"},
            ],
            "triageDistribution": [
                {"level": "AMBER", "count": 0, "color": TRIAGE_COLORS["AMBER"]},
                {"level": "RED", "count": 0, "color": TRIAGE_COLORS["RED"]},
                {"level": "GREEN", "count": 0, "color": TRIAGE_COLORS["GREEN"]},
            ],
        }

    for patient in patients:
        patient_id = str(patient.get("patient_id") or "")
        analyses_raw = patient.get("analyses")
        analyses = analyses_raw if isinstance(analyses_raw, list) else []

        timestamps: list[datetime] = []
        for analysis_raw in analyses:
            if not isinstance(analysis_raw, dict):
                continue
            analysis_ts = _to_datetime(analysis_raw.get("created_at"))
            if analysis_ts:
                timestamps.append(analysis_ts)
                month_key = f"{analysis_ts.year}-{analysis_ts.month:02d}"
                if month_key in monthly_cases_map:
                    monthly_cases_map[month_key]["total"] += 1
                    if _analysis_severity(analysis_raw) == "RED":
                        monthly_cases_map[month_key]["critical"] += 1
            total_analyses += 1

        timestamps.sort()
        if patient_id and timestamps:
            analysis_timestamps_by_patient[patient_id] = timestamps

    if reports:
        # Prefer report-severity distribution when reports exist.
        triage_counts = {"RED": 0, "AMBER": 0, "GREEN": 0}
    use_reports_for_monthly = total_analyses == 0

    for report in reports:
        severity = _severity_from_value(report.get("severity"))
        triage_counts[severity] += 1

        status = str(report.get("status") or "").strip().lower()
        if status and status != "finalized":
            pending_reports_count += 1

        report_ts = _to_datetime(report.get("created_at"))
        if not report_ts:
            continue

        month_key = f"{report_ts.year}-{report_ts.month:02d}"
        if use_reports_for_monthly and month_key in monthly_cases_map:
            monthly_cases_map[month_key]["total"] += 1
            if severity == "RED":
                monthly_cases_map[month_key]["critical"] += 1

        patient_id = str(report.get("patient_id") or "")
        analysis_times = analysis_timestamps_by_patient.get(patient_id, [])
        source_ts = next((ts for ts in reversed(analysis_times) if ts <= report_ts), None)
        if not source_ts:
            continue

        delta_hours = (report_ts - source_ts).total_seconds() / 3600
        if delta_hours < 0:
            continue

        turnaround_all.append(delta_hours)
        age_days = (now - report_ts).days
        if 0 <= age_days < 28:
            week_index = age_days // 7
            if 0 <= week_index < 4:
                turnaround_by_week[week_index].append(delta_hours)

    if not reports:
        # Fall back to analysis-based triage when no reports exist yet.
        for patient in patients:
            analyses_raw = patient.get("analyses")
            analyses = analyses_raw if isinstance(analyses_raw, list) else []
            if not analyses:
                continue
            latest = analyses[-1] if isinstance(analyses[-1], dict) else None
            if latest:
                triage_counts[_analysis_severity(latest)] += 1

    monthly_cases = [monthly_cases_map[key] for key in month_keys]
    current_month_key = month_keys[-1]
    previous_month_key = month_keys[-2] if len(month_keys) > 1 else month_keys[-1]

    cases_reviewed = total_analyses if total_analyses > 0 else len(reports)
    critical_findings = triage_counts["RED"]
    average_turnaround = (
        sum(turnaround_all) / len(turnaround_all) if turnaround_all else 0.0
    )

    report_turnaround: list[dict[str, Any]] = []
    for order, source_index in enumerate((3, 2, 1, 0), start=1):
        values = turnaround_by_week[source_index]
        avg_value = round(sum(values) / len(values), 1) if values else 0.0
        report_turnaround.append({"week": f"W{order}", "avgHours": avg_value})

    if average_turnaround <= 0:
        turnaround_change = "Insufficient data"
    else:
        delta_vs_target = average_turnaround - TARGET_TURNAROUND_HOURS
        if delta_vs_target > 0:
            turnaround_change = f"+{delta_vs_target:.1f}h above target"
        elif delta_vs_target < 0:
            turnaround_change = f"-{abs(delta_vs_target):.1f}h below target"
        else:
            turnaround_change = "At target"

    summary = [
        {
            "label": "Cases Reviewed",
            "value": str(cases_reviewed),
            "change": _format_vs_previous(
                monthly_cases_map[current_month_key]["total"],
                monthly_cases_map[previous_month_key]["total"],
            ),
        },
        {
            "label": "Critical Findings",
            "value": str(critical_findings),
            "change": _format_vs_previous(
                monthly_cases_map[current_month_key]["critical"],
                monthly_cases_map[previous_month_key]["critical"],
            ),
        },
        {
            "label": "Reports In Progress",
            "value": str(pending_reports_count),
            "change": (
                f"{pending_reports_count} pending"
                if pending_reports_count
                else "All reports finalized"
            ),
        },
        {
            "label": "Avg Turnaround",
            "value": f"{average_turnaround:.1f}h",
            "change": turnaround_change,
        },
    ]

    alerts: list[str] = []
    if critical_findings:
        alerts.append(
            f"{critical_findings} red-triage cases require immediate escalation review."
        )
    if pending_reports_count:
        alerts.append(
            f"{pending_reports_count} reports are still in progress and pending sign-off."
        )
    if average_turnaround > 0:
        if average_turnaround > TARGET_TURNAROUND_HOURS:
            alerts.append(
                f"Average report turnaround is {average_turnaround:.1f}h, above the {TARGET_TURNAROUND_HOURS:.0f}h target."
            )
        else:
            alerts.append(
                f"Average report turnaround is {average_turnaround:.1f}h, within the {TARGET_TURNAROUND_HOURS:.0f}h target."
            )
    if not reports and not total_analyses:
        alerts.append("No case activity found yet for this doctor account.")
    if not alerts:
        alerts.append("No active operational alerts from live data.")

    return {
        "alerts": alerts,
        "monthlyCases": monthly_cases,
        "reportTurnaround": report_turnaround,
        "summary": summary,
        "triageDistribution": [
            {"level": "AMBER", "count": triage_counts["AMBER"], "color": TRIAGE_COLORS["AMBER"]},
            {"level": "RED", "count": triage_counts["RED"], "color": TRIAGE_COLORS["RED"]},
            {"level": "GREEN", "count": triage_counts["GREEN"], "color": TRIAGE_COLORS["GREEN"]},
        ],
    }
