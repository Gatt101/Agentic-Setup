from __future__ import annotations

from typing import Any, Dict, List

from loguru import logger

from agents.base_agent import BaseAgent, AgentCapabilities, AgentMessage
from tools import ALL_TOOLS


class PatientEducationAgent(BaseAgent):
    """Autonomous agent that translates clinical findings into plain-language patient guidance."""

    def __init__(self):
        capabilities = AgentCapabilities(
            agent_name="patient_education_agent",
            tool_capabilities=[
                "knowledge_get_patient_education",
            ],
            perception_abilities=["text", "structured_data"],
            reasoning_level="advanced",
            collaboration_style="cooperative",
            specialization_domains=["patient_communication", "health_literacy", "patient_education"],
            confidence_ranges={
                "knowledge_get_patient_education": (0.80, 0.95),
            },
            max_concurrent_tasks=3,
        )
        super().__init__(capabilities)
        self.education_context: Dict[str, Any] = {}

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
            "session_id": context.get("session_id"),
        }
        self.education_context.update(perceptions)

        logger.info(
            "PatientEducationAgent perceived: diagnosis={}, triage_level={}",
            bool(diagnosis),
            triage.get("level", "unknown"),
        )
        return perceptions

    async def reason(self, context: Dict[str, Any]) -> Dict[str, Any]:
        diagnosis = self._extract_diagnosis(context)
        triage = self._extract_triage(context)

        situation = "ready_to_educate" if (diagnosis and triage) else "awaiting_clinical_data"

        reasoning = {
            "education_situation": situation,
            "has_diagnosis": bool(diagnosis),
            "has_triage": bool(triage),
            "triage_level": triage.get("level", "AMBER"),
            "recommended_actions": [],
        }

        if situation == "ready_to_educate":
            reasoning["recommended_actions"].append({
                "action_type": "knowledge_get_patient_education",
                "description": "Generate plain-language patient education content",
                "priority": 1,
                "confidence": 0.90,
            })

        logger.info(
            "PatientEducationAgent reasoning: situation={}, actions={}",
            situation,
            [a.get("action_type") for a in reasoning["recommended_actions"]],
        )
        return reasoning

    async def act(self, action: Dict[str, Any]) -> Dict[str, Any]:
        action_type = action.get("action_type")
        if action_type == "knowledge_get_patient_education":
            return await self._generate_education_content(action)
        logger.warning("PatientEducationAgent: unknown action {}", action_type)
        return {"success": False, "error": "Unknown action type"}

    async def _generate_education_content(self, action: Dict[str, Any]) -> Dict[str, Any]:
        try:
            edu_tool = next(
                (t for t in ALL_TOOLS if t.name == "knowledge_get_patient_education"), None
            )
            if not edu_tool:
                return {"success": False, "error": "Patient education tool not found"}

            diagnosis = self._extract_diagnosis(self.education_context)
            triage = self._extract_triage(self.education_context)
            patient_info = self._extract_patient_info(self.education_context)

            if not diagnosis:
                return {"success": False, "error": "No diagnosis available for patient education"}

            diag_str = (
                diagnosis.get("finding", str(diagnosis))
                if isinstance(diagnosis, dict)
                else str(diagnosis)
            )
            triage_level = triage.get("level", "AMBER")
            patient_age = int(patient_info.get("age", 40))
            body_part = self.education_context.get("body_part", "")

            result = await edu_tool.ainvoke({
                "diagnosis": diag_str,
                "triage_level": triage_level,
                "body_part": body_part,
                "patient_age": patient_age,
            })

            return {"success": True, "patient_education": result, "confidence": 0.90}

        except Exception as e:
            logger.error("PatientEducationAgent content generation failed: {}", e)
            return {"success": False, "error": str(e)}

    def _identify_urgent_tasks(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        triage = self._extract_triage(context)
        if triage.get("level", "").upper() == "RED":
            return [{
                "description": "Urgent patient education required — RED triage case",
                "objective": "Explain emergency situation to patient in plain language",
                "success_criteria": ["education_content_delivered"],
            }]
        return []

    def _identify_improvements(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        patient_info = self._extract_patient_info(context)
        if not patient_info.get("age"):
            return [{
                "description": "Patient age missing — age-specific education not possible",
                "objective": "Collect patient age for tailored education",
                "success_criteria": ["patient_age_collected"],
            }]
        return []

    async def _generate_consensus_assessment(self, topic: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "agent": "patient_education_agent",
            "assessment": "patient_communication_assessment",
            "confidence": 0.90,
            "reasoning": "Patient-centred communication and health literacy",
            "specialist_view": "Plain-language explanation of diagnosis and management",
            "recommendations": [
                "Adapt language complexity for patient age and literacy",
                "Include warning signs and when to seek emergency help",
            ],
        }
