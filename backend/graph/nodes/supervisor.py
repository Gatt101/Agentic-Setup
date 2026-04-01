from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from loguru import logger

from graph.state import AgentState
from services.groq_llm import get_supervisor_llm
from services.chat_store import chat_store
from services.agent_learning import adaptive_supervisor
from services.probabilistic_reasoning import (
    confidence_estimator,
    probabilistic_reasoner,
    bayesian_updater
)
from tools import ALL_TOOLS

SUPERVISOR_PROMPT = """You are an autonomous orthopedic AI clinical assistant with enhanced decision-making capabilities.

CORE PRINCIPLES:
1. You are responsible for tool selection and decision-making - choose tools based on clinical reasoning.
2. Use your judgment to determine the optimal sequence of actions.
3. Consider clinical context, patient safety, and information completeness before acting.
4. Learn from pipeline state to make informed decisions about next steps.

CLINICAL WORKFLOW GUIDANCE:
1. Image Analysis: When X-ray images are provided, systematically analyze using vision tools.
2. Diagnosis: Formulate diagnoses based on detection findings and clinical reasoning.
3. Triage Assessment: Evaluate urgency and recommend appropriate care timelines.
4. Knowledge Integration: Use clinical knowledge tools to support decision-making when needed.
5. Hospital Coordination: For urgent cases (RED/AMBER triage), consider hospital resources.

AUTONOMOUS DECISION-MAKING:
- You have full autonomy to choose tools based on clinical context.
- Evaluate confidence levels from vision analysis before proceeding.
- Determine when additional information is needed vs. when current data is sufficient.
- Adjust your approach based on pipeline state and previous tool outcomes.

SAFETY AND COMPLIANCE:
- Always prioritize patient safety and clinical accuracy.
- Include appropriate disclaimers for AI-generated medical content.
- Never provide definitive treatment recommendations without clinical review.
- Request patient information (name/age/gender) ONLY when generating formal reports.

REPORT GENERATION (requires explicit user request):
- Only generate PDF reports when user explicitly asks for "report", "PDF", or "document"
- Ensure patient information is complete before report generation
- Match report type to user role (patient vs. clinician)
"""

NON_VISION_TOOLS = [tool for tool in ALL_TOOLS if not tool.name.startswith("vision_")]


def _build_learning_context(state: AgentState) -> str:
    """Build context from experience-based learning patterns."""
    try:
        current_state_dict = {
            "body_part": state.get("body_part"),
            "diagnosis_present": bool(state.get("diagnosis")),
            "triage_present": bool(state.get("triage_result")),
            "session_context": {
                "actor_role": state.get("actor_role"),
                "actor_name": state.get("actor_name")
            }
        }

        applicable_patterns = adaptive_supervisor.find_applicable_patterns(current_state_dict)

        if not applicable_patterns:
            return "No relevant learning patterns found for current state."

        context_lines = ["=== LEARNING INSIGHTS FROM EXPERIENCE ==="]
        for i, pattern in enumerate(applicable_patterns[:3], 1):  # Top 3 patterns
            context_lines.append(f"{i}. [{pattern['pattern_type'].upper()}] {pattern['recommendation']}")
            context_lines.append(f"   Confidence: {pattern['confidence']:.2f}")

        context_lines.append("Consider these patterns in your decision-making process.\n")
        return "\n".join(context_lines)

    except Exception as e:
        logger.warning("Failed to build learning context: {}", e)
        return "Learning insights temporarily unavailable."


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
    report_stage = _report_requested(state)
    if missing_fields and report_stage and actor_role != "doctor":
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
    actor_role = str(state.get("actor_role") or "patient").lower()
    if actor_role == "doctor":
        return True
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


def _autonomous_safety_gate(state: AgentState, llm_decision: dict | None) -> dict | None:
    """Enhanced safety validation for autonomous agent decisions."""
    if not llm_decision:
        return None

    tool_name = llm_decision.get("name", "")

    # Safety checks for clinical tools
    if tool_name == "clinical_generate_diagnosis":
        detections = state.get("detections")
        if not detections or not isinstance(detections, list) or len(detections) == 0:
            logger.warning("Autonomy safety gate: clinical_generate_diagnosis blocked - no detections")
            return None

    if tool_name == "clinical_assess_triage":
        diagnosis = state.get("diagnosis")
        if not diagnosis or not isinstance(diagnosis, dict):
            logger.warning("Autonomy safety gate: clinical_assess_triage blocked - no diagnosis")
            return None

    # Enhanced report safety gate
    if tool_name.startswith("report_generate_"):
        report_this_turn = _report_requested(state)
        if not report_this_turn:
            logger.warning("Autonomy safety gate: report tool blocked - not requested this turn")
            return None

        # Check patient info completeness
        if not _patient_info_complete(state):
            logger.warning("Autonomy safety gate: report tool blocked - incomplete patient info")
            return None

        # Prevent infinite retry of report tools
        report_tools_attempted = [
            t for t in state.get("tool_calls_made", [])
            if t.startswith("report_generate_")
        ]
        if report_tools_attempted:
            logger.warning("Autonomy safety gate: report tool blocked - already attempted")
            return None

    return llm_decision


def _multi_agent_recommendation(state: AgentState) -> dict | None:
    insights = state.get("multi_agent_insights") or {}
    recommendation = insights.get("consensus_recommendation")
    if not isinstance(recommendation, dict):
        return None

    tool_name = str(recommendation.get("tool") or "").strip()
    confidence = float(recommendation.get("confidence") or 0.0)

    if not tool_name or confidence < settings.multi_agent_confidence_threshold:
        return None

    validated = _autonomous_safety_gate(state, {"name": tool_name, "args": {}})
    if validated:
        logger.info(
            "Applying multi-agent recommendation: tool={} confidence={:.2f}",
            tool_name,
            confidence,
        )
    return validated


def _enhanced_context_aware_suggestion(state: AgentState) -> dict | None:
    """Provide context-aware suggestions with probabilistic reasoning."""
    body_part = state.get("body_part")
    detections = state.get("detections")
    diagnosis = state.get("diagnosis")
    triage = state.get("triage_result")

    # Only provide guidance when clinically appropriate, not forced
    candidates = []

    if not body_part and state.get("image_data"):
        # Use probabilistic reasoning to estimate confidence
        confidence = confidence_estimator.estimate_tool_confidence(
            "vision_detect_body_part",
            {"image_data": state.get("image_data")}
        )
        candidates.append({
            "reasoning": "No body part detected yet",
            "suggested_action": "vision_detect_body_part",
            "confidence": confidence,
            "uncertainty_level": "high" if confidence < 0.8 else "moderate"
        })

    if body_part and not detections:
        if body_part == "hand":
            confidence = confidence_estimator.estimate_tool_confidence(
                "vision_detect_hand_fracture",
                {"body_part": "hand", "image_data": state.get("image_data")}
            )
            candidates.append({
                "reasoning": "Hand detected, fracture analysis needed",
                "suggested_action": "vision_detect_hand_fracture",
                "confidence": confidence,
                "uncertainty_level": "high" if confidence < 0.8 else "moderate"
            })
        elif body_part == "leg":
            confidence = confidence_estimator.estimate_tool_confidence(
                "vision_detect_leg_fracture",
                {"body_part": "leg", "image_data": state.get("image_data")}
            )
            candidates.append({
                "reasoning": "Leg detected, fracture analysis needed",
                "suggested_action": "vision_detect_leg_fracture",
                "confidence": confidence,
                "uncertainty_level": "high" if confidence < 0.8 else "moderate"
            })

    if detections and not diagnosis:
        confidence = confidence_estimator.estimate_tool_confidence(
            "clinical_generate_diagnosis",
            {"detections": detections}
        )
        candidates.append({
            "reasoning": "Detections available, clinical diagnosis needed",
            "suggested_action": "clinical_generate_diagnosis",
            "confidence": confidence,
            "uncertainty_level": "high" if confidence < 0.7 else "moderate"
        })

    if diagnosis and not triage:
        confidence = confidence_estimator.estimate_tool_confidence(
            "clinical_assess_triage",
            {"diagnosis": diagnosis}
        )
        candidates.append({
            "reasoning": "Diagnosis available, triage assessment needed",
            "suggested_action": "clinical_assess_triage",
            "confidence": confidence,
            "uncertainty_level": "high" if confidence < 0.7 else "moderate"
        })

    # Use probabilistic selection instead of just taking highest confidence
    if candidates:
        selected_candidate = probabilistic_reasoner.select_action_with_probability(
            candidates,
            state
        )

        if selected_candidate and selected_candidate.get("confidence", 0) > 0.6:
            logger.info(
                "Probabilistically selected action: {} with confidence {:.3f}",
                selected_candidate["suggested_action"],
                selected_candidate["confidence"]
            )
            return {"name": selected_candidate["suggested_action"], "args": {}}

    return None


def _autonomous_decision_logic(state: AgentState) -> dict | None:
    """Enhanced decision-making with autonomy while maintaining safety."""
    consensus_recommendation = _multi_agent_recommendation(state)
    if consensus_recommendation:
        return consensus_recommendation

    # First try autonomous suggestions
    suggestion = _enhanced_context_aware_suggestion(state)
    if suggestion:
        # Pass through safety gate
        validated = _autonomous_safety_gate(state, suggestion)
        if validated:
            return validated

    # Handle report generation with enhanced autonomy but safety
    diagnosis = state.get("diagnosis")
    triage = state.get("triage_result")
    report_url = state.get("report_url")

    if diagnosis and triage and not report_url:
        report_this_turn = _report_requested(state)
        if report_this_turn:
            actor_role = str(state.get("actor_role") or "patient").lower()

            # Apply safety gate
            if actor_role == "doctor":
                tool_name = _doctor_report_type_clear(state)
                if tool_name:
                    validated = _autonomous_safety_gate(state, {"name": tool_name, "args": {}})
                    if validated:
                        return validated
            else:
                validated = _autonomous_safety_gate(state, {"name": "report_generate_patient_pdf", "args": {}})
                if validated:
                    return validated

    return None


# Keep original function name for backward compatibility
def _forced_tool_call(state: AgentState) -> dict | None:
    """Enhanced autonomous decision-making with safety validation."""
    return _autonomous_decision_logic(state)


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

    learning_context = SystemMessage(content=_build_learning_context(state))

    # MULTI-AGENT INTEGRATION: Add multi-agent insights when available
    multi_agent_context = ""
    multi_agent_insights = state.get("multi_agent_insights", {})

    if multi_agent_insights:
        from core.config import settings

        # Build context from multi-agent system
        context_parts = []

        # 1. Consensus recommendations
        if multi_agent_insights.get("consensus_recommendation"):
            consensus = multi_agent_insights["consensus_recommendation"]
            if consensus.get("confidence", 0) >= settings.multi_agent_confidence_threshold:
                context_parts.append(
                    f"=== MULTI-AGENT CONSENSUS ===\n"
                    f"Agents: {', '.join(consensus.get('participants', []))}\n"
                    f"Recommended Tool: {consensus.get('tool', 'N/A')}\n"
                    f"Confidence: {consensus.get('confidence', 0):.2f}\n"
                    f"Reasoning: {consensus.get('reasoning', '')}\n"
                )
                logger.info(
                    "Using multi-agent consensus recommendation: {} (confidence: {:.2f})",
                    consensus.get("tool", "unknown"), consensus.get("confidence", 0)
                )

        # 2. Agent perceptions
        if multi_agent_insights.get("agent_perceptions"):
            context_parts.append("=== SPECIALIST AGENT PERCEPTIONS ===\n")
            for agent_name, perceptions in multi_agent_insights["agent_perceptions"].items():
                context_parts.append(
                    f"{agent_name.upper()}: {len(perceptions.get('detections', []))} detections, "
                    f"quality={perceptions.get('image_quality', {}).get('overall_quality', 'unknown')}"
                )

        # 3. Collaborative opportunities
        if multi_agent_insights.get("collaborative_opportunities"):
            context_parts.append("=== COLLABORATIVE OPPORTUNITIES ===\n")
            for opportunity in multi_agent_insights["collaborative_opportunities"]:
                context_parts.append(
                    f"Type: {opportunity.get('type', 'unknown')}, "
                    f"Participants: {', '.join(opportunity.get('participants', []))}, "
                    f"Priority: {opportunity.get('priority', 2)}"
                )

        # 4. Recommended actions from specialized agents
        if multi_agent_insights.get("clinical_agent_actions"):
            context_parts.append("=== CLINICAL AGENT RECOMMENDATIONS ===\n")
            for action in multi_agent_insights["clinical_agent_actions"]:
                context_parts.append(
                    f"- {action.get('action_type', 'unknown')}: {action.get('description', '')} "
                    f"(confidence: {action.get('confidence', 0):.2f})"
                )

        if multi_agent_insights.get("vision_agent_actions"):
            context_parts.append("=== VISION AGENT RECOMMENDATIONS ===\n")
            for action in multi_agent_insights["vision_agent_actions"]:
                context_parts.append(
                    f"- {action.get('action_type', 'unknown')}: {action.get('description', '')} "
                    f"(confidence: {action.get('confidence', 0):.2f})"
                )

        multi_agent_context = "\n".join(context_parts) + "\n"
        logger.info("session={} Multi-agent insights integrated", session_id)

    pipeline_context = SystemMessage(content="PIPELINE STATUS:\n" + _build_pipeline_context(state))
    prompt_messages = [SystemMessage(content=SUPERVISOR_PROMPT), learning_context, safety_context, image_context, pipeline_context, *messages]

    # Add multi-agent context if available
    if multi_agent_context:
        prompt_messages.insert(2, SystemMessage(content=multi_agent_context))

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
    _report_needed = _report_requested(state)
    if _pipeline_complete and not _report_needed and not _report_already_done:
        logger.info("session={} analysis pipeline complete, routing directly to response_builder", session_id)
        return {
            "messages": [AIMessage(content="")],  # empty — response_builder uses structured state
            "iteration_count": state.get("iteration_count", 0) + 1,
            "tool_calls_made": state.get("tool_calls_made", []),
            "agent_trace": [*state.get("agent_trace", []), {"type": "supervisor_decision", "iteration": iteration, "active_agent": "none", "tool_calls": []}],
            "current_agent": None,
            "error": None,
            "pending_report_actor_role": None,
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
                    content="Generating the clinician summary PDF using the completed analysis."
                )
            # (Full clinical report option removed — doctor always gets summary report)
        # Pending auto-trigger is disabled: report generation must be explicit per-turn.
        _pending_flag_update: str | None = None
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
