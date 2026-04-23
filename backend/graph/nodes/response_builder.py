from __future__ import annotations

from langchain_core.messages import AIMessage
from loguru import logger

from graph.state import AgentState


def _report_requested(state: AgentState) -> bool:
    text = str(state.get("user_message") or "").lower()
    return any(keyword in text for keyword in ("report", "pdf", "document"))


# Keywords that indicate the LLM returned a useless "please upload" type message
# instead of actual analysis — we discard these when structured data is available.
_STALE_LLM_PHRASES = (
    "please upload",
    "upload the image",
    "upload an image",
    "upload a scan",
    "provide an image",
    "share the image",
    "no image",
    "i need an image",
    "i need the image",
)

_REPORT_TOOLS = {
    "report_generate_patient_pdf",
    "report_generate_clinician_pdf",
    "report_generate_clinician_simple_pdf",
}
_ANALYSIS_TOOLS = {
    "clinical_generate_diagnosis",
    "clinical_assess_triage",
}


def _last_non_tool_ai_message(state: AgentState) -> str | None:
    diagnosis = state.get("diagnosis")
    triage = state.get("triage_result")
    pipeline_has_results = bool(diagnosis) and bool(triage)

    for message in reversed(state.get("messages", [])):
        if isinstance(message, AIMessage) and not getattr(message, "tool_calls", None):
            content = message.content
            if isinstance(content, str):
                text = content.strip()
            elif isinstance(content, list):
                parts = [part.get("text", "") for part in content if isinstance(part, dict)]
                text = " ".join(part for part in parts if part).strip()
            else:
                continue

            if not text:
                continue

            # If pipeline already produced structured results, discard stale LLM
            # messages that ask the user to upload an image — they are artifacts
            # from the supervisor running one extra iteration after the pipeline.
            if pipeline_has_results and any(phrase in text.lower() for phrase in _STALE_LLM_PHRASES):
                logger.debug("response_builder: discarding stale LLM message: {:.80}", text)
                continue

            return text
    return None


def _severity_emoji(severity: str) -> str:
    s = severity.lower()
    if s in ("high", "severe", "critical"):
        return "🔴"
    if s in ("moderate", "medium"):
        return "🟡"
    return "🟢"


def _triage_label(level: str) -> str:
    l = level.upper()
    if l == "RED":
        return "🔴 RED — Immediate attention required"
    if l == "AMBER":
        return "🟡 AMBER — Urgent — seek care within 24 hours"
    if l == "GREEN":
        return "🟢 GREEN — Routine — arrange follow-up"
    return level


async def response_builder_node(state: AgentState) -> dict:
    if state.get("final_response"):
        return {}

    diagnosis = state.get("diagnosis")
    triage = state.get("triage_result")
    hospitals = state.get("hospitals")
    report_url = state.get("report_url")
    tool_calls_made = [str(name) for name in (state.get("tool_calls_made") or [])]
    report_generated_this_turn = bool(report_url) and any(name in _REPORT_TOOLS for name in tool_calls_made)
    analysis_generated_this_turn = any(name in _ANALYSIS_TOOLS for name in tool_calls_made)
    report_requested = _report_requested(state)
    patient_info = state.get("patient_info") or {}
    patient_info_complete = (
        bool(str(patient_info.get("name") or "").strip())
        and patient_info.get("age") is not None
        and bool(str(patient_info.get("gender") or "").strip())
    )

    # If report generation happened using prior analysis, don't repeat analysis blocks.
    if report_generated_this_turn and not analysis_generated_this_turn:
        return {"final_response": "Your PDF report is ready. Use the download button below."}

    # If report already exists and user asks for it again, keep response concise.
    if report_url and report_requested and not analysis_generated_this_turn:
        return {"final_response": "Your report is already available. Use the download button below."}

    if report_requested and not (diagnosis and triage):
        if not state.get("image_data") and not state.get("volume_path"):
            return {
                "final_response": (
                    "I cannot generate the PDF yet. I have "
                    + ("your patient details, " if patient_info_complete else "partial patient details, ")
                    + "but I still need an X-ray analysis first. Upload the X-ray or ask me to analyze it, then ask for the report."
                )
            }
        if not diagnosis:
            return {
                "final_response": (
                    "I cannot generate the PDF yet because the clinical analysis is not complete. "
                    "I need to finish image analysis and diagnosis first."
                )
            }
        if not triage:
            return {
                "final_response": (
                    "I cannot generate the PDF yet because triage is still incomplete. "
                    "I need to finish the full analysis before creating the report."
                )
            }

    # If the full clinical pipeline ran, build a proper structured summary.
    # Do this BEFORE checking _last_non_tool_ai_message so a stale LLM message
    # (e.g. "Please upload an image") never overrides real analysis results.
    if diagnosis and triage:
        primary = (
            diagnosis.get("primary_diagnosis")
            or diagnosis.get("finding")
            or "Abnormality detected"
        )
        severity = str(diagnosis.get("severity") or "unknown").capitalize()
        icd = diagnosis.get("icd_code") or ""
        confidence = diagnosis.get("confidence") or diagnosis.get("ai_confidence")
        notes = diagnosis.get("notes") or diagnosis.get("clinical_notes") or ""
        differentials = diagnosis.get("differential_diagnoses") or diagnosis.get("differentials") or []
        triage_level = str(triage.get("level") or triage.get("triage_level") or "GREEN").upper()
        rationale = triage.get("rationale") or ""
        timeframe = triage.get("recommended_timeframe") or ""
        body_part = str(state.get("body_part") or "affected area").capitalize()
        detections = state.get("detections") or []

        lines = [
            f"## 🦴 AI Orthopedic Analysis — {body_part}",
            "",
            f"**Primary Finding:** {primary}  ",
            f"**Severity:** {_severity_emoji(severity)} {severity}"
            + (f"  |  **ICD-10:** `{icd}`" if icd else ""),
        ]
        if confidence is not None:
            try:
                lines.append(f"**AI Confidence:** {float(confidence):.0%}")
            except (ValueError, TypeError):
                pass
        if notes:
            lines += ["", f"**Clinical Notes:** {notes}"]
        if differentials:
            lines += ["", "**Differential Diagnoses:**"]
            for d in differentials:
                if isinstance(d, dict):
                    lines.append(f"- {d.get('diagnosis', d)} — probability: {d.get('probability', 'N/A')}")
                else:
                    lines.append(f"- {d}")
        lines += [
            "",
            f"## 🚨 Triage Assessment",
            f"**Level:** {_triage_label(triage_level)}",
        ]
        if rationale:
            lines.append(f"**Rationale:** {rationale}")
        if timeframe:
            lines.append(f"**Recommended Timeframe:** {timeframe}")
        if detections:
            lines += ["", f"**Detections:** {len(detections)} finding(s) identified by vision model."]
        if hospitals:
            lines += ["", f"**Nearby Hospitals:** {len(hospitals)} option(s) found near your location."]
        if report_url:
            lines += ["", f"**Report ready.** Use the download button below."]
        lines += [
            "",
            "---",
            "*⚠️ This AI analysis is for decision support only. Always confirm findings with a licensed clinician before treatment.*",
        ]
        if not _report_requested(state) and not report_url:
            lines += ["", "📄 *To generate a PDF report, just ask: \"Generate a report\".*"]

        # ── Care-plan agent outputs ──────────────────────────────────────────
        actor_role = str(state.get("actor_role") or "").lower()
        treatment_plan    = state.get("treatment_plan")
        rehabilitation_plan = state.get("rehabilitation_plan")
        patient_education = state.get("patient_education")
        appointment_schedule = state.get("appointment_schedule")

        is_doctor = actor_role == "doctor"
        is_patient = actor_role == "patient"

        # Treatment plan — doctors only
        if treatment_plan and (is_doctor or not is_patient):
            approach = str(treatment_plan.get("approach", "conservative")).capitalize()
            lines += ["", f"---", f"## 💊 Treatment Plan — {approach} Pathway"]
            for step in treatment_plan.get("immediate_steps", []):
                lines.append(f"- {step}")
            long_term = treatment_plan.get("long_term_plan", [])
            if long_term:
                lines += ["", "**Long-term:**"]
                for item in long_term:
                    lines.append(f"- {item}")
            meds = treatment_plan.get("medications", [])
            if meds:
                lines += ["", "**Medications:**"]
                for m in meds:
                    lines.append(f"- {m}")
            restrictions = treatment_plan.get("restrictions", [])
            if restrictions:
                lines += ["", "**Restrictions:**"]
                for r in restrictions:
                    lines.append(f"- {r}")

        # Rehabilitation plan — doctors only
        if rehabilitation_plan and (is_doctor or not is_patient):
            summary = rehabilitation_plan.get("summary", "")
            recovery_weeks = rehabilitation_plan.get("estimated_recovery_weeks", "")
            physio_freq = rehabilitation_plan.get("physiotherapy_frequency", "")
            lines += ["", "---", "## 🏃 Rehabilitation Plan"]
            if summary:
                lines.append(f"*{summary}*")
            if recovery_weeks:
                lines.append(f"**Estimated Recovery:** {recovery_weeks} weeks  |  **Physio:** {physio_freq}")
            phases = rehabilitation_plan.get("rehabilitation_phases", {})
            for phase_key in ("phase_1", "phase_2", "phase_3", "phase_4"):
                phase = phases.get(phase_key)
                if not phase:
                    continue
                lines.append(f"\n**Phase — Week {phase['weeks']}: {phase['label']}**")
                for act in phase.get("activities", []):
                    lines.append(f"  - {act}")
            precautions = rehabilitation_plan.get("special_precautions", [])
            if precautions:
                lines += ["", "**Precautions:**"]
                for p in precautions:
                    lines.append(f"- {p}")

        # Patient education — patients only
        if patient_education and (is_patient or not is_doctor):
            plain_summary = patient_education.get("plain_summary", "")
            age_note = patient_education.get("age_specific_note", "")
            lines += ["", "---", "## 📋 What This Means For You"]
            if plain_summary:
                lines.append(plain_summary)
            if age_note:
                lines += ["", f"*{age_note}*"]
            do_not = patient_education.get("do_not_list", [])
            if do_not:
                lines += ["", "**Important — Do NOT:**"]
                for item in do_not:
                    lines.append(f"- {item}")
            warnings = patient_education.get("warning_signs", [])
            if warnings:
                lines += ["", "**Seek urgent help if you notice:**"]
                for w in warnings:
                    lines.append(f"- {w}")
            reassurance = patient_education.get("reassurance", "")
            if reassurance:
                lines += ["", f"✅ {reassurance}"]

        # Appointment schedule — everyone
        if appointment_schedule:
            initial = appointment_schedule.get("initial_review", {})
            days = initial.get("days_from_now", "")
            note = initial.get("note", "")
            specialist = appointment_schedule.get("specialist_referral", "")
            physio_start = appointment_schedule.get("physiotherapy_start", "")
            milestones = appointment_schedule.get("follow_up_milestones", [])
            age_adj = appointment_schedule.get("age_specific_adjustment", "")
            lines += ["", "---", "## 📅 Follow-up Schedule"]
            if days:
                lines.append(f"**Next appointment in:** {days} day(s) — {note}")
            if specialist:
                lines.append(f"**Specialist referral:** {specialist}")
            if physio_start:
                lines.append(f"**Physiotherapy:** {physio_start}")
            if milestones:
                lines += ["", "**Milestones:**"]
                for m in milestones:
                    lines.append(f"- Week {m['week']}: {m['visit']}")
            if age_adj:
                lines += ["", f"⚠️ {age_adj}"]
            general = appointment_schedule.get("general_advice", "")
            if general:
                lines += ["", f"*{general}*"]
        # ────────────────────────────────────────────────────────────────────

        return {"final_response": "\n".join(lines)}

    # Fallback: use the last non-tool LLM message (e.g. for knowledge/text-only answers)
    ai_message = _last_non_tool_ai_message(state)
    if ai_message:
        return {"final_response": ai_message}

    # Final fallback — partial pipeline
    if diagnosis:
        primary = diagnosis.get("primary_diagnosis") or diagnosis.get("finding") or "N/A"
        severity = str(diagnosis.get("severity") or "N/A")
        resp = f"**Finding:** {primary} (severity: {severity}).\n\nTriage assessment is still in progress."
        resp += "\n\n*Please confirm with a licensed clinician.*"
        return {"final_response": resp}

    return {
        "final_response": (
            "I could not complete a full analysis from the provided data. "
            "Please share clearer details or a higher quality image."
        )
    }
