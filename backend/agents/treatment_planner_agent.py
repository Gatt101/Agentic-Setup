from __future__ import annotations

from typing import Any, Dict, List
from datetime import datetime

from loguru import logger

from agents.base_agent import BaseAgent, AgentCapabilities, AgentGoal, AgentMessage
from tools import ALL_TOOLS


class TreatmentPlannerAgent(BaseAgent):
    """Autonomous agent that builds conservative and surgical treatment pathways."""

    def __init__(self):
        capabilities = AgentCapabilities(
            agent_name="treatment_planner_agent",
            tool_capabilities=[
                "knowledge_get_treatment_recommendations",
            ],
            perception_abilities=["text", "structured_data"],
            reasoning_level="expert",
            collaboration_style="cooperative",
            specialization_domains=["orthopedics", "treatment_planning", "clinical_pathways"],
            confidence_ranges={
                "knowledge_get_treatment_recommendations": (0.75, 0.92),
            },
            max_concurrent_tasks=3,
        )
        super().__init__(capabilities)
        self.planner_context: Dict[str, Any] = {}

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
        self.planner_context.update(perceptions)

        logger.info(
            "TreatmentPlannerAgent perceived context: diagnosis={}, triage_level={}",
            bool(diagnosis),
            triage.get("level", "unknown"),
        )
        return perceptions

    async def reason(self, context: Dict[str, Any]) -> Dict[str, Any]:
        diagnosis = self._extract_diagnosis(context)
        triage = self._extract_triage(context)

        situation = "ready_to_plan" if diagnosis else "awaiting_diagnosis"
        if not triage:
            situation = "awaiting_triage"

        reasoning = {
            "planning_situation": situation,
            "has_diagnosis": bool(diagnosis),
            "has_triage": bool(triage),
            "triage_level": triage.get("level", "AMBER"),
            "recommended_actions": [],
        }

        if situation == "ready_to_plan":
            reasoning["recommended_actions"].append({
                "action_type": "knowledge_get_treatment_recommendations",
                "description": "Generate treatment pathway from diagnosis and triage",
                "priority": 1,
                "confidence": 0.85,
            })

        logger.info(
            "TreatmentPlannerAgent reasoning: situation={}, actions={}",
            situation,
            [a.get("action_type") for a in reasoning["recommended_actions"]],
        )
        return reasoning

    async def act(self, action: Dict[str, Any]) -> Dict[str, Any]:
        action_type = action.get("action_type")
        if action_type == "knowledge_get_treatment_recommendations":
            return await self._generate_treatment_plan(action)
        logger.warning("TreatmentPlannerAgent: unknown action {}", action_type)
        return {"success": False, "error": "Unknown action type"}

    async def _generate_treatment_plan(self, action: Dict[str, Any]) -> Dict[str, Any]:
        try:
            treatment_tool = next(
                (t for t in ALL_TOOLS if t.name == "knowledge_get_treatment_recommendations"), None
            )
            if not treatment_tool:
                return {"success": False, "error": "Treatment tool not found"}

            diagnosis = self._extract_diagnosis(self.planner_context)
            triage = self._extract_triage(self.planner_context)
            patient_info = self._extract_patient_info(self.planner_context)

            if not diagnosis:
                return {"success": False, "error": "No diagnosis available"}

            diag_str = (
                diagnosis.get("finding", str(diagnosis))
                if isinstance(diagnosis, dict)
                else str(diagnosis)
            )
            triage_level = triage.get("level", "AMBER")
            patient_age = int(patient_info.get("age", 40))

            result = await treatment_tool.ainvoke({
                "diagnosis": diag_str,
                "triage_level": triage_level,
                "patient_age": patient_age,
            })

            severity = diagnosis.get("severity", "moderate") if isinstance(diagnosis, dict) else "moderate"
            approach = (
                "surgical"
                if (triage_level == "RED" or severity == "severe")
                else "conservative"
            )

            plan = {
                "approach": approach,
                "immediate_steps": result.get("immediate_steps", []),
                "long_term_plan": result.get("long_term", []),
                "medications": result.get("medications", []),
                "restrictions": result.get("restrictions", []),
                "diagnosis_context": diag_str,
                "triage_level": triage_level,
                "patient_age": patient_age,
            }

            return {"success": True, "treatment_plan": plan, "confidence": 0.87}

        except Exception as e:
            logger.error("TreatmentPlannerAgent treatment generation failed: {}", e)
            return {"success": False, "error": str(e)}

    def _identify_urgent_tasks(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        triage = self._extract_triage(context)
        if triage.get("level", "").upper() == "RED":
            return [{
                "description": "Urgent treatment pathway required for RED triage",
                "objective": "Generate immediate treatment recommendations",
                "success_criteria": ["treatment_plan_generated"],
            }]
        return []

    def _identify_improvements(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        if not self._extract_patient_info(context).get("age"):
            return [{
                "description": "Patient age unavailable — age-adjusted plan not possible",
                "objective": "Obtain patient age for personalised recommendations",
                "success_criteria": ["patient_age_available"],
            }]
        return []

    async def _generate_consensus_assessment(self, topic: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "agent": "treatment_planner_agent",
            "assessment": "treatment_pathway_assessment",
            "confidence": 0.87,
            "reasoning": "Evidence-based treatment planning",
            "specialist_view": "Clinical pathway and treatment approach",
            "recommendations": [
                "Verify triage level before finalising approach",
                "Confirm patient age for age-adjusted pathway",
            ],
        }
