from __future__ import annotations

from typing import Any, Dict, List

from loguru import logger

from agents.base_agent import BaseAgent, AgentCapabilities, AgentMessage
from tools import ALL_TOOLS


class AppointmentAgent(BaseAgent):
    """Autonomous agent that schedules follow-up appointments and imaging milestones."""

    def __init__(self):
        capabilities = AgentCapabilities(
            agent_name="appointment_agent",
            tool_capabilities=[
                "knowledge_get_appointment_schedule",
            ],
            perception_abilities=["text", "structured_data"],
            reasoning_level="advanced",
            collaboration_style="cooperative",
            specialization_domains=["appointment_scheduling", "care_coordination", "follow_up_planning"],
            confidence_ranges={
                "knowledge_get_appointment_schedule": (0.80, 0.93),
            },
            max_concurrent_tasks=3,
        )
        super().__init__(capabilities)
        self.appointment_context: Dict[str, Any] = {}

    @staticmethod
    def _extract_diagnosis(context: Dict[str, Any]) -> Any:
        return context.get("diagnosis") or context.get("existing_diagnosis")

    @staticmethod
    def _extract_triage(context: Dict[str, Any]) -> Dict[str, Any]:
        t = context.get("triage_result") or context.get("existing_triage")
        return t if isinstance(t, dict) else {}

    @staticmethod
    def _extract_patient_info(context: Dict[str, Any]) -> Dict[str, Any]:
        p = context.get("patient_info")
        return p if isinstance(p, dict) else {}

    async def perceive(self, context: Dict[str, Any]) -> Dict[str, Any]:
        diagnosis = self._extract_diagnosis(context)
        triage = self._extract_triage(context)
        patient_info = self._extract_patient_info(context)

        perceptions = {
            "diagnosis": diagnosis,
            "triage_result": triage,
            "patient_info": patient_info,
            "body_part": context.get("body_part", ""),
            "treatment_plan": context.get("treatment_plan"),
            "session_id": context.get("session_id"),
        }
        self.appointment_context.update(perceptions)

        logger.info(
            "AppointmentAgent perceived: diagnosis={}, triage_level={}",
            bool(diagnosis),
            triage.get("level", "unknown"),
        )
        return perceptions

    async def reason(self, context: Dict[str, Any]) -> Dict[str, Any]:
        diagnosis = self._extract_diagnosis(context)
        triage = self._extract_triage(context)

        situation = "ready_to_schedule" if (diagnosis and triage) else "awaiting_clinical_data"

        reasoning = {
            "scheduling_situation": situation,
            "has_diagnosis": bool(diagnosis),
            "has_triage": bool(triage),
            "triage_level": triage.get("level", "AMBER"),
            "recommended_actions": [],
        }

        if situation == "ready_to_schedule":
            reasoning["recommended_actions"].append({
                "action_type": "knowledge_get_appointment_schedule",
                "description": "Generate follow-up appointment and imaging milestones",
                "priority": 1 if triage.get("level", "").upper() == "RED" else 2,
                "confidence": 0.88,
            })

        logger.info(
            "AppointmentAgent reasoning: situation={}, triage={}, actions={}",
            situation,
            triage.get("level", "unknown"),
            [a.get("action_type") for a in reasoning["recommended_actions"]],
        )
        return reasoning

    async def act(self, action: Dict[str, Any]) -> Dict[str, Any]:
        action_type = action.get("action_type")
        if action_type == "knowledge_get_appointment_schedule":
            return await self._generate_appointment_schedule(action)
        logger.warning("AppointmentAgent: unknown action {}", action_type)
        return {"success": False, "error": "Unknown action type"}

    async def _generate_appointment_schedule(self, action: Dict[str, Any]) -> Dict[str, Any]:
        try:
            appt_tool = next(
                (t for t in ALL_TOOLS if t.name == "knowledge_get_appointment_schedule"), None
            )
            if not appt_tool:
                return {"success": False, "error": "Appointment scheduling tool not found"}

            diagnosis = self._extract_diagnosis(self.appointment_context)
            triage = self._extract_triage(self.appointment_context)
            patient_info = self._extract_patient_info(self.appointment_context)

            if not diagnosis:
                return {"success": False, "error": "No diagnosis available for appointment scheduling"}

            diag_str = (
                diagnosis.get("finding", str(diagnosis))
                if isinstance(diagnosis, dict)
                else str(diagnosis)
            )
            triage_level = triage.get("level", "AMBER")
            patient_age = int(patient_info.get("age", 40))
            body_part = self.appointment_context.get("body_part", "")

            result = await appt_tool._arun(
                diagnosis=diag_str,
                triage_level=triage_level,
                body_part=body_part,
                patient_age=patient_age,
            )

            return {"success": True, "appointment_schedule": result, "confidence": 0.88}

        except Exception as e:
            logger.error("AppointmentAgent schedule generation failed: {}", e)
            return {"success": False, "error": str(e)}

    def _identify_urgent_tasks(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        triage = self._extract_triage(context)
        if triage.get("level", "").upper() == "RED":
            return [{
                "description": "Emergency follow-up scheduling required — RED triage",
                "objective": "Schedule 24-hour specialist review",
                "success_criteria": ["urgent_appointment_scheduled"],
            }]
        return []

    def _identify_improvements(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        if not context.get("treatment_plan"):
            return [{
                "description": "Treatment plan not yet available — appointment spacing may be suboptimal",
                "objective": "Coordinate with TreatmentPlannerAgent",
                "success_criteria": ["treatment_plan_received"],
            }]
        return []

    async def _generate_consensus_assessment(self, topic: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "agent": "appointment_agent",
            "assessment": "care_coordination_assessment",
            "confidence": 0.88,
            "reasoning": "Follow-up scheduling based on triage severity and clinical pathway",
            "specialist_view": "Care coordination and continuity of care",
            "recommendations": [
                "Align appointment schedule with rehabilitation milestones",
                "Flag RED triage cases for immediate specialist booking",
            ],
        }
