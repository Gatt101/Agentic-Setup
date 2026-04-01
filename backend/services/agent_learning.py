from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from loguru import logger
from collections import defaultdict, Counter

from services.mongo import mongo_service


class ExperiencePattern:
    """Represents a learned pattern from agent experience."""

    def __init__(self, pattern_id: str, pattern_type: str, pattern_data: Dict[str, Any]):
        self.pattern_id = pattern_id
        self.pattern_type = pattern_type  # 'success', 'failure', 'optimization'
        self.pattern_data = pattern_data
        self.success_count = 0
        self.failure_count = 0
        self.confidence = 0.0
        self.last_applied = None
        self.created_at = datetime.now()


class AdaptiveSupervisor:
    """Enhanced supervisor with experience-based learning capabilities."""

    def __init__(self):
        self.experience_patterns: Dict[str, ExperiencePattern] = {}
        self.successful_sequences: List[Dict[str, Any]] = []
        self.failed_sequences: List[Dict[str, Any]] = []
        self.learning_enabled = True
        self.last_learning_update = None
        self._initialized = False

        # Don't load patterns during import to prevent startup issues
        logger.info("Adaptive supervisor ready (lazy initialization)")

    async def ensure_initialized(self) -> None:
        """Ensure the supervisor is initialized before operations."""
        if not self._initialized:
            logger.info("Ensuring adaptive supervisor is initialized...")
            # Delay Mongo-backed loading until the service is fully initialized.
            if mongo_service.enabled and getattr(mongo_service, "_db", None) is not None:
                await self._load_existing_patterns()
            self._initialized = True

    async def _load_existing_patterns(self) -> None:
        """Load existing experience patterns from storage."""
        if not mongo_service.enabled:
            logger.info("MongoDB not available - starting without existing patterns")
            return
        if getattr(mongo_service, "_db", None) is None:
            logger.info("MongoDB not initialized yet - skipping pattern preload")
            return

        try:
            collection = mongo_service.get_collection("agent_patterns")
            patterns = await collection.find({}).to_list(length=None)
            for pattern_doc in patterns:
                pattern_id = pattern_doc.get("pattern_id")
                if pattern_id:
                    pattern = ExperiencePattern(
                        pattern_id=pattern_id,
                        pattern_type=pattern_doc.get("pattern_type", "success"),
                        pattern_data=pattern_doc.get("pattern_data", {})
                    )
                    pattern.success_count = pattern_doc.get("success_count", 0)
                    pattern.failure_count = pattern_doc.get("failure_count", 0)
                    pattern.confidence = pattern_doc.get("confidence", 0.0)
                    pattern.last_applied = pattern_doc.get("last_applied")
                    self.experience_patterns[pattern_id] = pattern

            logger.info("Loaded {} experience patterns", len(self.experience_patterns))

        except Exception as e:
            logger.warning("Failed to load existing patterns: {}", e)

    async def learn_from_feedback(self, feedback: Dict[str, Any]) -> None:
        """Extract learning signals from user feedback."""
        if not self.learning_enabled or not mongo_service.enabled:
            return

        try:
            normalized_feedback = self._normalize_feedback(feedback)
            patterns_to_update = []

            # Learn from incorrect diagnoses
            if normalized_feedback.get("diagnosis_correctness") == "incorrect":
                await self._learn_from_correction(normalized_feedback, "diagnosis")

            # Learn from triage mismatches
            if normalized_feedback.get("triage_appropriateness") == "inappropriate":
                await self._learn_from_correction(normalized_feedback, "triage")

            # Learn from low ratings
            if normalized_feedback.get("decision_accuracy", 5) <= 2:
                await self._learn_from_low_performance(normalized_feedback)

            # Learn from high performance
            if normalized_feedback.get("decision_accuracy", 0) >= 4:
                await self._learn_from_high_performance(normalized_feedback)

            # Analyze missed findings
            missed_findings = normalized_feedback.get("missed_findings", [])
            if missed_findings:
                await self._learn_from_missed_findings(normalized_feedback, missed_findings)

            # Analyze incorrect findings
            incorrect_findings = normalized_feedback.get("incorrect_findings", [])
            if incorrect_findings:
                await self._learn_from_incorrect_findings(normalized_feedback, incorrect_findings)

            self.last_learning_update = datetime.now()
            logger.info("Learning completed from feedback_id={}", normalized_feedback.get("feedback_id"))

        except Exception as e:
            logger.error("Failed to learn from feedback: {}", e)

    async def learn_from_execution(self, execution_state: Dict[str, Any]) -> None:
        """Learn from live agent executions even before explicit user feedback arrives."""
        if not self.learning_enabled or not mongo_service.enabled:
            return

        try:
            tool_outcomes = execution_state.get("tool_execution_outcomes") or []
            if not isinstance(tool_outcomes, list):
                tool_outcomes = []

            session_context = self._build_execution_context(execution_state)
            for outcome in tool_outcomes:
                if not isinstance(outcome, dict):
                    continue

                tool_name = str(outcome.get("tool_name") or "").strip()
                if not tool_name:
                    continue

                if outcome.get("success"):
                    continue

                error_key = self._normalize_error_key(outcome.get("error"))
                await self._upsert_pattern(
                    pattern_id=f"tool_failure::{tool_name}::{error_key}",
                    pattern_type="failure",
                    pattern_data={
                        "type": "tool_failure",
                        "tool_name": tool_name,
                        "error": error_key,
                        "session_context": session_context,
                    },
                    success=False,
                )

            pipeline_complete = bool(execution_state.get("diagnosis")) and bool(execution_state.get("triage_result"))
            if pipeline_complete:
                tool_sequence = [
                    str(tool_name)
                    for tool_name in execution_state.get("tool_calls_made", [])
                    if isinstance(tool_name, str) and tool_name
                ]
                sequence_key = "__".join(tool_sequence[-6:]) or "no_tools_recorded"
                await self._upsert_pattern(
                    pattern_id=f"success_sequence::{sequence_key}",
                    pattern_type="success",
                    pattern_data={
                        "type": "successful_sequence",
                        "tool_sequence": tool_sequence,
                        "session_context": session_context,
                        "consensus_used": bool(
                            (execution_state.get("multi_agent_coordination") or {}).get("consensus_reached")
                        ),
                    },
                    success=True,
                )

            self.last_learning_update = datetime.now()
            logger.info(
                "Execution learning completed for session_id={}",
                execution_state.get("session_id", "unknown"),
            )
        except Exception as e:
            logger.error("Failed to learn from execution: {}", e)

    def _normalize_feedback(self, feedback: Dict[str, Any]) -> Dict[str, Any]:
        """Support both flat feedback payloads and stored nested feedback documents."""
        ratings = feedback.get("ratings") if isinstance(feedback.get("ratings"), dict) else {}
        assessments = feedback.get("assessments") if isinstance(feedback.get("assessments"), dict) else {}
        corrections = feedback.get("corrections") if isinstance(feedback.get("corrections"), dict) else {}
        context = feedback.get("context") if isinstance(feedback.get("context"), dict) else {}

        normalized = dict(feedback)
        normalized.setdefault("decision_accuracy", ratings.get("decision_accuracy"))
        normalized.setdefault("clinical_relevance", ratings.get("clinical_relevance"))
        normalized.setdefault("response_helpfulness", ratings.get("response_helpfulness"))
        normalized.setdefault("report_quality", ratings.get("report_quality"))
        normalized.setdefault("overall_satisfaction", ratings.get("overall_satisfaction"))
        normalized.setdefault("diagnosis_correctness", assessments.get("diagnosis_correctness"))
        normalized.setdefault("triage_appropriateness", assessments.get("triage_appropriateness"))
        normalized.setdefault("missed_findings", corrections.get("missed_findings") or [])
        normalized.setdefault("incorrect_findings", corrections.get("incorrect_findings") or [])
        normalized.setdefault("user_corrections", corrections.get("user_corrections"))
        normalized.setdefault("actor_role", context.get("actor_role"))
        normalized.setdefault("actor_id", context.get("actor_id"))
        return normalized

    def _build_execution_context(self, execution_state: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "body_part": execution_state.get("body_part"),
            "actor_role": execution_state.get("actor_role"),
            "has_image": bool(execution_state.get("image_data")),
            "has_diagnosis": bool(execution_state.get("diagnosis")),
            "has_triage": bool(execution_state.get("triage_result")),
            "multi_agent_enabled": bool(execution_state.get("multi_agent_enabled")),
        }

    def _normalize_error_key(self, error: Any) -> str:
        value = str(error or "unknown_error").strip().lower()
        return value.replace(" ", "_")[:80]

    async def _upsert_pattern(
        self,
        pattern_id: str,
        pattern_type: str,
        pattern_data: Dict[str, Any],
        *,
        success: bool,
    ) -> None:
        pattern = self.experience_patterns.get(pattern_id)
        if pattern is None:
            pattern = ExperiencePattern(pattern_id, pattern_type, pattern_data)
            self.experience_patterns[pattern_id] = pattern
        else:
            pattern.pattern_data = pattern_data

        if success:
            pattern.success_count += 1
        else:
            pattern.failure_count += 1

        total_attempts = pattern.success_count + pattern.failure_count
        if total_attempts > 0:
            pattern.confidence = pattern.success_count / total_attempts
        pattern.last_applied = datetime.now()
        await self._save_pattern(pattern)

    async def _learn_from_correction(self, feedback: Dict[str, Any], correction_type: str) -> None:
        """Create failure patterns from corrections."""
        pattern_data = {
            "correction_type": correction_type,
            "session_context": feedback.get("session_context", {}),
            "correction_timestamp": feedback.get("timestamp")
        }

        pattern_id = f"failure_{correction_type}_{datetime.now().timestamp()}"
        pattern = ExperiencePattern(pattern_id, "failure", pattern_data)
        pattern.failure_count = 1
        pattern.confidence = 0.7  # Initial confidence for failure patterns

        self.experience_patterns[pattern_id] = pattern
        await self._save_pattern(pattern)

        # Add to failed sequences for context
        self.failed_sequences.append({
            "pattern_id": pattern_id,
            "timestamp": datetime.now(),
            "context": pattern_data
        })

    async def _learn_from_missed_findings(self, feedback: Dict[str, Any], missed: List[str]) -> None:
        """Learn patterns from missed clinical findings."""
        for finding in missed:
            pattern_data = {
                "type": "missed_finding",
                "finding": finding,
                "session_context": feedback.get("session_context", {}),
                "learning_priority": "high"
            }

            pattern_id = f"missed_{finding[:20].replace(' ', '_')}_{datetime.now().timestamp()}"
            pattern = ExperiencePattern(pattern_id, "failure", pattern_data)
            pattern.failure_count = 1
            pattern.confidence = 0.8  # High confidence for missed findings

            self.experience_patterns[pattern_id] = pattern
            await self._save_pattern(pattern)

    async def _learn_from_incorrect_findings(self, feedback: Dict[str, Any], incorrect: List[str]) -> None:
        """Learn patterns from incorrect clinical findings."""
        for finding in incorrect:
            pattern_data = {
                "type": "incorrect_finding",
                "finding": finding,
                "session_context": feedback.get("session_context", {}),
                "learning_priority": "high"
            }

            pattern_id = f"incorrect_{finding[:20].replace(' ', '_')}_{datetime.now().timestamp()}"
            pattern = ExperiencePattern(pattern_id, "failure", pattern_data)
            pattern.failure_count = 1
            pattern.confidence = 0.8

            self.experience_patterns[pattern_id] = pattern
            await self._save_pattern(pattern)

    async def _learn_from_low_performance(self, feedback: Dict[str, Any]) -> None:
        """Learn from low performance ratings."""
        pattern_data = {
            "type": "low_performance",
            "ratings": feedback.get("ratings", {}),
            "session_context": feedback.get("session_context", {}),
            "areas_for_improvement": []
        }

        # Identify specific areas
        if feedback.get("decision_accuracy", 5) <= 2:
            pattern_data["areas_for_improvement"].append("decision_accuracy")

        if feedback.get("clinical_relevance", 5) <= 2:
            pattern_data["areas_for_improvement"].append("clinical_relevance")

        pattern_id = f"low_perf_{datetime.now().timestamp()}"
        pattern = ExperiencePattern(pattern_id, "optimization", pattern_data)
        pattern.failure_count = 1
        pattern.confidence = 0.6

        self.experience_patterns[pattern_id] = pattern
        await self._save_pattern(pattern)

    async def _learn_from_high_performance(self, feedback: Dict[str, Any]) -> None:
        """Learn from high performance - extract success patterns."""
        pattern_data = {
            "type": "high_performance",
            "ratings": feedback.get("ratings", {}),
            "session_context": feedback.get("session_context", {}),
            "success_factors": []
        }

        # Identify success factors
        if feedback.get("decision_accuracy", 0) >= 4:
            pattern_data["success_factors"].append("accurate_decision_making")

        if feedback.get("clinical_relevance", 0) >= 4:
            pattern_data["success_factors"].append("clinical_relevance")

        if feedback.get("diagnosis_correctness") == "correct":
            pattern_data["success_factors"].append("accurate_diagnosis")

        pattern_id = f"high_perf_{datetime.now().timestamp()}"
        pattern = ExperiencePattern(pattern_id, "success", pattern_data)
        pattern.success_count = 1
        pattern.confidence = 0.8

        self.experience_patterns[pattern_id] = pattern
        await self._save_pattern(pattern)

        # Add to successful sequences
        self.successful_sequences.append({
            "pattern_id": pattern_id,
            "timestamp": datetime.now(),
            "success_factors": pattern_data["success_factors"]
        })

    def find_applicable_patterns(self, current_state: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Find patterns applicable to current state for decision enhancement."""
        applicable = []

        for pattern in self.experience_patterns.values():
            if self._is_pattern_applicable(pattern, current_state):
                applicable.append({
                    "pattern_id": pattern.pattern_id,
                    "pattern_type": pattern.pattern_type,
                    "confidence": pattern.confidence,
                    "pattern_data": pattern.pattern_data,
                    "recommendation": self._generate_pattern_recommendation(pattern)
                })

        # Sort by confidence and applicability
        applicable.sort(key=lambda x: x["confidence"], reverse=True)
        return applicable[:5]  # Return top 5 most applicable patterns

    def _is_pattern_applicable(self, pattern: ExperiencePattern, state: Dict[str, Any]) -> bool:
        """Check if a pattern is applicable to current state."""
        pattern_data = pattern.pattern_data

        # Skip very old patterns unless they're high-confidence
        pattern_age = datetime.now() - pattern.created_at
        if pattern_age > timedelta(days=90) and pattern.confidence < 0.7:
            return False

        # Check session context matching
        pattern_context = pattern_data.get("session_context", {})
        current_context = state.get("session_context", {})

        # Apply failure patterns with high confidence
        if pattern.pattern_type == "failure" and pattern.confidence > 0.7:
            return True

        # Apply success patterns with medium confidence
        if pattern.pattern_type == "success" and pattern.confidence > 0.6:
            return True

        # Check for specific context matches
        if pattern_data.get("type") in ["missed_finding", "incorrect_finding"]:
            # These are always applicable if recent enough
            return pattern_age < timedelta(days=30)

        return False

    def _generate_pattern_recommendation(self, pattern: ExperiencePattern) -> str:
        """Generate human-readable recommendation from pattern."""
        pattern_type = pattern.pattern_type
        pattern_data = pattern.pattern_data

        if pattern_type == "failure":
            if pattern_data.get("type") == "missed_finding":
                return f"CAUTION: Previously missed finding '{pattern_data.get('finding')}'. Verify thoroughly."
            elif pattern_data.get("type") == "incorrect_finding":
                return f"CAUTION: Previously incorrect finding '{pattern_data.get('finding')}'. Exercise caution."
            else:
                return f"CAUTION: Previous {pattern_data.get('correction_type', 'failure')} in similar context."

        elif pattern_type == "success":
            factors = pattern_data.get("success_factors", [])
            return f"CONFIDENCE: Success factors observed: {', '.join(factors)}"

        elif pattern_type == "optimization":
            areas = pattern_data.get("areas_for_improvement", [])
            return f"FOCUS: Consider improvement areas: {', '.join(areas)}"

        return "Review this pattern for applicable insights."

    async def update_pattern_confidence(self, pattern_id: str, success: bool) -> None:
        """Update pattern confidence based on application results."""
        if pattern_id not in self.experience_patterns:
            return

        pattern = self.experience_patterns[pattern_id]

        if success:
            pattern.success_count += 1
        else:
            pattern.failure_count += 1

        # Calculate updated confidence using Bayesian approach
        total_attempts = pattern.success_count + pattern.failure_count
        if total_attempts > 0:
            pattern.confidence = pattern.success_count / total_attempts

        pattern.last_applied = datetime.now()
        await self._save_pattern(pattern)

        logger.info(
            "Updated pattern {} confidence: {:.2f} (successes: {}, failures: {})",
            pattern_id, pattern.confidence, pattern.success_count, pattern.failure_count
        )

    async def _save_pattern(self, pattern: ExperiencePattern) -> None:
        """Save pattern to persistent storage."""
        if not mongo_service.enabled:
            return

        try:
            collection = mongo_service.get_collection("agent_patterns")
            pattern_doc = {
                "pattern_id": pattern.pattern_id,
                "pattern_type": pattern.pattern_type,
                "pattern_data": pattern.pattern_data,
                "success_count": pattern.success_count,
                "failure_count": pattern.failure_count,
                "confidence": pattern.confidence,
                "last_applied": pattern.last_applied,
                "created_at": pattern.created_at,
                "updated_at": datetime.now()
            }

            await collection.update_one(
                {"pattern_id": pattern.pattern_id},
                {"$set": pattern_doc},
                upsert=True
            )

        except Exception as e:
            logger.warning("Failed to save pattern {}: {}", pattern.pattern_id, e)

    def get_learning_summary(self) -> Dict[str, Any]:
        """Get summary of learned patterns and learning progress."""
        total_patterns = len(self.experience_patterns)
        by_type = defaultdict(int)

        for pattern in self.experience_patterns.values():
            by_type[pattern.pattern_type] += 1

        high_confidence_patterns = [
            p for p in self.experience_patterns.values()
            if p.confidence >= 0.8
        ]

        return {
            "total_patterns": total_patterns,
            "patterns_by_type": dict(by_type),
            "high_confidence_count": len(high_confidence_patterns),
            "successful_sequences": len(self.successful_sequences),
            "failed_sequences": len(self.failed_sequences),
            "last_learning_update": self.last_learning_update,
            "learning_enabled": self.learning_enabled
        }


# Global instance for use across the application
adaptive_supervisor = AdaptiveSupervisor()
