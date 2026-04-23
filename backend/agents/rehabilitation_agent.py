from __future__ import annotations

from typing import Any, Dict, List

from loguru import logger

from agents.base_agent import BaseAgent, AgentCapabilities, AgentMessage
from tools import ALL_TOOLS


class RehabilitationAgent(BaseAgent):
    """Autonomous agent that produces phased physiotherapy and recovery plans."""

    def __init__(self):
        capabilities = AgentCapabilities(
            agent_name="rehabilitation_agent",
            tool_capabilities=[
                "knowledge_get_rehabilitation_plan",
            ],
            perception_abilities=["text", "structured_data"],
            reasoning_level="expert",
            collaboration_style="cooperative",
            specialization_domains=["physiotherapy", "rehabilitation", "recovery_planning"],
            confidence_ranges={
                "knowledge_get_rehabilitation_plan": (0.78, 0.93),
            },
            max_concurrent_tasks=3,
        )
        super().__init__(capabilities)
        self.rehab_context: Dict[str, Any] = {}

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
            "treatment_plan": context.get("treatment_plan"),
            "body_part": context.get("body_part", ""),
            "session_id": context.get("session_id"),
        }
        self.rehab_context.update(perceptions)

        logger.info(
            "RehabilitationAgent perceived: diagnosis={}, triage_level={}",
            bool(diagnosis),
            triage.get("level", "unknown"),
        )
        return perceptions

    async def reason(self, context: Dict[str, Any]) -> Dict[str, Any]:
        diagnosis = self._extract_diagnosis(context)
        triage = self._extract_triage(context)

        has_treatment = bool(context.get("treatment_plan"))
        situation = "ready_for_rehab" if (diagnosis and triage) else "awaiting_clinical_data"

        reasoning = {
            "rehab_situation": situation,
            "has_diagnosis": bool(diagnosis),
            "has_triage": bool(triage),
            "has_treatment_plan": has_treatment,
            "triage_level": triage.get("level", "AMBER"),
            "recommended_actions": [],
        }

        if situation == "ready_for_rehab":
            reasoning["recommended_actions"].append({
                "action_type": "knowledge_get_rehabilitation_plan",
                "description": "Generate phased rehabilitation programme",
                "priority": 1,
                "confidence": 0.88,
            })

        logger.info(
            "RehabilitationAgent reasoning: situation={}, actions={}",
            situation,
            [a.get("action_type") for a in reasoning["recommended_actions"]],
        )
        return reasoning

    async def act(self, action: Dict[str, Any]) -> Dict[str, Any]:
        action_type = action.get("action_type")
        if action_type == "knowledge_get_rehabilitation_plan":
            return await self._generate_rehab_plan(action)
        logger.warning("RehabilitationAgent: unknown action {}", action_type)
        return {"success": False, "error": "Unknown action type"}

    async def _generate_rehab_plan(self, action: Dict[str, Any]) -> Dict[str, Any]:
        try:
            rehab_tool = next(
                (t for t in ALL_TOOLS if t.name == "knowledge_get_rehabilitation_plan"), None
            )
            if not rehab_tool:
                return {"success": False, "error": "Rehabilitation tool not found"}

            diagnosis = self._extract_diagnosis(self.rehab_context)
            triage = self._extract_triage(self.rehab_context)
            patient_info = self._extract_patient_info(self.rehab_context)

            if not diagnosis:
                return {"success": False, "error": "No diagnosis available for rehabilitation planning"}

            diag_str = (
                diagnosis.get("finding", str(diagnosis))
                if isinstance(diagnosis, dict)
                else str(diagnosis)
            )
            triage_level = triage.get("level", "AMBER")
            patient_age = int(patient_info.get("age", 40))
            body_part = self.rehab_context.get("body_part", "")

            result = await rehab_tool._arun(
                diagnosis=diag_str,
                triage_level=triage_level,
                patient_age=patient_age,
                body_part=body_part,
            )

            return {"success": True, "rehabilitation_plan": result, "confidence": 0.88}

        except Exception as e:
            logger.error("RehabilitationAgent plan generation failed: {}", e)
            return {"success": False, "error": str(e)}

    def _identify_urgent_tasks(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        triage = self._extract_triage(context)
        if triage.get("level", "").upper() == "RED":
            return [{
                "description": "Post-surgical rehabilitation planning required",
                "objective": "Generate immediate post-operative rehab protocol",
                "success_criteria": ["rehab_plan_generated"],
            }]
        return []

    def _identify_improvements(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        if not context.get("treatment_plan"):
            return [{
                "description": "No treatment plan available — rehabilitation sequencing may be suboptimal",
                "objective": "Coordinate with TreatmentPlannerAgent for full pathway",
                "success_criteria": ["treatment_plan_received"],
            }]
        return []

    async def _generate_consensus_assessment(self, topic: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "agent": "rehabilitation_agent",
            "assessment": "rehabilitation_pathway_assessment",
            "confidence": 0.88,
            "reasoning": "Phased physiotherapy based on triage and age",
            "specialist_view": "Physiotherapy and recovery timeline perspective",
            "recommendations": [
                "Confirm treatment approach before sequencing rehab phases",
                "Adjust timeline for elderly or paediatric patients",
            ],
        }
