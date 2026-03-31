from __future__ import annotations

import random
from typing import Any, Dict, List, Optional, Tuple
from loguru import logger
from datetime import datetime
import math

from services.agent_learning import adaptive_supervisor


class ConfidenceEstimator:
    """Estimates confidence levels for agent decisions."""

    def __init__(self):
        self.confidence_history = []
        self.calibration_data = {}

    def estimate_tool_confidence(self, tool_name: str, state: Dict[str, Any]) -> float:
        """Estimate confidence for a specific tool execution."""
        base_confidence = self._get_base_tool_confidence(tool_name)

        # Adjust based on state completeness
        state_multiplier = self._get_state_multiplier(tool_name, state)

        # Apply learning adjustments
        learning_adjustment = self._get_learning_adjustment(tool_name, state)

        final_confidence = base_confidence * state_multiplier * learning_adjustment

        # Ensure confidence is within valid range
        final_confidence = max(0.1, min(0.99, final_confidence))

        logger.debug(
            "Tool confidence estimate: {} -> {:.3f} (base: {:.3f}, state: {:.3f}, learning: {:.3f})",
            tool_name, final_confidence, base_confidence, state_multiplier, learning_adjustment
        )

        return final_confidence

    def _get_base_tool_confidence(self, tool_name: str) -> float:
        """Get base confidence for tool based on historical performance."""
        # Base confidences for different tool types
        base_confidences = {
            "vision_detect_body_part": 0.95,
            "vision_detect_hand_fracture": 0.85,
            "vision_detect_leg_fracture": 0.85,
            "clinical_generate_diagnosis": 0.75,
            "clinical_assess_triage": 0.80,
            "report_generate_patient_pdf": 0.90,
            "report_generate_clinician_pdf": 0.92,
            "hospital_find_nearby_hospitals": 0.95,
            "knowledge_query": 0.85,
        }

        # Extract namespace from tool name
        namespace = tool_name.split("_")[0]
        return base_confidences.get(tool_name, base_confidences.get(namespace, 0.70))

    def _get_state_multiplier(self, tool_name: str, state: Dict[str, Any]) -> float:
        """Adjust confidence based on state completeness."""
        multiplier = 1.0

        # Vision tools
        if tool_name.startswith("vision_"):
            if state.get("image_data"):
                multiplier *= 1.0
            else:
                multiplier *= 0.3

            if tool_name == "vision_detect_hand_fracture":
                if state.get("body_part") == "hand":
                    multiplier *= 1.1
                else:
                    multiplier *= 0.8

            elif tool_name == "vision_detect_leg_fracture":
                if state.get("body_part") == "leg":
                    multiplier *= 1.1
                else:
                    multiplier *= 0.8

        # Clinical tools
        elif tool_name.startswith("clinical_"):
            if tool_name == "clinical_generate_diagnosis":
                detections = state.get("detections")
                if detections and isinstance(detections, list) and len(detections) > 0:
                    multiplier *= 1.2
                else:
                    multiplier *= 0.4

            elif tool_name == "clinical_assess_triage":
                if state.get("diagnosis"):
                    multiplier *= 1.1
                else:
                    multiplier *= 0.3

        # Report tools
        elif tool_name.startswith("report_"):
            patient_info = state.get("patient_info", {})
            has_name = bool(patient_info.get("name"))
            has_age = bool(patient_info.get("age"))
            has_gender = bool(patient_info.get("gender"))

            completeness = sum([has_name, has_age, has_gender]) / 3.0
            multiplier *= (0.5 + completeness * 0.5)  # Range: 0.5 to 1.0

        return max(0.1, min(1.5, multiplier))

    def _get_learning_adjustment(self, tool_name: str, state: Dict[str, Any]) -> float:
        """Adjust confidence based on learned patterns."""
        try:
            applicable = adaptive_supervisor.find_applicable_patterns(state)

            for pattern in applicable:
                # Reduce confidence for failure patterns
                if pattern["pattern_type"] == "failure" and pattern["confidence"] > 0.7:
                    logger.info("Reducing confidence due to failure pattern: {}", pattern["pattern_id"])
                    return 0.8

                # Increase confidence for success patterns
                if pattern["pattern_type"] == "success" and pattern["confidence"] > 0.8:
                    return 1.1

        except Exception as e:
            logger.warning("Failed to apply learning adjustment: {}", e)

        return 1.0


class ProbabilisticDecisionMaker:
    """Makes decisions with probabilistic reasoning and uncertainty handling."""

    def __init__(self, confidence_estimator: ConfidenceEstimator):
        self.confidence_estimator = confidence_estimator
        self.decision_history = []

    def select_action_with_probability(
        self,
        candidates: List[Dict[str, Any]],
        state: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Select action using Thompson Sampling for exploration-exploitation.

        Balances using successful patterns (exploitation) with trying new
        approaches (exploration) based on confidence estimates.
        """
        if not candidates:
            return None

        # Calculate probabilities for each candidate
        candidate_probabilities = []
        for candidate in candidates:
            tool_name = candidate.get("name", "")

            # Get confidence estimate
            confidence = self.confidence_estimator.estimate_tool_confidence(tool_name, state)

            # Add candidate data with confidence
            candidate_probabilities.append({
                "candidate": candidate,
                "probability": confidence,
                "tool_name": tool_name
            })

        # Sort by probability
        candidate_probabilities.sort(key=lambda x: x["probability"], reverse=True)

        # Apply Thompson Sampling
        selected = self._thompson_sampling(candidate_probabilities)

        if selected:
            self._record_decision(selected["tool_name"], selected["probability"])
            return selected["candidate"]

        # Fallback to highest probability if sampling fails
        return candidate_probabilities[0]["candidate"]

    def _thompson_sampling(self, candidates: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Implement Thompson Sampling for exploration-exploitation trade-off."""
        if not candidates:
            return None

        # Extract probabilities
        probabilities = [c["probability"] for c in candidates]

        # Create probability distribution
        total_prob = sum(probabilities)
        if total_prob == 0:
            return candidates[0]

        # Normalize probabilities
        normalized_probs = [p / total_prob for p in probabilities]

        # Sample according to distribution
        try:
            chosen_index = random.choices(
                range(len(candidates)),
                weights=normalized_probs,
                k=1
            )[0]

            return candidates[chosen_index]

        except Exception as e:
            logger.warning("Thompson sampling failed, using highest probability: {}", e)
            return candidates[0]

    def assess_decision_uncertainty(self, action: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
        """Assess uncertainty level for a given action."""
        tool_name = action.get("name", "")

        confidence = self.confidence_estimator.estimate_tool_confidence(tool_name, state)

        # Categorize uncertainty
        if confidence >= 0.9:
            uncertainty_level = "low"
            uncertainty_score = 0.1
        elif confidence >= 0.7:
            uncertainty_level = "moderate"
            uncertainty_score = 0.3
        elif confidence >= 0.5:
            uncertainty_level = "medium"
            uncertainty_score = 0.5
        else:
            uncertainty_level = "high"
            uncertainty_score = 0.7

        # Provide recommendations based on uncertainty
        recommendations = []
        if uncertainty_level == "high":
            recommendations.append("Consider requesting additional information")
            recommendations.append("Review available patterns for similar cases")

        return {
            "action": tool_name,
            "confidence": confidence,
            "uncertainty_level": uncertainty_level,
            "uncertainty_score": uncertainty_score,
            "recommendations": recommendations
        }

    def _record_decision(self, tool_name: str, probability: float) -> None:
        """Record decision for future analysis."""
        self.decision_history.append({
            "tool_name": tool_name,
            "probability": probability,
            "timestamp": datetime.now()
        })

        # Keep history manageable
        if len(self.decision_history) > 1000:
            self.decision_history = self.decision_history[-1000:]

    def get_decision_statistics(self) -> Dict[str, Any]:
        """Get statistics about decision-making patterns."""
        if not self.decision_history:
            return {
                "total_decisions": 0,
                "average_confidence": None,
                "most_common_tools": [],
                "confidence_distribution": {}
            }

        total_decisions = len(self.decision_history)

        # Calculate average confidence
        avg_confidence = sum(d["probability"] for d in self.decision_history) / total_decisions

        # Most common tools
        tool_counts = {}
        for decision in self.decision_history:
            tool_name = decision["tool_name"]
            tool_counts[tool_name] = tool_counts.get(tool_name, 0) + 1

        most_common = sorted(tool_counts.items(), key=lambda x: x[1], reverse=True)[:5]

        # Confidence distribution
        confidence_ranges = {
            "high (0.9+)": sum(1 for d in self.decision_history if d["probability"] >= 0.9),
            "medium-high (0.7-0.9)": sum(1 for d in self.decision_history if 0.7 <= d["probability"] < 0.9),
            "medium (0.5-0.7)": sum(1 for d in self.decision_history if 0.5 <= d["probability"] < 0.7),
            "low (<0.5)": sum(1 for d in self.decision_history if d["probability"] < 0.5)
        }

        return {
            "total_decisions": total_decisions,
            "average_confidence": round(avg_confidence, 3),
            "most_common_tools": [{"tool": tool, "count": count} for tool, count in most_common],
            "confidence_distribution": confidence_ranges
        }


class BayesianBeliefUpdater:
    """Updates beliefs about tool effectiveness using Bayesian inference."""

    def __init__(self):
        self.tool_beliefs = {}
        self.alpha = 1.0  # Prior success parameter
        self.beta = 1.0   # Prior failure parameter

    def initialize_belief(self, tool_name: str, prior_success: float = 0.8) -> None:
        """Initialize belief for a tool with prior success probability."""
        # Convert prior probability to alpha/beta parameters
        if prior_success <= 0 or prior_success >= 1:
            alpha = self.alpha
            beta = self.beta
        else:
            # Use a weak prior with concentration parameter of 2
            alpha = 2 * prior_success
            beta = 2 * (1 - prior_success)

        self.tool_beliefs[tool_name] = {
            "alpha": alpha,
            "beta": beta,
            "prior_success": prior_success,
            "success_count": 0,
            "failure_count": 0,
            "last_updated": datetime.now()
        }

    def update_belief(self, tool_name: str, success: bool) -> None:
        """Update belief based on observed outcome."""
        if tool_name not in self.tool_beliefs:
            self.initialize_belief(tool_name)

        belief = self.tool_beliefs[tool_name]

        if success:
            belief["alpha"] += 1
            belief["success_count"] += 1
        else:
            belief["beta"] += 1
            belief["failure_count"] += 1

        belief["last_updated"] = datetime.now()

        logger.info(
            "Updated belief for {}: α={}, β={}, success={}, failures={}",
            tool_name, belief["alpha"], belief["beta"],
            belief["success_count"], belief["failure_count"]
        )

    def get_success_probability(self, tool_name: str) -> float:
        """Get posterior success probability for a tool."""
        if tool_name not in self.tool_beliefs:
            self.initialize_belief(tool_name)

        belief = self.tool_beliefs[tool_name]
        posterior_mean = belief["alpha"] / (belief["alpha"] + belief["beta"])

        return posterior_mean

    def get_confidence_interval(self, tool_name: str, confidence: float = 0.95) -> Tuple[float, float]:
        """Get confidence interval for tool success probability."""
        if tool_name not in self.tool_beliefs:
            self.initialize_belief(tool_name)

        belief = self.tool_beliefs[tool_name]

        # Beta distribution parameters
        alpha = belief["alpha"]
        beta = belief["beta"]

        # Use normal approximation for confidence interval
        mean = alpha / (alpha + beta)
        variance = (alpha * beta) / ((alpha + beta)**2 * (alpha + beta + 1))
        std_dev = math.sqrt(variance)

        # Z-score for confidence level
        z_scores = {0.90: 1.645, 0.95: 1.96, 0.99: 2.576}
        z = z_scores.get(confidence, 1.96)

        lower = max(0, mean - z * std_dev)
        upper = min(1, mean + z * std_dev)

        return (lower, upper)


# Global instances
confidence_estimator = ConfidenceEstimator()
probabilistic_reasoner = ProbabilisticDecisionMaker(confidence_estimator)
bayesian_updater = BayesianBeliefUpdater()