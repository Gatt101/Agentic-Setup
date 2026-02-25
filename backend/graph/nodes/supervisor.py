from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from loguru import logger

from graph.state import AgentState
from services.groq_llm import get_supervisor_llm
from services.chat_store import chat_store
from tools import ALL_TOOLS

SUPERVISOR_PROMPT = """You are an orthopedic AI clinical assistant.
You must reason step-by-step and use tools when required.

PIPELINE RULES:
1. If an image is provided, first call vision_detect_body_part.
2. After body part detection, choose vision_detect_hand_fracture or vision_detect_leg_fracture.
3. If detection confidence is low, request better image quality.
4. clinical_generate_diagnosis requires detections.
5. clinical_assess_triage requires diagnosis.
6. If triage is RED or AMBER, hospital_find_nearby_hospitals is required.
7. For text-only questions, use knowledge_* tools.
8. Generate report PDFs ONLY when user explicitly asks for report/document/PDF.
9. Never call the same tool repeatedly with identical context.
10. Keep final clinical response concise and medically safe.
11. CRITICAL: Do NOT ask the user for information obtainable from tools.
12. CRITICAL: NEVER ask for patient name/age/gender UNLESS the user has explicitly asked for a report or PDF IN THEIR CURRENT MESSAGE. Analysis requests do NOT need patient info.
13. CRITICAL: When the vision+clinical pipeline is complete (diagnosis and triage both present) and the user has NOT asked for a report, respond with a clear summary of the findings. Do NOT ask for any extra information.

=== REPORT GATE (ONLY applies when user explicitly says \"report\", \"PDF\", or \"document\") ===
If PIPELINE STATUS shows \"Report patient info needed\" AND the user demanded a report THIS turn:
  Ask in ONE message: \"Before I generate your report, I need a few details:\n- Full name\n- Age\n- Gender\nPlease share these.\"
  Do NOT call any report tool until all of name, age, and gender are confirmed.

=== REPORT ROUTING ===
  actor_role = patient \u2192 report_generate_patient_pdf
  actor_role = doctor \u2192 report_generate_clinician_simple_pdf
  Always inject doctor_name from actor_name into metadata when actor_role is doctor.
"""

NON_VISION_TOOLS = [tool for tool in ALL_TOOLS if not tool.name.startswith("vision_")]


def _build_pipeline_context(state: AgentState) -> str:
    lines: list[str] = []

    actor_role = str(state.get("actor_role") or "patient").lower()
    actor_name = str(state.get("actor_name") or "")
    lines.append(
        f"Actor role: {actor_role}" + (f" | Actor name: {actor_name}" if actor_name else "")
    )

    if state.get("image_data"):
        lines.append("Image: available")

    if state.get("body_part"):
        lines.append(f"Body part: {state['body_part']}")

    detections = state.get("detections")
    if isinstance(detections, list):
        lines.append(f"Detections: {len(detections)} finding(s)")
    else:
        lines.append("Detections: NOT YET")

    diagnosis = state.get("diagnosis")
    if isinstance(diagnosis, dict):
        primary = diagnosis.get("primary_diagnosis") or diagnosis.get("diagnosis") or "?"
        lines.append(f"Diagnosis: {primary}")
    else:
        lines.append("Diagnosis: NOT YET")

    triage = state.get("triage_result")
    if isinstance(triage, dict):
        level = triage.get("level") or triage.get("triage_level") or "?"
        lines.append(f"Triage: {level}")
    else:
        lines.append("Triage: NOT YET")

    # Patient info — only surface the "needed" label during an explicit report request
    pi = state.get("patient_info") or {}
    missing_fields = _missing_patient_fields(state)
    report_stage = bool(state.get("pending_report_actor_role")) or _report_requested(state)
    if missing_fields and report_stage:
        lines.append(f"Report patient info needed: {', '.join(missing_fields)}")
    elif missing_fields:
        lines.append("Patient info: pending")
    else:
        name = pi.get("name") or ""
        lines.append(f"Patient info: complete (name={name})")

    if state.get("report_url"):
        lines.append(f"Report URL: {state['report_url']}")

    tools_made = state.get("tool_calls_made", [])
    if tools_made:
        lines.append("Tools used: " + ", ".join(tools_made))

    return "\n".join(lines)


def _patient_info_complete(state: AgentState) -> bool:
    """Return True if patient name, age, and gender are all present."""
    return len(_missing_patient_fields(state)) == 0


def _missing_patient_fields(state: AgentState) -> list[str]:
    """Return missing intake fields required for report generation."""
    pi = state.get("patient_info") or {}
    missing: list[str] = []

    name_ok = bool(str(pi.get("name") or "").strip())
    age_ok = isinstance(pi.get("age"), int) or bool(str(pi.get("age") or "").strip())
    gender_ok = bool(str(pi.get("gender") or "").strip())

    if not name_ok:
        missing.append("name")
    if not age_ok:
        missing.append("age")
    if not gender_ok:
        missing.append("gender")
    return missing


def _doctor_report_type_clear(state: AgentState) -> str | None:
    """Always use the summary/simple report for doctors — full clinical report is disabled."""
    return "report_generate_clinician_simple_pdf"


def _tool_to_agent(tool_name: str | None) -> str | None:
    if not tool_name:
        return None
    namespace = tool_name.split("_", 1)[0]
    mapping = {
        "vision": "vision_agent",
        "clinical": "clinical_agent",
        "knowledge": "knowledge_agent",
        "report": "report_agent",
        "hospital": "hospital_agent",
    }
    return mapping.get(namespace)


def _report_requested(state: AgentState) -> bool:
    text = str(state.get("user_message") or "").lower().strip()
    report_keywords = ("report", "pdf", "document")
    type_keywords = ("summary", "quick", "simple", "simplified", "full", "clinical",
                     "detailed", "depth", "complete", "comprehensive")
    if any(keyword in text for keyword in report_keywords):
        return True
    # Also detect report-type responses when clinical pipeline is already done
    diagnosis = state.get("diagnosis")
    triage = state.get("triage_result")
    if diagnosis and triage and not state.get("report_url"):
        if any(keyword in text for keyword in type_keywords):
            return True
        if text in ("1", "2"):
            return True
    return False


def _forced_tool_call(state: AgentState) -> dict | None:
    body_part = state.get("body_part")
    detections = state.get("detections")
    diagnosis = state.get("diagnosis")
    triage = state.get("triage_result")
    report_url = state.get("report_url")

    if not body_part and state.get("image_data"):
        return {"name": "vision_detect_body_part", "args": {}}

    if body_part in {"hand", "leg"} and detections is None:
        name = "vision_detect_hand_fracture" if body_part == "hand" else "vision_detect_leg_fracture"
        return {"name": name, "args": {}}

    if detections is not None and not diagnosis:
        return {"name": "clinical_generate_diagnosis", "args": {}}

    if diagnosis and not triage:
        return {"name": "clinical_assess_triage", "args": {}}

    if diagnosis and triage and not report_url:
        # Check if report was explicitly requested this turn OR was pending from a previous gated turn
        pending_role = state.get("pending_report_actor_role")
        report_this_turn = _report_requested(state)

        if report_this_turn or pending_role:
            actor_role = str(state.get("actor_role") or pending_role or "patient").lower()

            # Guard: don't retry a report tool that already ran (prevents infinite loops)
            report_tools_attempted = [
                t for t in state.get("tool_calls_made", [])
                if t in {"report_generate_patient_pdf", "report_generate_clinician_pdf", "report_generate_clinician_simple_pdf"}
            ]
            if report_tools_attempted:
                return None  # already attempted, let graph route to response_builder

            # Gate 1: patient info must be complete
            if not _patient_info_complete(state):
                return None  # supervisor LLM will ask for missing fields

            # Gate 2 (doctor): must have chosen report type
            if actor_role == "doctor":
                tool_name = _doctor_report_type_clear(state)
                if not tool_name:
                    return None  # supervisor LLM will ask for type choice
                return {"name": tool_name, "args": {}}

            return {"name": "report_generate_patient_pdf", "args": {}}

    return None


async def supervisor_node(state: AgentState) -> dict:
    has_image_data = bool(state.get("image_data"))
    toolset = ALL_TOOLS if has_image_data else NON_VISION_TOOLS
    llm = get_supervisor_llm().bind_tools(toolset)
    session_id = state.get("session_id", "unknown")
    iteration = state.get("iteration_count", 0)

    messages = list(state.get("messages", []))
    if not messages and state.get("user_message"):
        messages = [HumanMessage(content=state["user_message"])]

    # Truncate history to last 10 messages to avoid blowing up TPM limits.
    # _build_pipeline_context already injects all structured clinical state
    # (diagnosis, triage, detections, etc.) as a SystemMessage so the LLM
    # does NOT need the verbose old tool-result blobs.
    MAX_HISTORY = 10
    if len(messages) > MAX_HISTORY:
        messages = messages[-MAX_HISTORY:]

    # Strip all AIMessages-with-tool-calls and ToolMessages from history.
    # These can carry tool_call IDs exceeding OpenAI's 40-char limit, and they
    # add no value since PIPELINE STATUS already contains all structured state.
    # Only keep plain human/assistant conversational messages.
    messages = [
        msg for msg in messages
        if not (isinstance(msg, AIMessage) and getattr(msg, "tool_calls", None))
        and not isinstance(msg, ToolMessage)
    ]

    safety_context = SystemMessage(
        content=(
            "Already-called tools in this run: "
            + ", ".join(state.get("tool_calls_made", []))
            if state.get("tool_calls_made")
            else "No tools have been called yet in this run."
        )
    )
    image_context = SystemMessage(
        content=(
            "Valid image data is available for vision analysis."
            if has_image_data
            else "No valid image data is available in this turn. Do not call any vision_* tools."
        )
    )

    pipeline_context = SystemMessage(content="PIPELINE STATUS:\n" + _build_pipeline_context(state))
    prompt_messages = [SystemMessage(content=SUPERVISOR_PROMPT), safety_context, image_context, pipeline_context, *messages]

    forced_call = _forced_tool_call(state)
    if forced_call:
        # OpenAI hard limit: tool_call id must be <= 40 chars
        raw_id = f"fc_{iteration}_{forced_call['name']}"
        forced_id = raw_id[:40]
        response = AIMessage(
            content="",
            tool_calls=[
                {
                    "id": forced_id,
                    "type": "tool_call",
                    "name": forced_call["name"],
                    "args": forced_call["args"],
                }
            ],
        )
        return {
            "messages": [response],
            "iteration_count": state.get("iteration_count", 0) + 1,
            "tool_calls_made": [*state.get("tool_calls_made", []), forced_call["name"]],
            "agent_trace": [*state.get("agent_trace", []), {"type": "supervisor_decision", "iteration": iteration, "active_agent": _tool_to_agent(forced_call["name"]) or "none", "tool_calls": [forced_call["name"]]}],
            "current_agent": _tool_to_agent(forced_call["name"]),
            "error": None,
            # Clear the pending flag once we actually fire the report tool
            "pending_report_actor_role": None,
        }

    # ── Short-circuit: if report was already generated, skip LLM entirely ──────
    _REPORT_TOOLS = {
        "report_generate_patient_pdf",
        "report_generate_clinician_pdf",
        "report_generate_clinician_simple_pdf",
    }
    _report_already_done = (
        bool(state.get("report_url"))
        and any(t in _REPORT_TOOLS for t in state.get("tool_calls_made", []))
    )
    if _report_already_done:
        logger.info("session={} report already generated, skipping LLM", session_id)
        response = AIMessage(content="Your report has been generated successfully.")
        called: list[str] = []
        return {
            "messages": [response],
            "iteration_count": state.get("iteration_count", 0) + 1,
            "tool_calls_made": state.get("tool_calls_made", []),
            "agent_trace": [*state.get("agent_trace", []), {"type": "supervisor_decision", "iteration": iteration, "active_agent": "none", "tool_calls": []}],
            "current_agent": None,
            "error": None,
            "pending_report_actor_role": None,
        }

    # ── Short-circuit: full analysis pipeline done, no report requested ──────
    # Skip the LLM entirely — it has no image and no tools to call at this point,
    # so it generates nonsense like "Please upload an image".  The response_builder
    # node will produce the rich clinical summary directly from state.
    _pipeline_complete = bool(state.get("diagnosis")) and bool(state.get("triage_result"))
    _report_needed = _report_requested(state) or bool(state.get("pending_report_actor_role"))
    if _pipeline_complete and not _report_needed and not _report_already_done:
        logger.info("session={} analysis pipeline complete, routing directly to response_builder", session_id)
        return {
            "messages": [AIMessage(content="")],  # empty — response_builder uses structured state
            "iteration_count": state.get("iteration_count", 0) + 1,
            "tool_calls_made": state.get("tool_calls_made", []),
            "agent_trace": [*state.get("agent_trace", []), {"type": "supervisor_decision", "iteration": iteration, "active_agent": "none", "tool_calls": []}],
            "current_agent": None,
            "error": None,
            "pending_report_actor_role": state.get("pending_report_actor_role"),
        }

    else:
        response = await llm.ainvoke(prompt_messages)
        # ── Intercept: prevent LLM from calling a report tool when gates not met ──
        _REPORT_TOOLS_INTERCEPT = _REPORT_TOOLS  # same set, already defined above
        llm_tool_calls = getattr(response, "tool_calls", []) or []
        if any(tc.get("name") in _REPORT_TOOLS_INTERCEPT for tc in llm_tool_calls):
            actor_role = str(state.get("actor_role") or "patient").lower()
            missing_fields = _missing_patient_fields(state)
            # Block retry: if any report tool already ran (success or fail), don't let LLM call it again.
            _already_ran_report = any(t in _REPORT_TOOLS_INTERCEPT for t in state.get("tool_calls_made", []))
            if _already_ran_report:
                response = AIMessage(
                    content=(
                        "I attempted to generate the report but encountered a processing issue. "
                        "The analysis data may be incomplete — please retry by re-uploading the X-ray "
                        "and running a fresh analysis, then request the report again."
                    )
                )
            elif missing_fields and actor_role == "patient":
                missing_fields_list = "name" if "name" in missing_fields else ""
                if "age" in missing_fields: missing_fields_list += (", age" if missing_fields_list else "age")
                if "gender" in missing_fields: missing_fields_list += (", gender" if missing_fields_list else "gender")
                response = AIMessage(
                    content=(
                        f"Before I generate your report, I need a few details:\n"
                        f"Please share your **{missing_fields_list}** so I can personalise the report."
                    )
                )
            elif missing_fields and actor_role == "doctor":
                response = AIMessage(
                    content=(
                        f"Before generating the report, please provide the patient\u2019s "
                        f"**{', '.join(missing_fields)}** so the report is complete."
                    )
                )
            # (Full clinical report option removed — doctor always gets summary report)
        # ── Set pending_report flag when gating so next turn auto-triggers report ──
        _pending_flag_update: str | None = state.get("pending_report_actor_role")
        _gated_response = getattr(response, "tool_calls", None) is None or len(getattr(response, "tool_calls", [])) == 0
        if _gated_response and _report_requested(state) and state.get("diagnosis") and state.get("triage_result"):
            # We were asked for a report but gated — remember this for the next turn
            _pending_flag_update = str(state.get("actor_role") or "patient").lower()
        elif state.get("report_url"):
            _pending_flag_update = None  # report done, clear flag
    called = [call.get("name", "") for call in getattr(response, "tool_calls", []) if call.get("name")]
    active_agent = _tool_to_agent(called[-1]) if called else state.get("current_agent")

    logger.info(
        "session={} iteration={} active_agent={} tool_calls={}",
        session_id,
        iteration,
        active_agent or "none",
        ",".join(called) if called else "none",
    )

    trace_event = {
        "type": "supervisor_decision",
        "iteration": iteration,
        "active_agent": active_agent or "none",
        "tool_calls": called,
    }
    try:
        await chat_store.append_trace_event(session_id, trace_event)
    except Exception:
        pass

    return {
        "messages": [response],
        "iteration_count": state.get("iteration_count", 0) + 1,
        "tool_calls_made": [*state.get("tool_calls_made", []), *called],
        "agent_trace": [*state.get("agent_trace", []), trace_event],
        "current_agent": active_agent,
        "error": None,
        "pending_report_actor_role": _pending_flag_update,
    }
