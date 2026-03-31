from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from loguru import logger

from api.schemas.feedback import AgentFeedback, FeedbackResponse, FeedbackSummary
from services.mongo import mongo_service
from services.chat_store import chat_store
from services.agent_learning import adaptive_supervisor
from services.probabilistic_reasoning import (
    confidence_estimator,
    probabilistic_reasoner,
    bayesian_updater
)


@router.get("/feedback/learning/summary")
async def get_learning_summary() -> Dict[str, Any]:
    """
    Get summary of agent learning progress and patterns.

    Provides insights into what the agent has learned from user feedback,
    including successful patterns, failure patterns, and confidence levels.
    """
    try:
        summary = adaptive_supervisor.get_learning_summary()
        return summary
    except Exception as e:
        logger.error("Failed to get learning summary: {}", e)
        raise HTTPException(status_code=500, detail=f"Failed to get learning summary: {str(e)}")


@router.get("/feedback/learning/patterns")
async def get_applicable_patterns(
    body_part: str = Query(None),
    diagnosis_present: bool = Query(False),
    triage_present: bool = Query(False)
) -> Dict[str, Any]:
    """
    Get experience-based patterns applicable to current analysis state.

    Returns patterns that the agent has learned from previous interactions
    that may be relevant to the current analysis.
    """
    try:
        current_state = {
            "body_part": body_part,
            "diagnosis_present": diagnosis_present,
            "triage_present": triage_present,
            "session_context": {}  # Could be enhanced with actual session context
        }

        applicable = adaptive_supervisor.find_applicable_patterns(current_state)
        return {
            "applicable_patterns": applicable,
            "total_available": len(applicable)
        }
    except Exception as e:
        logger.error("Failed to get applicable patterns: {}", e)
        raise HTTPException(status_code=500, detail=f"Failed to get applicable patterns: {str(e)}")


@router.get("/feedback/probabilistic/confidence")
async def get_tool_confidence(
    tool_name: str = Query(...),
    body_part: str = Query(None),
    has_detections: bool = Query(False),
    has_diagnosis: bool = Query(False)
) -> Dict[str, Any]:
    """
    Get confidence estimate for a specific tool in current context.

    Provides probabilistic confidence scores for tool execution based on
    state completeness, learning patterns, and historical performance.
    """
    try:
        state = {
            "body_part": body_part,
            "detections": [] if has_detections else None,
            "diagnosis": {} if has_diagnosis else None
        }

        confidence = confidence_estimator.estimate_tool_confidence(tool_name, state)

        return {
            "tool_name": tool_name,
            "confidence_estimate": round(confidence, 3),
            "state_context": state,
            "interpretation": "high" if confidence >= 0.8 else "moderate" if confidence >= 0.6 else "low"
        }
    except Exception as e:
        logger.error("Failed to get confidence estimate: {}", e)
        raise HTTPException(status_code=500, detail=f"Failed to get confidence estimate: {str(e)}")


@router.get("/feedback/probabilistic/uncertainty")
async def assess_action_uncertainty(
    tool_name: str = Query(...),
    body_part: str = Query(None),
    has_detections: bool = Query(False),
    has_diagnosis: bool = Query(False)
) -> Dict[str, Any]:
    """
    Assess uncertainty level for a potential action.

    Provides uncertainty assessment with recommendations for high-uncertainty
    situations to improve decision quality.
    """
    try:
        state = {
            "body_part": body_part,
            "detections": [] if has_detections else None,
            "diagnosis": {} if has_diagnosis else None
        }

        action = {"name": tool_name, "args": {}}
        uncertainty = probabilistic_reasoner.assess_decision_uncertainty(action, state)

        return uncertainty
    except Exception as e:
        logger.error("Failed to assess uncertainty: {}", e)
        raise HTTPException(status_code=500, detail=f"Failed to assess uncertainty: {str(e)}")


@router.get("/feedback/probabilistic/statistics")
async def get_decision_statistics() -> Dict[str, Any]:
    """
    Get statistics about agent decision-making patterns.

    Provides insights into decision confidence distributions, most commonly
    used tools, and decision-making trends over time.
    """
    try:
        stats = probabilistic_reasoner.get_decision_statistics()
        return stats
    except Exception as e:
        logger.error("Failed to get decision statistics: {}", e)
        raise HTTPException(status_code=500, detail=f"Failed to get decision statistics: {str(e)}")


@router.get("/feedback/beliefs")
async def get_tool_beliefs(
    tool_name: str = Query(None)
) -> Dict[str, Any]:
    """
    Get Bayesian belief estimates about tool effectiveness.

    Provides posterior success probabilities and confidence intervals
    for tool performance based on observed outcomes.
    """
    try:
        if tool_name:
            # Get beliefs for specific tool
            success_prob = bayesian_updater.get_success_probability(tool_name)
            lower, upper = bayesian_updater.get_confidence_interval(tool_name)

            return {
                "tool_name": tool_name,
                "success_probability": round(success_prob, 3),
                "confidence_interval": {
                    "lower": round(lower, 3),
                    "upper": round(upper, 3),
                    "confidence_level": 0.95
                }
            }
        else:
            # Get beliefs for all initialized tools
            all_beliefs = {}
            for tool_name in bayesian_updater.tool_beliefs.keys():
                success_prob = bayesian_updater.get_success_probability(tool_name)
                lower, upper = bayesian_updater.get_confidence_interval(tool_name)

                all_beliefs[tool_name] = {
                    "success_probability": round(success_prob, 3),
                    "confidence_interval": {
                        "lower": round(lower, 3),
                        "upper": round(upper, 3)
                    }
                }

            return {
                "tool_beliefs": all_beliefs,
                "total_tools": len(all_beliefs)
            }
    except Exception as e:
        logger.error("Failed to get tool beliefs: {}", e)
        raise HTTPException(status_code=500, detail=f"Failed to get tool beliefs: {str(e)}")


@router.get("/feedback/learning/summary")
async def get_learning_summary() -> Dict[str, Any]:
    """
    Get summary of agent learning progress and patterns.

    Provides insights into what the agent has learned from user feedback,
    including successful patterns, failure patterns, and confidence levels.
    """
    try:
        summary = adaptive_supervisor.get_learning_summary()
        return summary
    except Exception as e:
        logger.error("Failed to get learning summary: {}", e)
        raise HTTPException(status_code=500, detail=f"Failed to get learning summary: {str(e)}")


@router.get("/feedback/learning/patterns")
async def get_applicable_patterns(
    body_part: str = Query(None),
    diagnosis_present: bool = Query(False),
    triage_present: bool = Query(False)
) -> Dict[str, Any]:
    """
    Get experience-based patterns applicable to current analysis state.

    Returns patterns that the agent has learned from previous interactions
    that may be relevant to the current analysis.
    """
    try:
        current_state = {
            "body_part": body_part,
            "diagnosis_present": diagnosis_present,
            "triage_present": triage_present,
            "session_context": {}  # Could be enhanced with actual session context
        }

        applicable = adaptive_supervisor.find_applicable_patterns(current_state)
        return {
            "applicable_patterns": applicable,
            "total_available": len(applicable)
        }
    except Exception as e:
        logger.error("Failed to get applicable patterns: {}", e)
        raise HTTPException(status_code=500, detail=f"Failed to get applicable patterns: {str(e)}")


router = APIRouter(tags=["feedback"])


async def _analyze_feedback_patterns(feedback: AgentFeedback) -> Dict[str, Any]:
    """Analyze feedback for patterns and learning opportunities."""
    patterns = {
        "improvement_areas": [],
        "success_factors": [],
        "risk_indicators": [],
        "learning_signals": []
    }

    # Decision Quality Analysis
    if feedback.decision_accuracy and feedback.decision_accuracy <= 2:
        patterns["risk_indicators"].append("Low decision accuracy - may need pipeline review")

    if feedback.clinical_relevance and feedback.clinical_relevance <= 2:
        patterns["improvement_areas"].append("Clinical relevance concerns - knowledge base expansion needed")

    if feedback.diagnosis_correctness == "incorrect":
        patterns["risk_indicators"].append("Incorrect diagnosis detected - model recalibration needed")

    # Success Factors
    if feedback.decision_accuracy and feedback.decision_accuracy >= 4:
        patterns["success_factors"].append("High decision accuracy patterns")

    if feedback.overall_satisfaction and feedback.overall_satisfaction >= 4:
        patterns["success_factors"].append("High user satisfaction patterns")

    # Learning Opportunities
    if feedback.missed_findings:
        patterns["learning_signals"].append({
            "type": "missed_findings",
            "count": len(feedback.missed_findings),
            "findings": feedback.missed_findings
        })

    if feedback.incorrect_findings:
        patterns["learning_signals"].append({
            "type": "incorrect_findings",
            "count": len(feedback.incorrect_findings),
            "findings": feedback.incorrect_findings
        })

    if feedback.user_corrections:
        patterns["learning_signals"].append({
            "type": "user_corrections",
            "corrections": feedback.user_corrections
        })

    return patterns


async def _store_feedback_patterns(feedback_id: str, patterns: Dict[str, Any]) -> None:
    """Store analyzed patterns for future learning."""
    if not mongo_service.enabled:
        return

    try:
        collection = mongo_service.get_collection("feedback_patterns")
        await collection.insert_one({
            "feedback_id": feedback_id,
            "patterns": patterns,
            "timestamp": datetime.now(),
            "processed": False  # Mark for future ML processing
        })
        logger.info("Stored feedback patterns for feedback_id={}", feedback_id)
    except Exception as e:
        logger.warning("Failed to store feedback patterns: {}", e)


@router.post("/feedback", response_model=FeedbackResponse)
async def submit_feedback(feedback: AgentFeedback) -> FeedbackResponse:
    """
    Submit feedback on agent decisions and performance.

    This endpoint collects user feedback on agent decision quality, diagnosis accuracy,
    triage appropriateness, and overall satisfaction. The feedback is stored and
    analyzed for patterns to improve agent performance over time.
    """
    if not mongo_service.enabled:
        return FeedbackResponse(
            success=False,
            message="MongoDB not available - feedback not stored"
        )

    try:
        # Validate session exists
        session = await chat_store.get_session(feedback.session_id)
        if not session:
            return FeedbackResponse(
                success=False,
                message="Invalid session ID"
            )

        # Generate feedback ID
        feedback_id = str(uuid4())

        # Analyze feedback patterns
        patterns = await _analyze_feedback_patterns(feedback)

        # Store feedback
        collection = mongo_service.get_collection("agent_feedback")
        feedback_document = {
            "feedback_id": feedback_id,
            "session_id": feedback.session_id,
            "trace_id": feedback.trace_id,
            "ratings": {
                "decision_accuracy": feedback.decision_accuracy,
                "clinical_relevance": feedback.clinical_relevance,
                "response_helpfulness": feedback.response_helpfulness,
                "report_quality": feedback.report_quality,
                "overall_satisfaction": feedback.overall_satisfaction
            },
            "assessments": {
                "diagnosis_correctness": feedback.diagnosis_correctness,
                "triage_appropriateness": feedback.triage_appropriateness
            },
            "corrections": {
                "user_corrections": feedback.user_corrections,
                "missed_findings": feedback.missed_findings,
                "incorrect_findings": feedback.incorrect_findings
            },
            "context": {
                "actor_role": feedback.actor_role,
                "actor_id": feedback.actor_id,
                "would_recommend": feedback.would_recommend,
                "additional_comments": feedback.additional_comments
            },
            "session_context": {
                "patient_id": session.get("patient_id"),
                "doctor_id": session.get("doctor_id"),
                "owner_role": session.get("owner_role")
            },
            "patterns_analysis": patterns,
            "timestamp": datetime.now()
        }

        await collection.insert_one(feedback_document)

        # Store patterns separately for learning
        await _store_feedback_patterns(feedback_id, patterns)

        # Trigger adaptive learning from feedback
        await adaptive_supervisor.learn_from_feedback(feedback_document)

        logger.info("Feedback submitted successfully: feedback_id={}, session_id={}", feedback_id, feedback.session_id)

        return FeedbackResponse(
            success=True,
            feedback_id=feedback_id,
            message="Feedback submitted successfully. Thank you for helping improve OrthoAssist!",
            feedback_analyzed=patterns
        )

    except Exception as e:
        logger.error("Failed to submit feedback: {}", e)
        return FeedbackResponse(
            success=False,
            message=f"Failed to submit feedback: {str(e)}"
        )


@router.get("/feedback/summary", response_model=FeedbackSummary)
async def get_feedback_summary(
    actor_id: str = Query(...),
    actor_role: str = Query(...),
    days: int = Query(30, ge=1, le=90, description="Number of days to analyze")
) -> FeedbackSummary:
    """
    Get summary statistics of feedback for analytics and improvement.

    Provides aggregated feedback metrics including satisfaction scores,
    common corrections, and identified improvement areas.
    """
    if not mongo_service.enabled:
        return FeedbackSummary(
            total_feedback_count=0,
            average_satisfaction=None,
            decision_accuracy_distribution={},
            common_corrections=[],
            improvement_areas=[]
        )

    try:
        collection = mongo_service.get_collection("agent_feedback")

        # Calculate date range
        cutoff_date = datetime.now() - timedelta(days=days) if days > 0 else None

        # Build query
        query = {
            "context.actor_role": actor_role.lower(),
            "context.actor_id": actor_id
        }
        if cutoff_date:
            query["timestamp"] = {"$gte": cutoff_date}

        # Fetch feedback documents
        cursor = collection.find(query)
        feedback_list = await cursor.to_list(length=None)

        if not feedback_list:
            return FeedbackSummary(
                total_feedback_count=0,
                average_satisfaction=None,
                decision_accuracy_distribution={},
                common_corrections=[],
                improvement_areas=[]
            )

        # Calculate statistics
        total_count = len(feedback_list)

        # Average satisfaction
        satisfaction_scores = [
            f.get("ratings", {}).get("overall_satisfaction")
            for f in feedback_list
            if f.get("ratings", {}).get("overall_satisfaction") is not None
        ]
        avg_satisfaction = sum(satisfaction_scores) / len(satisfaction_scores) if satisfaction_scores else None

        # Decision accuracy distribution
        accuracy_scores = {}
        for f in feedback_list:
            accuracy = f.get("ratings", {}).get("decision_accuracy")
            if accuracy is not None:
                accuracy_label = f"Level {accuracy}"
                accuracy_scores[accuracy_label] = accuracy_scores.get(accuracy_label, 0) + 1

        # Common corrections
        missed_findings = []
        incorrect_findings = []
        for f in feedback_list:
            corrections = f.get("corrections", {})
            if corrections.get("missed_findings"):
                missed_findings.extend(corrections["missed_findings"])
            if corrections.get("incorrect_findings"):
                incorrect_findings.extend(corrections["incorrect_findings"])

        # Count common findings
        from collections import Counter
        common_missed = [item for item, count in Counter(missed_findings).most_common(5)]
        common_incorrect = [item for item, count in Counter(incorrect_findings).most_common(5)]

        # Improvement areas
        improvement_areas = set()
        for f in feedback_list:
            patterns = f.get("patterns_analysis", {})
            for area in patterns.get("improvement_areas", []):
                improvement_areas.add(area)
            if f.get("ratings", {}).get("decision_accuracy", 5) <= 2:
                improvement_areas.add("Low decision accuracy instances")

        return FeedbackSummary(
            total_feedback_count=total_count,
            average_satisfaction=avg_satisfaction,
            decision_accuracy_distribution=accuracy_scores,
            common_corrections=common_missed + common_incorrect,
            improvement_areas=list(improvement_areas)
        )

    except Exception as e:
        logger.error("Failed to get feedback summary: {}", e)
        raise HTTPException(status_code=500, detail=f"Failed to get feedback summary: {str(e)}")


@router.get("/feedback/session/{session_id}")
async def get_session_feedback(
    session_id: str,
    actor_id: str = Query(...),
    actor_role: str = Query(...),
) -> Dict[str, Any]:
    """Get all feedback for a specific session."""
    if not mongo_service.enabled:
        return {"feedback": [], "count": 0}

    try:
        collection = mongo_service.get_collection("agent_feedback")
        query = {
            "session_id": session_id,
            "context.actor_id": actor_id,
            "context.actor_role": actor_role.lower()
        }

        cursor = collection.find(query)
        feedback_list = await cursor.to_list(length=None)

        # Remove sensitive data and MongoDB IDs
        cleaned_feedback = []
        for feedback in feedback_list:
            clean_item = {k: v for k, v in feedback.items() if k != "_id"}
            cleaned_feedback.append(clean_item)

        return {
            "feedback": cleaned_feedback,
            "count": len(cleaned_feedback)
        }

    except Exception as e:
        logger.error("Failed to get session feedback: {}", e)
        raise HTTPException(status_code=500, detail=f"Failed to get session feedback: {str(e)}")