from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional
from datetime import datetime

from loguru import logger

from agents.base_agent import BaseAgent, AgentCapabilities, AgentGoal, AgentMessage
from tools import ALL_TOOLS


class ClinicalAgent(BaseAgent):
    """Autonomous clinical analysis agent specializing in diagnosis and triage."""

    def __init__(self):
        capabilities = AgentCapabilities(
            agent_name="clinical_agent",
            tool_capabilities=[
                "clinical_generate_diagnosis",
                "clinical_assess_triage",
                "clinical_analyze_symptoms"
            ],
            perception_abilities=["text", "structured_data"],
            reasoning_level="expert",
            collaboration_style="cooperative",
            specialization_domains=["orthopedics", "triage", "clinical_reasoning"],
            confidence_ranges={
                "clinical_generate_diagnosis": (0.7, 0.9),
                "clinical_assess_triage": (0.8, 0.95),
                "clinical_analyze_symptoms": (0.75, 0.9)
            },
            max_concurrent_tasks=3
        )

        super().__init__(capabilities)
        self.clinical_context = {}
        self.patient_history = {}

    async def perceive(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Perceive clinical context and gather relevant information."""
        perceptions = {
            "image_data": context.get("image_data"),
            "detections": context.get("detections"),
            "symptoms": context.get("symptoms"),
            "patient_info": context.get("patient_info", {}),
            "existing_diagnosis": context.get("diagnosis"),
            "existing_triage": context.get("triage_result"),
            "location": context.get("location"),
            "session_id": context.get("session_id")
        }

        # Update clinical context
        self.clinical_context.update(perceptions)

        # Extract patient information for history tracking
        patient_id = context.get("patient_id")
        if patient_id:
            self.patient_history[patient_id] = self.patient_history.get(patient_id, {})
            if context.get("diagnosis"):
                self.patient_history[patient_id]["recent_diagnoses"] = \
                    self.patient_history[patient_id].get("recent_diagnoses", [])
                self.patient_history[patient_id]["recent_diagnoses"].append({
                    "diagnosis": context["diagnosis"],
                    "timestamp": datetime.now()
                })

        logger.info(
            "Clinical agent perceived context: detections={}, symptoms={}, patient={}",
            len(perceptions.get("detections", [])),
            bool(perceptions.get("symptoms")),
            patient_id
        )

        return perceptions

    async def reason(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Reason about clinical situation and form hypotheses."""
        reasoning = {
            "clinical_situation": self._assess_clinical_situation(context),
            "information_completeness": self._assess_information_completeness(context),
            "priority_assessment": self._assess_priority(context),
            "hypotheses": self._generate_clinical_hypotheses(context),
            "collaboration_needs": self._identify_collaboration_needs(context),
            "recommended_actions": []
        }

        # Formulate recommended actions based on reasoning
        reasoning["recommended_actions"] = await self._plan_clinical_actions(context, reasoning)

        logger.info(
            "Clinical agent reasoning: situation={}, priority={}, actions={}",
            reasoning["clinical_situation"],
            reasoning["priority_assessment"]["level"],
            [a.get("action_type") for a in reasoning["recommended_actions"]]
        )

        return reasoning

    def _assess_clinical_situation(self, context: Dict[str, Any]) -> str:
        """Assess overall clinical situation."""
        detections = context.get("detections")
        diagnosis = context.get("diagnosis")
        triage = context.get("triage_result")
        symptoms = context.get("symptoms")

        if not detections and not symptoms:
            return "waiting_for_clinical_data"

        if detections and not diagnosis:
            return "diagnosis_needed"

        if diagnosis and not triage:
            return "triage_needed"

        if diagnosis and triage:
            return "clinical_analysis_complete"

        return "clinical_analysis_in_progress"

    def _assess_information_completeness(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Assess completeness of available clinical information."""
        completeness = {
            "detections_available": bool(context.get("detections")),
            "symptoms_available": bool(context.get("symptoms")),
            "patient_info_complete": False,
            "overall_score": 0.0
        }

        patient_info = context.get("patient_info", {})
        completeness["patient_info_complete"] = all([
            patient_info.get("name"),
            patient_info.get("age"),
            patient_info.get("gender")
        ])

        # Calculate overall completeness score
        factors = [
            completeness["detections_available"],
            completeness["symptoms_available"] or completeness["patient_info_complete"],
            completeness["patient_info_complete"]
        ]
        completeness["overall_score"] = sum(factors) / len(factors)

        return completeness

    def _assess_priority(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Assess urgency and priority of clinical situation."""
        priority = {
            "level": "medium",
            "factors": []
        }

        # Check for urgent indicators
        symptoms = context.get("symptoms", "").lower()
        if any(urgent in symptoms for urgent in ["severe", "emergency", "acute pain", "bleeding"]):
            priority["level"] = "urgent"
            priority["factors"].append("severe_symptoms")

        # Check existing triage level
        triage = context.get("triage_result", {})
        triage_level = triage.get("level", "").upper()
        if triage_level == "RED":
            priority["level"] = "urgent"
            priority["factors"].append("red_triage")
        elif triage_level == "AMBER":
            priority["level"] = "high"
            priority["factors"].append("amber_triage")

        # Check detection severity
        detections = context.get("detections", [])
        if detections:
            for detection in detections:
                severity = detection.get("severity", "").lower()
                if "severe" in severity or "critical" in severity:
                    priority["level"] = "urgent"
                    priority["factors"].append("severe_detection")
                    break

        return priority

    def _generate_clinical_hypotheses(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate clinical hypotheses based on available data."""
        hypotheses = []

        detections = context.get("detections", [])
        symptoms = context.get("symptoms", "")

        # Generate hypotheses from detections
        if detections:
            for detection in detections:
                finding = detection.get("finding", "")
                confidence = detection.get("confidence", 0.0)

                hypothesis = {
                    "finding": finding,
                    "hypothesis": f"Based on detection of {finding}",
                    "confidence": confidence,
                    "requires_verification": confidence < 0.8
                }
                hypotheses.append(hypothesis)

        # Generate hypotheses from symptoms
        if symptoms:
            hypothesis = {
                "hypothesis": f"Clinical presentation suggests {symptoms[:100]}...",
                "confidence": 0.7,
                "requires_verification": True
            }
            hypotheses.append(hypothesis)

        return hypotheses

    def _identify_collaboration_needs(self, context: Dict[str, Any]) -> List[str]:
        """Identify when collaboration with other agents is beneficial."""
        needs = []

        # Need vision analysis if no detections
        if not context.get("detections") and context.get("image_data"):
            needs.append("vision_analysis")

        # Need knowledge base for complex cases
        if context.get("detections") and len(context["detections"]) > 2:
            needs.append("knowledge_base_query")

        # Need hospital info for urgent cases
        priority = self._assess_priority(context)
        if priority["level"] in ["urgent", "high"] and not context.get("hospitals"):
            needs.append("hospital_information")

        return needs

    async def _plan_clinical_actions(self, context: Dict[str, Any], reasoning: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Plan clinical actions based on reasoning."""
        actions = []
        situation = reasoning["clinical_situation"]

        if situation == "diagnosis_needed":
            actions.append({
                "action_type": "clinical_generate_diagnosis",
                "description": "Generate clinical diagnosis from detections",
                "priority": 1,
                "confidence": 0.8,
                "required_capabilities": ["clinical_generate_diagnosis"]
            })

        elif situation == "triage_needed":
            actions.append({
                "action_type": "clinical_assess_triage",
                "description": "Assess triage level from diagnosis",
                "priority": 1,
                "confidence": 0.85,
                "required_capabilities": ["clinical_assess_triage"]
            })

        # Address collaboration needs
        for need in reasoning["collaboration_needs"]:
            if need == "vision_analysis":
                actions.append({
                    "action_type": "request_vision_analysis",
                    "description": "Request vision agent to analyze image",
                    "priority": 1,
                    "collaboration": True,
                    "target_agent": "vision_agent"
                })
            elif need == "knowledge_base_query":
                actions.append({
                    "action_type": "request_knowledge_query",
                    "description": "Query knowledge base for additional context",
                    "priority": 2,
                    "collaboration": True,
                    "target_agent": "knowledge_agent"
                })
            elif need == "hospital_information":
                actions.append({
                    "action_type": "request_hospital_info",
                    "description": "Find nearby hospitals for urgent case",
                    "priority": 1,
                    "collaboration": True,
                    "target_agent": "hospital_agent"
                })

        return actions

    async def act(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Execute clinical action."""
        action_type = action.get("action_type")

        if action_type == "clinical_generate_diagnosis":
            return await self._generate_diagnosis(action)
        elif action_type == "clinical_assess_triage":
            return await self._assess_triage(action)
        elif action_type.startswith("request_"):
            return await self._request_collaboration(action)
        else:
            logger.warning("Unknown clinical action: {}", action_type)
            return {"success": False, "error": "Unknown action type"}

    async def _generate_diagnosis(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Generate clinical diagnosis from detections."""
        try:
            # Find the clinical_generate_diagnosis tool
            diagnosis_tool = None
            for tool in ALL_TOOLS:
                if tool.name == "clinical_generate_diagnosis":
                    diagnosis_tool = tool
                    break

            if not diagnosis_tool:
                return {"success": False, "error": "Diagnosis tool not found"}

            # Prepare input
            detections = self.clinical_context.get("detections", [])
            if not detections:
                return {"success": False, "error": "No detections available for diagnosis"}

            # Execute tool
            result = await diagnosis_tool._run({"detections": detections})

            return {
                "success": True,
                "diagnosis": result.get("diagnosis", {}),
                "confidence": result.get("confidence", 0.7)
            }

        except Exception as e:
            logger.error("Clinical diagnosis generation failed: {}", e)
            return {"success": False, "error": str(e)}

    async def _assess_triage(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Assess triage level from diagnosis."""
        try:
            # Find the clinical_assess_triage tool
            triage_tool = None
            for tool in ALL_TOOLS:
                if tool.name == "clinical_assess_triage":
                    triage_tool = tool
                    break

            if not triage_tool:
                return {"success": False, "error": "Triage tool not found"}

            # Prepare input
            diagnosis = self.clinical_context.get("diagnosis", {})
            if not diagnosis:
                return {"success": False, "error": "No diagnosis available for triage"}

            # Execute tool
            result = await triage_tool._run({"diagnosis": diagnosis})

            return {
                "success": True,
                "triage": result.get("triage_result", {}),
                "confidence": result.get("confidence", 0.8)
            }

        except Exception as e:
            logger.error("Clinical triage assessment failed: {}", e)
            return {"success": False, "error": str(e)}

    async def _request_collaboration(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Request collaboration from other agents."""
        target_agent = action.get("target_agent")
        task = {
            "task_type": action["action_type"],
            "description": action["description"],
            "context": self.clinical_context,
            "priority": action.get("priority", 2)
        }

        # This would normally go through the coordinator
        # For now, we'll return a placeholder
        return {
            "success": True,
            "status": "collaboration_requested",
            "target_agent": target_agent,
            "task": task
        }

    def _identify_urgent_tasks(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Identify urgent clinical tasks."""
        tasks = []

        priority = self._assess_priority(context)
        if priority["level"] == "urgent":
            tasks.append({
                "description": "Immediate clinical assessment required",
                "objective": "Complete diagnosis and triage",
                "success_criteria": ["diagnosis_generated", "triage_assessed"]
            })

        return tasks

    def _identify_improvements(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Identify clinical improvement opportunities."""
        improvements = []

        # Check for missed learning opportunities
        completeness = self._assess_information_completeness(context)
        if completeness["overall_score"] < 0.7:
            improvements.append({
                "description": "Improve clinical information gathering",
                "objective": "Achieve higher information completeness",
                "success_criteria": ["completeness_score > 0.8"]
            })

        return improvements

    async def _generate_consensus_assessment(self, topic: Dict[str, Any]) -> Dict[str, Any]:
        """Generate clinical assessment for consensus building."""
        assessment = {
            "agent": "clinical_agent",
            "clinical_assessment": "pending",
            "confidence": 0.85,
            "reasoning": "Clinical expertise assessment",
            "specialist_view": "orthopedic clinical perspective",
            "recommendations": []
        }

        # Add specific clinical insights based on topic
        if topic.get("type") == "diagnosis_consensus":
            assessment["clinical_assessment"] = "Diagnosis verification required"
            assessment["recommendations"].append("Review detection accuracy")
            assessment["recommendations"].append("Consider clinical history")
        elif topic.get("type") == "triage_consensus":
            assessment["clinical_assessment"] = "Triage level assessment"
            assessment["recommendations"].append("Assess urgency factors")
            assessment["recommendations"].append("Consider patient symptoms")

        return assessment