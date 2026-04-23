"""PDF Generation Agent — collects all report context and generates a comprehensive PDF."""
from __future__ import annotations

from typing import Any, Dict, List

from loguru import logger

from agents.base_agent import AgentCapabilities, BaseAgent
from tools import ALL_TOOLS


class PDFGenerationAgent(BaseAgent):
    """Agent that assembles full report context and calls the comprehensive PDF tool."""

    def __init__(self):
        capabilities = AgentCapabilities(
            agent_name="pdf_generation_agent",
            tool_capabilities=["report_generate_comprehensive_pdf"],
            perception_abilities=["text", "structured_data", "vision"],
            reasoning_level="advanced",
            collaboration_style="cooperative",
            specialization_domains=["report_generation", "pdf", "clinical_documentation"],
            confidence_ranges={
                "report_generate_comprehensive_pdf": (0.85, 0.97),
            },
            max_concurrent_tasks=2,
        )
        super().__init__(capabilities)
        self.pdf_context: Dict[str, Any] = {}

    # ── Context helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _patient_info(ctx: Dict[str, Any]) -> Dict[str, Any]:
        p = ctx.get("patient_info")
        return p if isinstance(p, dict) else {}

    @staticmethod
    def _diagnosis(ctx: Dict[str, Any]) -> Any:
        return ctx.get("diagnosis") or ctx.get("existing_diagnosis")

    @staticmethod
    def _triage(ctx: Dict[str, Any]) -> Dict[str, Any]:
        t = ctx.get("triage_result") or ctx.get("existing_triage")
        return t if isinstance(t, dict) else {}

    # ── perceive ──────────────────────────────────────────────────────────────

    async def perceive(self, context: Dict[str, Any]) -> Dict[str, Any]:
        pi = self._patient_info(context)

        perceptions = {
            "diagnosis":              self._diagnosis(context),
            "triage_result":          self._triage(context),
            "patient_info":           pi,
            "actor_role":             context.get("actor_role", "doctor"),
            "image_base64":           context.get("image_data") or context.get("image_base64"),
            "annotated_image_base64": context.get("annotated_image_base64"),
            "detections":             context.get("detections"),
            "treatment_plan":         context.get("treatment_plan"),
            "rehabilitation_plan":    context.get("rehabilitation_plan"),
            "patient_education":      context.get("patient_education"),
            "appointment_schedule":   context.get("appointment_schedule"),
            "body_part":              context.get("body_part", ""),
            "session_id":             context.get("session_id"),
            # Completeness flags
            "has_name":    bool(str(pi.get("name")   or "").strip()),
            "has_age":     pi.get("age") is not None,
            "has_gender":  bool(str(pi.get("gender") or "").strip()),
        }
        self.pdf_context.update(perceptions)

        logger.info(
            "PDFGenerationAgent perceived: diagnosis={} triage={} name={} age={} "
            "gender={} image={} annotated={}",
            bool(perceptions["diagnosis"]),
            bool(perceptions["triage_result"]),
            perceptions["has_name"],
            perceptions["has_age"],
            perceptions["has_gender"],
            bool(perceptions["image_base64"]),
            bool(perceptions["annotated_image_base64"]),
        )
        return perceptions

    # ── reason ────────────────────────────────────────────────────────────────

    async def reason(self, context: Dict[str, Any]) -> Dict[str, Any]:
        diagnosis = self._diagnosis(context)
        triage = self._triage(context)
        pi = self._patient_info(context)

        has_name   = bool(str(pi.get("name")   or "").strip())
        has_age    = pi.get("age") is not None
        has_gender = bool(str(pi.get("gender") or "").strip())
        missing    = [f for f, ok in [("name", has_name), ("age", has_age), ("gender", has_gender)] if not ok]

        if not diagnosis or not triage:
            situation = "awaiting_clinical_data"
        elif missing:
            situation = "ready_with_partial_patient_info"
        else:
            situation = "ready_to_generate"

        reasoning: Dict[str, Any] = {
            "pdf_situation":          situation,
            "has_diagnosis":          bool(diagnosis),
            "has_triage":             bool(triage),
            "patient_info_complete":  not missing,
            "missing_patient_fields": missing,
            "has_image":              bool(context.get("image_data") or context.get("image_base64")),
            "has_care_plan":          bool(context.get("treatment_plan") or context.get("rehabilitation_plan")),
            "recommended_actions":    [],
        }

        if situation in ("ready_to_generate", "ready_with_partial_patient_info"):
            reasoning["recommended_actions"].append({
                "action_type": "report_generate_comprehensive_pdf",
                "description": "Generate comprehensive PDF with all available data",
                "priority":    1,
                "confidence":  0.92,
            })

        logger.info(
            "PDFGenerationAgent reasoning: situation={} missing={}",
            situation, missing,
        )
        return reasoning

    # ── act ───────────────────────────────────────────────────────────────────

    async def act(self, action: Dict[str, Any]) -> Dict[str, Any]:
        if action.get("action_type") == "report_generate_comprehensive_pdf":
            return await self._generate_pdf()
        logger.warning("PDFGenerationAgent: unknown action {}", action.get("action_type"))
        return {"success": False, "error": "Unknown action type"}

    async def _generate_pdf(self) -> Dict[str, Any]:
        try:
            pdf_tool = next(
                (t for t in ALL_TOOLS if t.name == "report_generate_comprehensive_pdf"), None
            )
            if not pdf_tool:
                return {"success": False, "error": "comprehensive PDF tool not registered"}

            ctx = self.pdf_context
            diagnosis = self._diagnosis(ctx)
            triage    = self._triage(ctx)
            pi        = self._patient_info(ctx)

            if not diagnosis or not triage:
                return {"success": False, "error": "Diagnosis and triage required"}

            recs: list[str] = []
            tf = str(triage.get("recommended_timeframe") or "")
            if tf:
                recs.append(tf)
            rt = str(triage.get("rationale") or "")
            if rt:
                recs.append(rt)
            if not recs:
                recs = ["Follow clinical protocol appropriate to triage level."]

            result = await pdf_tool.ainvoke({
                "diagnosis": diagnosis,
                "triage": triage,
                "patient_info": pi,
                "actor_role": str(ctx.get("actor_role") or "doctor"),
                "image_base64": ctx.get("image_base64"),
                "annotated_image_base64": ctx.get("annotated_image_base64"),
                "detections": ctx.get("detections") or [],
                "recommendations": recs,
                "metadata": {
                    "patient_id": str(pi.get("patient_id") or "unknown"),
                    "patient_name": str(pi.get("name") or ""),
                    "patient_age": str(pi.get("age") or ""),
                    "patient_gender": str(pi.get("gender") or ""),
                    "doctor_name": str(pi.get("doctor") or ""),
                    "body_part": str(ctx.get("body_part") or pi.get("body_part") or ""),
                },
                "treatment_plan": ctx.get("treatment_plan"),
                "rehabilitation_plan": ctx.get("rehabilitation_plan"),
                "patient_education": ctx.get("patient_education"),
                "appointment_schedule": ctx.get("appointment_schedule"),
            })

            if result.get("error"):
                return {"success": False, "error": result["error"]}

            logger.info(
                "PDFGenerationAgent: PDF generated report_id={}",
                result.get("report_id"),
            )
            return {
                "success":   True,
                "pdf_url":   result.get("pdf_url"),
                "report_id": result.get("report_id"),
                "confidence": 0.95,
            }

        except Exception as exc:
            logger.error("PDFGenerationAgent._generate_pdf failed: {}", exc)
            return {"success": False, "error": str(exc)}

    # ── goal helpers ──────────────────────────────────────────────────────────

    def _identify_urgent_tasks(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        if self._triage(context).get("level", "").upper() == "RED":
            return [{
                "description": "Urgent PDF report required for RED triage",
                "objective": "Generate immediate clinical report",
                "success_criteria": ["pdf_generated"],
            }]
        return []

    async def _generate_consensus_assessment(self, topic: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "agent": "pdf_generation_agent",
            "assessment": "report_generation_assessment",
            "confidence": 0.92,
            "reasoning": "Comprehensive PDF with all patient info and both images",
            "specialist_view": "Clinical report generation and documentation",
            "recommendations": [
                "Ensure patient name, age, gender are captured before generating",
                "Include both original and annotated X-ray images",
                "Attach care plan (treatment, rehab, education, appointments)",
            ],
        }
