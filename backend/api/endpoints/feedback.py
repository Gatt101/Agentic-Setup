from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta
from typing import Any, Dict
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from loguru import logger

from api.schemas.feedback import AgentFeedback, FeedbackResponse, FeedbackSummary
from services.agent_learning import adaptive_supervisor
from services.chat_store import chat_store
from services.mongo import mongo_service
from services.probabilistic_reasoning import (
    bayesian_updater,
    confidence_estimator,
    probabilistic_reasoner,
)


router = APIRouter(tags=["feedback"])


async def _analyze_feedback_patterns(feedback: AgentFeedback) -> Dict[str, Any]:
    patterns = {
        "improvement_areas": [],
        "success_factors": [],
        "risk_indicators": [],
        "learning_signals": [],
    }

    if feedback.decision_accuracy and feedback.decision_accuracy <= 2:
        patterns["risk_indicators"].append("Low decision accuracy - review orchestration and tool selection")

    if feedback.clinical_relevance and feedback.clinical_relevance <= 2:
        patterns["improvement_areas"].append("Clinical relevance concerns - improve clinical context usage")

    if feedback.diagnosis_correctness == "incorrect":
        patterns["risk_indicators"].append("Incorrect diagnosis detected - model and workflow recalibration needed")

    if feedback.triage_appropriateness == "inappropriate":
        patterns["risk_indicators"].append("Triage mismatch detected - review urgency heuristics")

    if feedback.decision_accuracy and feedback.decision_accuracy >= 4:
        patterns["success_factors"].append("High decision accuracy")

    if feedback.overall_satisfaction and feedback.overall_satisfaction >= 4:
        patterns["success_factors"].append("High user satisfaction")

    if feedback.missed_findings:
        patterns["learning_signals"].append(
            {"type": "missed_findings", "count": len(feedback.missed_findings), "findings": feedback.missed_findings}
        )

    if feedback.incorrect_findings:
        patterns["learning_signals"].append(
            {
                "type": "incorrect_findings",
                "count": len(feedback.incorrect_findings),
                "findings": feedback.incorrect_findings,
            }
        )

    if feedback.user_corrections:
        patterns["learning_signals"].append(
            {"type": "user_corrections", "corrections": feedback.user_corrections}
        )

    return patterns


async def _store_feedback_patterns(feedback_id: str, patterns: Dict[str, Any]) -> None:
    if not mongo_service.enabled:
        return

    try:
        collection = mongo_service.get_collection("feedback_patterns")
        await collection.insert_one(
            {
                "feedback_id": feedback_id,
                "patterns": patterns,
                "timestamp": datetime.now(),
                "processed": False,
            }
        )
    except Exception as e:
        logger.warning("Failed to store feedback patterns for {}: {}", feedback_id, e)


@router.post("/feedback", response_model=FeedbackResponse)
async def submit_feedback(feedback: AgentFeedback) -> FeedbackResponse:
    if not mongo_service.enabled:
        return FeedbackResponse(success=False, message="MongoDB not available - feedback not stored")

    try:
        session = await chat_store.get_session(feedback.session_id)
        if not session:
            return FeedbackResponse(success=False, message="Invalid session ID")

        trace_snapshot = await chat_store.get_trace(feedback.session_id)
        feedback_id = str(uuid4())
        patterns = await _analyze_feedback_patterns(feedback)

        feedback_document = {
            "feedback_id": feedback_id,
            "session_id": feedback.session_id,
            "trace_id": feedback.trace_id,
            "decision_accuracy": feedback.decision_accuracy,
            "clinical_relevance": feedback.clinical_relevance,
            "response_helpfulness": feedback.response_helpfulness,
            "report_quality": feedback.report_quality,
            "overall_satisfaction": feedback.overall_satisfaction,
            "diagnosis_correctness": feedback.diagnosis_correctness,
            "triage_appropriateness": feedback.triage_appropriateness,
            "user_corrections": feedback.user_corrections,
            "missed_findings": feedback.missed_findings or [],
            "incorrect_findings": feedback.incorrect_findings or [],
            "ratings": {
                "decision_accuracy": feedback.decision_accuracy,
                "clinical_relevance": feedback.clinical_relevance,
                "response_helpfulness": feedback.response_helpfulness,
                "report_quality": feedback.report_quality,
                "overall_satisfaction": feedback.overall_satisfaction,
            },
            "assessments": {
                "diagnosis_correctness": feedback.diagnosis_correctness,
                "triage_appropriateness": feedback.triage_appropriateness,
            },
            "corrections": {
                "user_corrections": feedback.user_corrections,
                "missed_findings": feedback.missed_findings or [],
                "incorrect_findings": feedback.incorrect_findings or [],
            },
            "context": {
                "actor_role": feedback.actor_role.lower(),
                "actor_id": feedback.actor_id,
                "would_recommend": feedback.would_recommend,
                "additional_comments": feedback.additional_comments,
            },
            "session_context": {
                "patient_id": session.get("patient_id"),
                "doctor_id": session.get("doctor_id"),
                "owner_role": session.get("owner_role"),
                "trace_status": trace_snapshot.get("status"),
                "trace_event_count": len(trace_snapshot.get("trace", [])),
            },
            "trace_snapshot": trace_snapshot.get("trace", []),
            "patterns_analysis": patterns,
            "timestamp": datetime.now(),
        }

        collection = mongo_service.get_collection("agent_feedback")
        await collection.insert_one(feedback_document)
        await _store_feedback_patterns(feedback_id, patterns)
        await adaptive_supervisor.learn_from_feedback(feedback_document)

        logger.info(
            "Feedback submitted successfully: feedback_id={} session_id={}",
            feedback_id,
            feedback.session_id,
        )

        return FeedbackResponse(
            success=True,
            feedback_id=feedback_id,
            message="Feedback submitted successfully.",
            feedback_analyzed=patterns,
        )
    except Exception as e:
        logger.error("Failed to submit feedback: {}", e)
        return FeedbackResponse(success=False, message=f"Failed to submit feedback: {str(e)}")


@router.get("/feedback/summary", response_model=FeedbackSummary)
async def get_feedback_summary(
    actor_id: str = Query(...),
    actor_role: str = Query(...),
    days: int = Query(30, ge=1, le=90),
) -> FeedbackSummary:
    if not mongo_service.enabled:
        return FeedbackSummary(
            total_feedback_count=0,
            average_satisfaction=None,
            decision_accuracy_distribution={},
            common_corrections=[],
            improvement_areas=[],
        )

    try:
        collection = mongo_service.get_collection("agent_feedback")
        query: Dict[str, Any] = {
            "context.actor_id": actor_id,
            "context.actor_role": actor_role.lower(),
        }
        if days > 0:
            query["timestamp"] = {"$gte": datetime.now() - timedelta(days=days)}

        feedback_list = await collection.find(query).to_list(length=None)
        if not feedback_list:
            return FeedbackSummary(
                total_feedback_count=0,
                average_satisfaction=None,
                decision_accuracy_distribution={},
                common_corrections=[],
                improvement_areas=[],
            )

        satisfaction_scores = [
            item.get("overall_satisfaction")
            for item in feedback_list
            if item.get("overall_satisfaction") is not None
        ]
        decision_accuracy_distribution: Dict[str, int] = {}
        missed_findings: list[str] = []
        incorrect_findings: list[str] = []
        improvement_areas: set[str] = set()

        for item in feedback_list:
            accuracy = item.get("decision_accuracy")
            if accuracy is not None:
                label = f"Level {accuracy}"
                decision_accuracy_distribution[label] = decision_accuracy_distribution.get(label, 0) + 1

            missed_findings.extend(item.get("missed_findings") or [])
            incorrect_findings.extend(item.get("incorrect_findings") or [])
            for area in item.get("patterns_analysis", {}).get("improvement_areas", []):
                improvement_areas.add(area)

        common_corrections = [
            finding for finding, _count in Counter(missed_findings + incorrect_findings).most_common(10)
        ]

        average_satisfaction = (
            sum(satisfaction_scores) / len(satisfaction_scores) if satisfaction_scores else None
        )

        return FeedbackSummary(
            total_feedback_count=len(feedback_list),
            average_satisfaction=average_satisfaction,
            decision_accuracy_distribution=decision_accuracy_distribution,
            common_corrections=common_corrections,
            improvement_areas=sorted(improvement_areas),
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
    if not mongo_service.enabled:
        return {"feedback": [], "count": 0}

    try:
        collection = mongo_service.get_collection("agent_feedback")
        feedback_list = await collection.find(
            {
                "session_id": session_id,
                "context.actor_id": actor_id,
                "context.actor_role": actor_role.lower(),
            }
        ).to_list(length=None)

        cleaned = [{k: v for k, v in item.items() if k != "_id"} for item in feedback_list]
        return {"feedback": cleaned, "count": len(cleaned)}
    except Exception as e:
        logger.error("Failed to get session feedback: {}", e)
        raise HTTPException(status_code=500, detail=f"Failed to get session feedback: {str(e)}")


@router.get("/feedback/learning/summary")
async def get_learning_summary() -> Dict[str, Any]:
    try:
        return adaptive_supervisor.get_learning_summary()
    except Exception as e:
        logger.error("Failed to get learning summary: {}", e)
        raise HTTPException(status_code=500, detail=f"Failed to get learning summary: {str(e)}")


@router.get("/feedback/learning/patterns")
async def get_applicable_patterns(
    body_part: str | None = Query(None),
    diagnosis_present: bool = Query(False),
    triage_present: bool = Query(False),
) -> Dict[str, Any]:
    try:
        current_state = {
            "body_part": body_part,
            "diagnosis_present": diagnosis_present,
            "triage_present": triage_present,
            "session_context": {},
        }
        applicable = adaptive_supervisor.find_applicable_patterns(current_state)
        return {"applicable_patterns": applicable, "total_available": len(applicable)}
    except Exception as e:
        logger.error("Failed to get applicable patterns: {}", e)
        raise HTTPException(status_code=500, detail=f"Failed to get applicable patterns: {str(e)}")


@router.get("/feedback/probabilistic/confidence")
async def get_tool_confidence(
    tool_name: str = Query(...),
    body_part: str | None = Query(None),
    has_detections: bool = Query(False),
    has_diagnosis: bool = Query(False),
) -> Dict[str, Any]:
    try:
        state = {
            "body_part": body_part,
            "detections": [] if has_detections else None,
            "diagnosis": {} if has_diagnosis else None,
        }
        confidence = confidence_estimator.estimate_tool_confidence(tool_name, state)
        return {
            "tool_name": tool_name,
            "confidence_estimate": round(confidence, 3),
            "state_context": state,
            "interpretation": "high" if confidence >= 0.8 else "moderate" if confidence >= 0.6 else "low",
        }
    except Exception as e:
        logger.error("Failed to get confidence estimate: {}", e)
        raise HTTPException(status_code=500, detail=f"Failed to get confidence estimate: {str(e)}")


@router.get("/feedback/probabilistic/uncertainty")
async def assess_action_uncertainty(
    tool_name: str = Query(...),
    body_part: str | None = Query(None),
    has_detections: bool = Query(False),
    has_diagnosis: bool = Query(False),
) -> Dict[str, Any]:
    try:
        state = {
            "body_part": body_part,
            "detections": [] if has_detections else None,
            "diagnosis": {} if has_diagnosis else None,
        }
        return probabilistic_reasoner.assess_decision_uncertainty({"name": tool_name, "args": {}}, state)
    except Exception as e:
        logger.error("Failed to assess uncertainty: {}", e)
        raise HTTPException(status_code=500, detail=f"Failed to assess uncertainty: {str(e)}")


@router.get("/feedback/probabilistic/statistics")
async def get_decision_statistics() -> Dict[str, Any]:
    try:
        return probabilistic_reasoner.get_decision_statistics()
    except Exception as e:
        logger.error("Failed to get decision statistics: {}", e)
        raise HTTPException(status_code=500, detail=f"Failed to get decision statistics: {str(e)}")


@router.get("/feedback/beliefs")
async def get_tool_beliefs(tool_name: str | None = Query(None)) -> Dict[str, Any]:
    try:
        if tool_name:
            success_probability = bayesian_updater.get_success_probability(tool_name)
            lower, upper = bayesian_updater.get_confidence_interval(tool_name)
            return {
                "tool_name": tool_name,
                "success_probability": round(success_probability, 3),
                "confidence_interval": {
                    "lower": round(lower, 3),
                    "upper": round(upper, 3),
                    "confidence_level": 0.95,
                },
            }

        all_beliefs = {}
        for current_tool_name in bayesian_updater.tool_beliefs.keys():
            success_probability = bayesian_updater.get_success_probability(current_tool_name)
            lower, upper = bayesian_updater.get_confidence_interval(current_tool_name)
            all_beliefs[current_tool_name] = {
                "success_probability": round(success_probability, 3),
                "confidence_interval": {"lower": round(lower, 3), "upper": round(upper, 3)},
            }

        return {"tool_beliefs": all_beliefs, "total_tools": len(all_beliefs)}
    except Exception as e:
        logger.error("Failed to get tool beliefs: {}", e)
        raise HTTPException(status_code=500, detail=f"Failed to get tool beliefs: {str(e)}")
