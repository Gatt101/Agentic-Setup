from __future__ import annotations

from datetime import datetime
from functools import lru_cache
from uuid import uuid4

from langchain_core.messages import HumanMessage
from langgraph.graph import END, START, StateGraph
from loguru import logger

from core.config import settings
from core.exceptions import AgentExecutionError
from graph.checkpointer import get_checkpointer
from graph.nodes.error_handler import error_handler_node
from graph.nodes.response_builder import response_builder_node
from graph.nodes.supervisor import supervisor_node
from graph.nodes.tool_executor import tool_executor_node
from graph.state import AgentState, base_state
from services.chat_store import chat_store

# Multi-agent system integration
from agents.agent_coordinator import agent_coordinator
from services.agent_learning import adaptive_supervisor
from services.probabilistic_reasoning import bayesian_updater
import asyncio


def _report_requested(state: AgentState) -> bool:
    text = str(state.get("user_message") or "").lower().strip()
    report_keywords = ("report", "pdf", "document")
    type_keywords = ("summary", "quick", "simple", "simplified", "full", "clinical",
                     "detailed", "depth", "complete", "comprehensive")
    if any(keyword in text for keyword in report_keywords):
        return True
    # Treat type-selection responses as report requests when pipeline is complete
    diagnosis = state.get("diagnosis")
    triage = state.get("triage_result")
    if diagnosis and triage and not state.get("report_url"):
        if any(keyword in text for keyword in type_keywords):
            return True
        # Also handle numbered choices "1" / "2" as report type selection
        if text in ("1", "2"):
            return True
    return False


def should_continue(state: AgentState) -> str:
    if state.get("iteration_count", 0) >= settings.max_agent_iterations:
        return "error_handler"
    if state.get("error"):
        return "error_handler"

    messages = state.get("messages", [])
    if not messages:
        return "response_builder"

    last_message = messages[-1]

    # If supervisor returned tool calls, always execute them first
    if getattr(last_message, "tool_calls", None):
        return "tool_executor"

    # No tool calls — decide whether to end or loop back
    diagnosis = state.get("diagnosis")
    triage = state.get("triage_result")
    report_url = state.get("report_url")
    tool_calls_made = state.get("tool_calls_made", [])
    report_tool_attempts = sum(
        1 for name in tool_calls_made if name in {
            "report_generate_patient_pdf",
            "report_generate_clinician_pdf",
            "report_generate_clinician_simple_pdf",
        }
    )

    # When clinical pipeline is complete, run care-plan agents before responding
    if diagnosis and triage:
        if not state.get("care_plan_generated"):
            return "care_plan_node"
        if not _report_requested(state):
            return "response_builder"
        if report_url:
            return "response_builder"
        if report_tool_attempts >= 1:
            return "response_builder"

    return "response_builder"


def error_handler_route(state: AgentState) -> str:
    if state.get("final_response"):
        return "response_builder"
    if state.get("iteration_count", 0) >= settings.max_agent_iterations:
        return "response_builder"
    return "supervisor"


def _next_pipeline_tool(state: AgentState) -> str | None:
    if state.get("image_data") and not state.get("body_part"):
        return "vision_detect_body_part"

    body_part = str(state.get("body_part") or "").lower()
    if body_part == "hand" and not state.get("detections"):
        return "vision_detect_hand_fracture"
    if body_part == "leg" and not state.get("detections"):
        return "vision_detect_leg_fracture"

    if state.get("detections") and not state.get("diagnosis"):
        return "clinical_generate_diagnosis"
    if state.get("diagnosis") and not state.get("triage_result"):
        return "clinical_assess_triage"

    return None


def _first_actionable_tool(actions: object) -> str | None:
    if not isinstance(actions, list):
        return None

    for action in actions:
        if not isinstance(action, dict):
            continue
        action_type = str(action.get("action_type") or "")
        if action_type.startswith(("vision_", "clinical_", "hospital_", "report_", "knowledge_")):
            return action_type

    return None


def _resolve_consensus_tool_recommendation(
    state: AgentState,
    coordination_result: dict,
    consensus_decision: dict,
) -> str | None:
    explicit_tool = str(consensus_decision.get("recommended_tool") or "").strip()
    if explicit_tool:
        return explicit_tool

    agent_reasoning = coordination_result.get("agent_reasoning", {})
    primary_agent = str(consensus_decision.get("primary_agent") or "")
    if primary_agent:
        primary_actions = agent_reasoning.get(primary_agent, {}).get("recommended_actions", [])
        recommended_tool = _first_actionable_tool(primary_actions)
        if recommended_tool:
            return recommended_tool

    for agent_name in ("vision_agent", "clinical_agent"):
        recommended_tool = _first_actionable_tool(
            agent_reasoning.get(agent_name, {}).get("recommended_actions", [])
        )
        if recommended_tool:
            return recommended_tool

    return _next_pipeline_tool(state)


@lru_cache(maxsize=1)
def get_graph():
    workflow = StateGraph(AgentState)
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("tool_executor", tool_executor_node)
    workflow.add_node("response_builder", response_builder_node)
    workflow.add_node("error_handler", error_handler_node)
    workflow.add_node("care_plan_node", care_plan_node)

    # Multi-agent integration node (optional, can be enabled via config)
    workflow.add_node("multi_agent_integrator", multi_agent_integration_node)

    workflow.add_edge(START, "multi_agent_integrator")
    workflow.add_edge("multi_agent_integrator", "supervisor")
    workflow.add_conditional_edges(
        "supervisor",
        should_continue,
        {
            "tool_executor": "tool_executor",
            "response_builder": "response_builder",
            "error_handler": "error_handler",
            "care_plan_node": "care_plan_node",
        },
    )
    workflow.add_edge("tool_executor", "supervisor")
    # care_plan_node always goes directly to response_builder after running
    workflow.add_edge("care_plan_node", "response_builder")
    workflow.add_conditional_edges(
        "error_handler",
        error_handler_route,
        {"supervisor": "supervisor", "response_builder": "response_builder"},
    )
    workflow.add_edge("response_builder", END)

    return workflow.compile(checkpointer=get_checkpointer())


async def care_plan_node(state: AgentState) -> dict:
    """
    Run the four specialist care-plan agents in parallel once diagnosis and triage are ready.

    TreatmentPlannerAgent + RehabilitationAgent   → doctor-facing outputs
    PatientEducationAgent + AppointmentAgent       → patient-facing outputs

    All four run regardless of role; response_builder renders the role-appropriate sections.
    Skips gracefully if agents are unavailable or care plan was already generated.
    """
    if state.get("care_plan_generated"):
        return {}

    diagnosis = state.get("diagnosis")
    triage = state.get("triage_result")
    if not diagnosis or not triage:
        return {"care_plan_generated": True}

    session_id = state.get("session_id", "unknown")
    logger.info("care_plan_node: starting for session={}", session_id)

    # Ensure the coordinator has initialised its agents
    if not agent_coordinator._agents_initialized:
        try:
            await agent_coordinator.coordinate_analysis({"session_id": "init_care_plan"})
        except Exception:
            pass

    treatment_agent   = agent_coordinator.agents.get("treatment_planner_agent")
    rehab_agent       = agent_coordinator.agents.get("rehabilitation_agent")
    education_agent   = agent_coordinator.agents.get("patient_education_agent")
    appointment_agent = agent_coordinator.agents.get("appointment_agent")
    pdf_agent         = agent_coordinator.agents.get("pdf_generation_agent")

    if not all([treatment_agent, rehab_agent, education_agent, appointment_agent]):
        logger.warning("care_plan_node: one or more care-plan agents missing — skipping")
        return {"care_plan_generated": True}

    context = {
        "session_id": session_id,
        "diagnosis": diagnosis,
        "triage_result": triage,
        "patient_info": state.get("patient_info"),
        "body_part": state.get("body_part") or state.get("body_region") or "",
        "actor_role": state.get("actor_role"),
    }

    # Extend context with image data needed by the PDF agent
    context["image_base64"]           = state.get("image_data")
    context["annotated_image_base64"] = state.get("annotated_image_base64")
    context["detections"]             = state.get("detections")

    pdf_agents = [pdf_agent] if pdf_agent else []

    try:
        # Phase 1 — parallel perception (care-plan agents + PDF agent)
        p = await asyncio.gather(
            treatment_agent.perceive(context),
            rehab_agent.perceive(context),
            education_agent.perceive(context),
            appointment_agent.perceive(context),
            *(ag.perceive(context) for ag in pdf_agents),
            return_exceptions=True,
        )

        def _safe(result: object) -> dict:
            return result if isinstance(result, dict) else {}

        # Phase 2 — parallel reasoning
        r = await asyncio.gather(
            treatment_agent.reason({**context, **_safe(p[0])}),
            rehab_agent.reason({**context, **_safe(p[1])}),
            education_agent.reason({**context, **_safe(p[2])}),
            appointment_agent.reason({**context, **_safe(p[3])}),
            *(ag.reason({**context, **_safe(p[4 + i])}) for i, ag in enumerate(pdf_agents)),
            return_exceptions=True,
        )

        def _first_action(reasoning: object) -> dict:
            if not isinstance(reasoning, dict):
                return {}
            return (reasoning.get("recommended_actions") or [{}])[0]

        # Phase 3 — parallel action execution (care-plan agents only; PDF generates on demand)
        a = await asyncio.gather(
            treatment_agent.act(_first_action(r[0])),
            rehab_agent.act(_first_action(r[1])),
            education_agent.act(_first_action(r[2])),
            appointment_agent.act(_first_action(r[3])),
            return_exceptions=True,
        )

        updates: dict = {"care_plan_generated": True}

        if isinstance(a[0], dict) and a[0].get("success"):
            updates["treatment_plan"] = a[0].get("treatment_plan")
        if isinstance(a[1], dict) and a[1].get("success"):
            updates["rehabilitation_plan"] = a[1].get("rehabilitation_plan")
        if isinstance(a[2], dict) and a[2].get("success"):
            updates["patient_education"] = a[2].get("patient_education")
        if isinstance(a[3], dict) and a[3].get("success"):
            updates["appointment_schedule"] = a[3].get("appointment_schedule")

        logger.info(
            "care_plan_node: done session={} treatment={} rehab={} education={} appointment={}",
            session_id,
            bool(updates.get("treatment_plan")),
            bool(updates.get("rehabilitation_plan")),
            bool(updates.get("patient_education")),
            bool(updates.get("appointment_schedule")),
        )
        return updates

    except Exception as exc:
        logger.error("care_plan_node failed session={}: {}", session_id, exc)
        return {"care_plan_generated": True}


async def multi_agent_integration_node(state: AgentState) -> dict:
    """
    Integrate multi-agent insights into the production workflow.

    This node optionally runs multi-agent coordination and enriches the state
    with autonomous agent insights, collaborative decisions, and learning patterns.
    The integration is controlled via settings.multi_agent_enabled.
    """
    # Check if multi-agent integration is enabled
    if not settings.multi_agent_enabled:
        logger.debug("Multi-agent integration disabled, proceeding to supervisor")
        return {}

    session_id = state.get("session_id", "unknown")
    logger.info("Multi-agent integration node: session={}", session_id)

    try:
        # Prepare context for multi-agent coordination
        multi_agent_context = {
            "session_id": session_id,
            "user_message": state.get("user_message"),
            "image_data": state.get("image_data"),
            "symptoms": state.get("symptoms"),
            "patient_info": state.get("patient_info"),
            "location": state.get("location"),
            "actor_role": state.get("actor_role"),
            "actor_name": state.get("actor_name"),
            # Include existing production state
            "existing_diagnosis": state.get("diagnosis"),
            "existing_triage": state.get("triage_result"),
            "existing_detections": state.get("detections"),
            "existing_body_part": state.get("body_part")
        }

        # Coordinate multi-agent analysis
        logger.info("Calling multi-agent coordinator for session {}", session_id)
        coordination_result = await agent_coordinator.coordinate_analysis(multi_agent_context)

        if not coordination_result.get("success"):
            logger.warning(
                "Multi-agent coordination failed for session {}: {}",
                session_id, coordination_result.get("error", "unknown")
            )
            # Add failure as metadata for learning
            return {
                "multi_agent_coordination": {
                    "status": "failed",
                    "error": coordination_result.get("error"),
                    "timestamp": datetime.now().isoformat()
                }
            }

        # Extract valuable insights from multi-agent analysis
        multi_agent_insights = {}

        # 1. Consensus-based tool recommendations
        consensus_result = coordination_result.get("consensus_result", {})
        if consensus_result.get("consensus_reached"):
            consensus_decision = consensus_result.get("final_decision", {})
            decision_confidence = consensus_result.get("confidence", 0.5)
            recommended_tool = _resolve_consensus_tool_recommendation(
                state,
                coordination_result,
                consensus_decision,
            )

            if recommended_tool:
                multi_agent_insights["consensus_recommendation"] = {
                    "tool": recommended_tool,
                    "confidence": decision_confidence,
                    "reasoning": consensus_decision.get("reasoning", "Multi-agent consensus"),
                    "participants": consensus_result.get("participants", [])
                }

                logger.info(
                    "Multi-agent consensus reached: tool={}, confidence={:.2f}",
                    recommended_tool,
                    decision_confidence
                )

        # 2. Agent-perceived context enrichment
        agent_perceptions = coordination_result.get("agent_perceptions", {})
        multi_agent_insights["agent_perceptions"] = agent_perceptions

        # 3. Collaborative decision opportunities
        collaborative_decisions = coordination_result.get("collaborative_decisions", {})
        if collaborative_decisions:
            multi_agent_insights["collaborative_opportunities"] = []
            for decision_type, decision in collaborative_decisions.items():
                if decision.get("collaboration"):
                    multi_agent_insights["collaborative_opportunities"].append({
                        "type": decision_type,
                        "participants": decision.get("participants", []),
                        "priority": decision.get("priority", 2)
                    })

        # 4. Learning pattern suggestions
        agent_reasoning = coordination_result.get("agent_reasoning", {})
        if agent_reasoning.get("clinical_agent", {}).get("recommended_actions", []):
            clinical_actions = agent_reasoning["clinical_agent"]["recommended_actions"]
            multi_agent_insights["clinical_agent_actions"] = clinical_actions

        if agent_reasoning.get("vision_agent", {}).get("recommended_actions", []):
            vision_actions = agent_reasoning["vision_agent"]["recommended_actions"]
            multi_agent_insights["vision_agent_actions"] = vision_actions

        # Store coordination metadata for future learning
        coordination_metadata = {
            "coordination_id": coordination_result.get("coordination_id"),
            "coordination_time": coordination_result.get("coordination_time"),
            "consensus_reached": consensus_result.get("consensus_reached", False),
            "participants_count": len(coordination_result.get("agents_involved", [])),
            "timestamp": datetime.now().isoformat()
        }

        logger.info(
            "Multi-agent integration completed for session {}: consensus={}, agents={}, time={:.2f}s",
            session_id,
            consensus_result.get("consensus_reached", False),
            len(coordination_result.get("agents_involved", [])),
            coordination_result.get("coordination_time", 0)
        )

        return {
            "multi_agent_insights": multi_agent_insights,
            "multi_agent_coordination": coordination_metadata,
            "multi_agent_enabled": True
        }

    except Exception as e:
        logger.error("Multi-agent integration node failed: {}", e)
        return {
            "multi_agent_coordination": {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            },
            "multi_agent_enabled": True
        }


async def run_agent(payload: dict) -> AgentState:
    graph = get_graph()
    state = base_state()
    state.update(payload)

    session_id = state.get("session_id") or str(uuid4())
    user_message = state.get("user_message") or "Analyze the case with available context."

    state["session_id"] = session_id
    if not state.get("messages"):
        state["messages"] = [HumanMessage(content=user_message)]

    try:
        await chat_store.init_trace(session_id)
        await chat_store.append_trace_event(
            session_id,
            {
                "type": "session_started",
                "message": "Analysis request accepted by backend.",
            },
        )
    except Exception:
        pass
    logger.info("session={} agent_run_started", session_id)

    try:
        result = await graph.ainvoke(state, config={"configurable": {"thread_id": f"{session_id}:{uuid4()}"}})
    except Exception as exc:
        logger.exception("session={} agent_run_failed", session_id)
        raise AgentExecutionError(str(exc)) from exc

    logger.info(
        "session={} agent_run_completed iterations={} active_agent={}",
        session_id,
        result.get("iteration_count", 0),
        result.get("current_agent") or "none",
    )

    try:
        await adaptive_supervisor.learn_from_execution(result)
    except Exception:
        logger.warning("session={} execution learning failed", session_id)

    try:
        await chat_store.complete_trace(session_id, result.get("agent_trace", []))
    except Exception:
        pass

    return result
