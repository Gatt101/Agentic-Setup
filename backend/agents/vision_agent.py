from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional
from datetime import datetime

from loguru import logger

from agents.base_agent import BaseAgent, AgentCapabilities, AgentGoal, AgentMessage
from tools import ALL_TOOLS


class VisionAgent(BaseAgent):
    """Autonomous vision analysis agent specializing in medical imaging."""

    def __init__(self):
        capabilities = AgentCapabilities(
            agent_name="vision_agent",
            tool_capabilities=[
                "vision_detect_body_part",
                "vision_detect_hand_fracture",
                "vision_detect_leg_fracture",
                "vision_annotate_image"
            ],
            perception_abilities=["vision", "structured_data"],
            reasoning_level="advanced",
            collaboration_style="cooperative",
            specialization_domains=["medical_imaging", "computer_vision", "xray_analysis"],
            confidence_ranges={
                "vision_detect_body_part": (0.9, 0.98),
                "vision_detect_hand_fracture": (0.8, 0.92),
                "vision_detect_leg_fracture": (0.8, 0.92),
                "vision_annotate_image": (0.85, 0.95)
            },
            max_concurrent_tasks=2
        )

        super().__init__(capabilities)
        self.image_analysis_history = {}
        self.quality_assessment = {}

    async def perceive(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Perceive visual information and image data."""
        perceptions = {
            "image_data": context.get("image_data"),
            "image_quality": await self._assess_image_quality(context.get("image_data")),
            "existing_detections": context.get("detections"),
            "body_part": context.get("body_part"),
            "session_id": context.get("session_id")
        }

        # Store in analysis history
        session_id = context.get("session_id", "unknown")
        if perceptions["image_data"]:
            self.image_analysis_history[session_id] = self.image_analysis_history.get(session_id, {})
            self.image_analysis_history[session_id]["last_image_timestamp"] = datetime.now()
            self.image_analysis_history[session_id]["image_quality"] = perceptions["image_quality"]

        logger.info(
            "Vision agent perceived: quality={}, existing_detections={}, body_part={}",
            perceptions["image_quality"].get("overall_quality", "unknown"),
            len(perceptions.get("existing_detections", [])),
            perceptions.get("body_part")
        )

        return perceptions

    async def reason(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Reason about image analysis requirements and approach."""
        reasoning = {
            "analysis_status": self._assess_analysis_status(context),
            "image_quality_assessment": self._assess_image_quality(context.get("image_data")),
            "required_analyses": self._determine_required_analyses(context),
            "confidence_expectations": self._estimate_confidence_expectations(context),
            "collaboration_needs": self._identify_vision_collaboration_needs(context),
            "recommended_actions": []
        }

        # Plan recommended actions
        reasoning["recommended_actions"] = await self._plan_vision_actions(context, reasoning)

        logger.info(
            "Vision agent reasoning: status={}, quality={}, actions={}",
            reasoning["analysis_status"],
            reasoning["image_quality_assessment"].get("overall_quality", "unknown"),
            [a.get("action_type") for a in reasoning["recommended_actions"]]
        )

        return reasoning

    async def _assess_image_quality(self, image_data: Optional[str]) -> Dict[str, Any]:
        """Assess quality of medical image."""
        if not image_data:
            return {
                "overall_quality": "no_image",
                "clarity": "unknown",
                "adequate_for_analysis": False,
                "issues": ["no_image_provided"]
            }

        # Basic quality assessment (in real implementation, would use CV algorithms)
        assessment = {
            "overall_quality": "adequate",
            "clarity": "good",
            "adequate_for_analysis": True,
            "issues": [],
            "confidence_factor": 1.0
        }

        # Check for common issues
        if len(image_data) < 1000:  # Very short base64 string
            assessment["overall_quality"] = "poor"
            assessment["clarity"] = "poor"
            assessment["adequate_for_analysis"] = False
            assessment["issues"].append("image_size_too_small")
            assessment["confidence_factor"] = 0.5

        return assessment

    def _assess_analysis_status(self, context: Dict[str, Any]) -> str:
        """Assess current analysis status."""
        image_data = context.get("image_data")
        body_part = context.get("body_part")
        detections = context.get("detections")

        if not image_data:
            return "no_image_available"

        if image_data and not body_part:
            return "body_part_detection_needed"

        if body_part and not detections:
            return f"{body_part}_fracture_detection_needed"

        if detections:
            return "analysis_complete"

        return "analysis_ready"

    def _determine_required_analyses(self, context: Dict[str, Any]) -> List[str]:
        """Determine what vision analyses are needed."""
        required = []

        image_data = context.get("image_data")
        if not image_data:
            return required

        body_part = context.get("body_part")

        if not body_part:
            required.append("body_part_detection")
        elif body_part == "hand":
            required.append("hand_fracture_detection")
        elif body_part == "leg":
            required.append("leg_fracture_detection")

        # Always consider annotation if detections exist
        if context.get("detections"):
            required.append("image_annotation")

        return required

    def _estimate_confidence_expectations(self, context: Dict[str, Any]) -> Dict[str, float]:
        """Estimate expected confidence levels for different analyses."""
        expectations = {}

        quality = self._assess_image_quality(context.get("image_data"))
        quality_factor = quality.get("confidence_factor", 1.0)

        body_part = context.get("body_part")

        # Base confidence estimates adjusted by quality
        if body_part == "hand":
            expectations["hand_fracture_detection"] = 0.85 * quality_factor
        elif body_part == "leg":
            expectations["leg_fracture_detection"] = 0.85 * quality_factor
        else:
            expectations["body_part_detection"] = 0.95 * quality_factor

        expectations["image_annotation"] = 0.9 * quality_factor

        return expectations

    def _identify_vision_collaboration_needs(self, context: Dict[str, Any]) -> List[str]:
        """Identify when vision agent needs collaboration."""
        needs = []

        # Need clinical input if low confidence detections
        detections = context.get("detections", [])
        if detections:
            low_confidence_detections = [
                d for d in detections
                if d.get("confidence", 1.0) < 0.7
            ]
            if low_confidence_detections:
                needs.append("clinical_verification")

        # Need better quality image if quality is poor
        quality = self._assess_image_quality(context.get("image_data"))
        if quality.get("overall_quality") == "poor":
            needs.append("image_quality_improvement")

        return needs

    async def _plan_vision_actions(self, context: Dict[str, Any], reasoning: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Plan vision analysis actions."""
        actions = []
        status = reasoning["analysis_status"]

        if status == "body_part_detection_needed":
            actions.append({
                "action_type": "vision_detect_body_part",
                "description": "Detect body part from X-ray image",
                "priority": 1,
                "confidence": 0.95,
                "required_capabilities": ["vision_detect_body_part"]
            })

        elif status == "hand_fracture_detection_needed":
            actions.append({
                "action_type": "vision_detect_hand_fracture",
                "description": "Detect hand fractures from X-ray",
                "priority": 1,
                "confidence": reasoning["confidence_expectations"].get("hand_fracture_detection", 0.85),
                "required_capabilities": ["vision_detect_hand_fracture"]
            })

        elif status == "leg_fracture_detection_needed":
            actions.append({
                "action_type": "vision_detect_leg_fracture",
                "description": "Detect leg fractures from X-ray",
                "priority": 1,
                "confidence": reasoning["confidence_expectations"].get("leg_fracture_detection", 0.85),
                "required_capabilities": ["vision_detect_leg_fracture"]
            })

        elif status == "analysis_complete":
            # Consider annotation
            actions.append({
                "action_type": "vision_annotate_image",
                "description": "Annotate X-ray with detection results",
                "priority": 2,
                "confidence": reasoning["confidence_expectations"].get("image_annotation", 0.9),
                "required_capabilities": ["vision_annotate_image"]
            })

        # Address collaboration needs
        for need in reasoning["collaboration_needs"]:
            if need == "clinical_verification":
                actions.append({
                    "action_type": "request_clinical_verification",
                    "description": "Request clinical agent to verify low-confidence detections",
                    "priority": 1,
                    "collaboration": True,
                    "target_agent": "clinical_agent"
                })
            elif need == "image_quality_improvement":
                actions.append({
                    "action_type": "request_better_image",
                    "description": "Request user to provide higher quality image",
                    "priority": 1,
                    "user_interaction": True
                })

        return actions

    async def act(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Execute vision analysis action."""
        action_type = action.get("action_type")

        if action_type.startswith("vision_"):
            return await self._execute_vision_tool(action)
        elif action_type.startswith("request_"):
            return await self._request_collaboration(action)
        else:
            logger.warning("Unknown vision action: {}", action_type)
            return {"success": False, "error": "Unknown action type"}

    async def _execute_vision_tool(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Execute vision analysis tool."""
        action_type = action.get("action_type")

        # Find the appropriate tool
        vision_tool = None
        for tool in ALL_TOOLS:
            if tool.name == action_type:
                vision_tool = tool
                break

        if not vision_tool:
            return {"success": False, "error": f"Vision tool {action_type} not found"}

        try:
            # Prepare input
            image_data = self.clinical_context.get("image_data")
            if not image_data:
                return {"success": False, "error": "No image data available"}

            # Execute tool
            result = await vision_tool._run({"image_data": image_data})

            # Update confidence with quality factor
            quality_assessment = self._assess_image_quality(image_data)
            quality_factor = quality_assessment.get("confidence_factor", 1.0)

            # Adjust result confidence if provided
            if "confidence" in result:
                result["adjusted_confidence"] = result["confidence"] * quality_factor

            return {
                "success": True,
                "result": result,
                "quality_factor": quality_factor
            }

        except Exception as e:
            logger.error("Vision tool execution failed: {}", e)
            return {"success": False, "error": str(e)}

    async def _request_collaboration(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Request collaboration from other agents."""
        target_agent = action.get("target_agent")
        task = {
            "task_type": action["action_type"],
            "description": action["description"],
            "context": {
                "detections": self.clinical_context.get("existing_detections"),
                "image_quality": self._assess_image_quality(self.clinical_context.get("image_data"))
            },
            "priority": action.get("priority", 2)
        }

        return {
            "success": True,
            "status": "collaboration_requested",
            "target_agent": target_agent,
            "task": task
        }

    def _identify_urgent_tasks(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Identify urgent vision analysis tasks."""
        tasks = []

        # Urgent if poor image quality
        quality = self._assess_image_quality(context.get("image_data"))
        if quality.get("overall_quality") == "poor":
            tasks.append({
                "description": "Improve image quality for analysis",
                "objective": "Obtain higher quality medical image",
                "success_criteria": ["quality_adequate_for_analysis"]
            })

        return tasks

    def _identify_improvements(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Identify vision analysis improvement opportunities."""
        improvements = []

        # Check for learning opportunities from previous analyses
        session_id = context.get("session_id")
        if session_id and session_id in self.image_analysis_history:
            history = self.image_analysis_history[session_id]
            if history.get("image_quality", {}).get("overall_quality") == "poor":
                improvements.append({
                    "description": "Improve image quality assessment",
                    "objective": "Develop better quality metrics",
                    "success_criteria": ["accuracy_improvement", "fewer_false_negatives"]
                })

        return improvements

    async def _generate_consensus_assessment(self, topic: Dict[str, Any]) -> Dict[str, Any]:
        """Generate vision assessment for consensus building."""
        assessment = {
            "agent": "vision_agent",
            "visual_assessment": "pending_detailed_analysis",
            "confidence": 0.9,
            "reasoning": "Computer vision analysis perspective",
            "specialist_view": "medical imaging analysis",
            "recommendations": []
        }

        # Add specific vision insights based on topic
        if topic.get("type") == "detection_consensus":
            assessment["visual_assessment"] = "Detection verification required"
            assessment["recommendations"].append("Review image quality factors")
            assessment["recommendations"].append("Consider detection confidence thresholds")
        elif topic.get("type") == "findings_consensus":
            assessment["visual_assessment"] = "Visual findings validation"
            assessment["recommendations"].append("Cross-reference with clinical presentation")
            assessment["recommendations"].append("Verify anatomical accuracy")

        return assessment