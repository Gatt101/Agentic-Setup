from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from loguru import logger
from collections import defaultdict, Counter
import asyncio

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
        self._load_existing_patterns()

    def _load_existing_patterns(self) -> None:
        """Load existing experience patterns from storage."""
        if not mongo_service.enabled:
            logger.info("MongoDB not available - starting without existing patterns")
            return

        try:
            collection = mongo_service.get_collection("agent_patterns")
            cursor = collection.find({})

            async def load_patterns():
                patterns = await cursor.to_list(length=None)
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

            asyncio.run(load_patterns())

        except Exception as e:
            logger.warning("Failed to load existing patterns: {}", e)

    async def learn_from_feedback(self, feedback: Dict[str, Any]) -> None:
        """Extract learning signals from user feedback."""
        if not self.learning_enabled or not mongo_service.enabled:
            return

        try:
            patterns_to_update = []

            # Learn from incorrect diagnoses
            if feedback.get("diagnosis_correctness") == "incorrect":
                await self._learn_from_correction(feedback, "diagnosis")

            # Learn from triage mismatches
            if feedback.get("triage_appropriateness") == "inappropriate":
                await self._learn_from_correction(feedback, "triage")

            # Learn from low ratings
            if feedback.get("decision_accuracy", 5) <= 2:
                await self._learn_from_low_performance(feedback)

            # Learn from high performance
            if feedback.get("decision_accuracy", 0) >= 4:
                await self._learn_from_high_performance(feedback)

            # Analyze missed findings
            missed_findings = feedback.get("missed_findings", [])
            if missed_findings:
                await self._learn_from_missed_findings(feedback, missed_findings)

            # Analyze incorrect findings
            incorrect_findings = feedback.get("incorrect_findings", [])
            if incorrect_findings:
                await self._learn_from_incorrect_findings(feedback, incorrect_findings)

            self.last_learning_update = datetime.now()
            logger.info("Learning completed from feedback_id={}", feedback.get("feedback_id"))

        except Exception as e:
            logger.error("Failed to learn from feedback: {}", e)

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