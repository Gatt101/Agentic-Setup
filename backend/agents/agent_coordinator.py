from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional, Set
from datetime import datetime
from uuid import uuid4
from dataclasses import dataclass

from loguru import logger

from agents.base_agent import BaseAgent, AgentMessage, AgentGoal
from agents.clinical_agent import ClinicalAgent
from agents.vision_agent import VisionAgent
from agents.treatment_planner_agent import TreatmentPlannerAgent
from agents.rehabilitation_agent import RehabilitationAgent
from agents.patient_education_agent import PatientEducationAgent
from agents.appointment_agent import AppointmentAgent
from agents.pdf_agent import PDFGenerationAgent


@dataclass
class ConsensusResult:
    """Result from agent consensus process."""

    consensus_id: str
    topic: str
    participants: List[str]
    consensus_reached: bool
    final_decision: Dict[str, Any]
    participant_assessments: Dict[str, Dict[str, Any]]
    confidence: float
    timestamp: datetime
    reasoning_process: List[Dict[str, Any]]


class MultiAgentCoordinator:
    """Coordinates autonomous agents for collaborative decision-making."""

    def __init__(self):
        self.agents: Dict[str, BaseAgent] = {}
        self.message_bus: List[AgentMessage] = []
        self.consensus_history: List[ConsensusResult] = []
        self.collaboration_metrics = {
            "total_collaborations": 0,
            "successful_consensus": 0,
            "failed_consensus": 0,
            "average_consensus_time": 0.0
        }
        self.running_tasks: Dict[str, Dict[str, Any]] = {}

        # Initialize specialized agents
        self._initialize_agents()

    def _initialize_agents(self) -> None:
        """Initialize specialized autonomous agents asynchronously."""
        logger.info("Initializing multi-agent system...")

        # Don't initialize agents during module import to prevent hanging
        # Mark as not initialized and let it happen on first use
        self.agents = {}
        self.message_bus = []
        self.consensus_history = []
        self.collaboration_metrics = {
            "total_collaborations": 0,
            "successful_consensus": 0,
            "failed_consensus": 0,
            "average_consensus_time": 0.0
        }
        self.running_tasks = {}
        self._agents_initialized = False

        logger.info("Multi-agent system ready (lazy initialization)")
        logger.info(
            "Agents will be initialized on first use: {}",
            ["clinical_agent", "vision_agent"]
        )

    async def coordinate_analysis(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Coordinate multi-agent analysis of medical case.

        This is the main entry point for autonomous multi-agent collaboration.
        Agents perceive, reason, and act independently while collaborating.
        """
        logger.info("Starting multi-agent coordination for session {}", context.get("session_id", "unknown"))

        # Lazy initialization: create agents on first use if not exists
        if not self._agents_initialized:
            logger.info("Initializing agents for first use...")

            for agent_instance in [
                ClinicalAgent(),
                VisionAgent(),
                TreatmentPlannerAgent(),
                RehabilitationAgent(),
                PatientEducationAgent(),
                AppointmentAgent(),
                PDFGenerationAgent(),
            ]:
                self.agents[agent_instance.capabilities.agent_name] = agent_instance

            self._agents_initialized = True
            logger.info(
                "Multi-agent system initialized: {}",
                list(self.agents.keys())
            )

        coordination_id = str(uuid4())
        start_time = datetime.now()

        try:
            # Phase 1: Agent perception - all agents perceive the situation
            perception_results = await self._parallel_agent_perception(context)

            # Phase 2: Agent reasoning - each agent reasons independently
            reasoning_results = await self._parallel_agent_reasoning(context, perception_results)

            # Phase 3: Goal formulation - agents formulate their own goals
            goal_formulation = await self._parallel_goal_formulation(context, reasoning_results)

            # Phase 4: Collaborative decision making - agents collaborate on decisions
            collaborative_decisions = await self._facilitate_collaboration(context, reasoning_results, goal_formulation)

            # Phase 5: Action execution - agents execute their decisions
            execution_results = await self._execute_collaborative_actions(context, collaborative_decisions)

            # Phase 6: Consensus building - reach consensus on final outcome
            final_consensus = await self._build_agent_consensus(context, execution_results)

            # Record coordination metrics
            coordination_time = (datetime.now() - start_time).total_seconds()
            self._record_coordination_metrics(coordination_id, coordination_time, True)

            logger.info(
                "Multi-agent coordination completed successfully: consensus_reached={}, time={:.2f}s",
                final_consensus.get("consensus_reached", False),
                coordination_time
            )

            return {
                "coordination_id": coordination_id,
                "success": True,
                "consensus_result": final_consensus,
                "agent_perceptions": perception_results,
                "agent_reasoning": reasoning_results,
                "collaborative_decisions": collaborative_decisions,
                "execution_results": execution_results,
                "coordination_time": coordination_time,
                "agents_involved": list(self.agents.keys())
            }

        except Exception as e:
            logger.error("Multi-agent coordination failed: {}", e)
            coordination_time = (datetime.now() - start_time).total_seconds()
            self._record_coordination_metrics(coordination_id, coordination_time, False)

            return {
                "coordination_id": coordination_id,
                "success": False,
                "error": str(e),
                "coordination_time": coordination_time
            }

    async def _parallel_agent_perception(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Have all agents perceive the current situation in parallel."""
        logger.debug("Starting parallel agent perception...")

        perception_tasks = [
            agent.perceive(context)
            for agent in self.agents.values()
        ]

        results = await asyncio.gather(*perception_tasks, return_exceptions=True)

        perception_results = {}
        for agent_name, result in zip(self.agents.keys(), results):
            if isinstance(result, Exception):
                logger.error("Agent {} perception failed: {}", agent_name, result)
                perception_results[agent_name] = {"error": str(result)}
            else:
                perception_results[agent_name] = result

        logger.info("Parallel perception completed: {} agents perceived", len(perception_results))
        return perception_results

    async def _parallel_agent_reasoning(self, context: Dict[str, Any], perception_results: Dict[str, Any]) -> Dict[str, Any]:
        """Have all agents reason about the situation independently."""
        logger.debug("Starting parallel agent reasoning...")

        reasoning_tasks = []
        task_agent_names = []
        for agent_name, perception in perception_results.items():
            if agent_name in self.agents:
                # Combine context with agent's perception
                agent_context = {**context, **perception, "agent_perception": perception}
                reasoning_tasks.append(self.agents[agent_name].reason(agent_context))
                task_agent_names.append(agent_name)

        results = await asyncio.gather(*reasoning_tasks, return_exceptions=True)

        reasoning_results = {}
        for agent_name, result in zip(task_agent_names, results):
            if isinstance(result, Exception):
                logger.error("Agent {} reasoning failed: {}", agent_name, result)
                reasoning_results[agent_name] = {"error": str(result)}
            else:
                reasoning_results[agent_name] = result

        logger.info("Parallel reasoning completed: {} agents reasoned", len(reasoning_results))
        return reasoning_results

    async def _parallel_goal_formulation(self, context: Dict[str, Any], reasoning_results: Dict[str, Any]) -> Dict[str, Any]:
        """Have agents formulate their own goals based on reasoning."""
        logger.debug("Starting parallel goal formulation...")

        goal_tasks = []
        task_agent_names = []
        for agent_name, reasoning in reasoning_results.items():
            if agent_name in self.agents and "error" not in reasoning:
                # Combine context with agent's reasoning
                agent_context = {**context, **reasoning, "agent_reasoning": reasoning}
                goal_tasks.append(self.agents[agent_name].formulate_goals(agent_context))
                task_agent_names.append(agent_name)

        results = await asyncio.gather(*goal_tasks, return_exceptions=True)

        goal_formulation = {}
        for agent_name, result in zip(task_agent_names, results):
            if isinstance(result, Exception):
                logger.error("Agent {} goal formulation failed: {}", agent_name, result)
                goal_formulation[agent_name] = {"error": str(result), "goals": []}
            else:
                goal_formulation[agent_name] = {
                    "goals": result,
                    "goal_count": len(result),
                    "urgent_goals": len([g for g in result if g.is_urgent()])
                }

        logger.info("Parallel goal formulation completed: {} goals formulated", sum(gf.get("goal_count", 0) for gf in goal_formulation.values()))
        return goal_formulation

    async def _facilitate_collaboration(self, context: Dict[str, Any], reasoning_results: Dict[str, Any], goal_formulation: Dict[str, Any]) -> Dict[str, Any]:
        """Facilitate collaboration between agents based on their reasoning and goals."""
        logger.debug("Facilitating agent collaboration...")

        collaboration_decisions = {}

        # Identify collaboration opportunities
        collaboration_needs = self._identify_collaboration_needs(reasoning_results)

        for need in collaboration_needs:
            logger.info("Addressing collaboration need: {}", need["type"])

            # Route to appropriate collaboration handler
            if need["type"] == "vision_clinical_collaboration":
                decision = await self._handle_vision_clinical_collaboration(context, need)
                collaboration_decisions["vision_clinical"] = decision
            elif need["type"] == "multi_agent_consensus":
                decision = await self._handle_multi_agent_consensus(context, need)
                collaboration_decisions["multi_agent_consensus"] = decision

        logger.info("Collaboration facilitated: {} collaborative decisions made", len(collaboration_decisions))
        return collaboration_decisions

    def _identify_collaboration_needs(self, reasoning_results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Identify when agents need to collaborate."""
        needs = []

        # Check if vision and clinical agents both have recommendations
        vision_reasoning = reasoning_results.get("vision_agent", {})
        clinical_reasoning = reasoning_results.get("clinical_agent", {})

        vision_collabs = vision_reasoning.get("collaboration_needs", [])
        clinical_collabs = clinical_reasoning.get("collaboration_needs", [])

        if any("clinical_verification" in c for c in vision_collabs) or any("vision_analysis" in c for c in clinical_collabs):
            needs.append({
                "type": "vision_clinical_collaboration",
                "participants": ["vision_agent", "clinical_agent"],
                "reason": "Mutual verification needed"
            })

        # Check if multiple agents need to reach consensus
        total_needs = len(vision_collabs) + len(clinical_collabs)
        if total_needs > 2:
            needs.append({
                "type": "multi_agent_consensus",
                "participants": list(self.agents.keys()),
                "reason": "Complex case requiring consensus"
            })

        return needs

    async def _handle_vision_clinical_collaboration(self, context: Dict[str, Any], need: Dict[str, Any]) -> Dict[str, Any]:
        """Handle collaboration between vision and clinical agents."""
        logger.info("Handling vision-clinical collaboration...")

        # Create collaboration messages
        collaboration_id = str(uuid4())

        # This would normally involve actual message passing
        # For now, we'll simulate the collaboration
        vision_agent = self.agents.get("vision_agent")
        clinical_agent = self.agents.get("clinical_agent")

        if not vision_agent or not clinical_agent:
            return {"error": "Required agents not available"}

        # Simulate collaborative decision
        collaboration_result = {
            "collaboration_id": collaboration_id,
            "participants": need["participants"],
            "type": "vision_clinical_collaboration",
            "collaborative_decision": {
                "action": "proceed_with_analysis",
                "confidence": 0.85,
                "reasoning": "Vision and clinical agents agree on analysis approach"
            },
            "agreement_level": "high"
        }

        return collaboration_result

    async def _handle_multi_agent_consensus(self, context: Dict[str, Any], need: Dict[str, Any]) -> Dict[str, Any]:
        """Handle multi-agent consensus building."""
        logger.info("Handling multi-agent consensus...")

        consensus_id = str(uuid4())
        topic = f"Case analysis for session {context.get('session_id', 'unknown')}"

        # Collect assessments from all participants
        participant_assessments = {}
        assessment_tasks = []

        for participant_name in need["participants"]:
            if participant_name in self.agents:
                task = self.agents[participant_name]._generate_consensus_assessment({
                    "type": "analysis_consensus",
                    "context": context
                })
                assessment_tasks.append((participant_name, task))

        results = await asyncio.gather(*[task for _, task in assessment_tasks], return_exceptions=True)

        for (participant_name, _), result in zip(assessment_tasks, results):
            if isinstance(result, Exception):
                logger.error("Agent {} consensus assessment failed: {}", participant_name, result)
                participant_assessments[participant_name] = {"error": str(result)}
            else:
                participant_assessments[participant_name] = result

        # Determine if consensus was reached
        consensus_reached = self._evaluate_consensus(participant_assessments)

        # Build consensus result
        consensus_result = ConsensusResult(
            consensus_id=consensus_id,
            topic=topic,
            participants=list(participant_assessments.keys()),
            consensus_reached=consensus_reached,
            final_decision=self._derive_final_decision(participant_assessments, consensus_reached),
            participant_assessments=participant_assessments,
            confidence=self._calculate_consensus_confidence(participant_assessments),
            timestamp=datetime.now(),
            reasoning_process=self._document_reasoning_process(participant_assessments)
        )

        # Store in history
        self.consensus_history.append(consensus_result)

        return {
            "consensus_id": consensus_id,
            "consensus_reached": consensus_reached,
            "final_decision": consensus_result.final_decision,
            "participant_assessments": participant_assessments,
            "confidence": consensus_result.confidence
        }

    def _evaluate_consensus(self, participant_assessments: Dict[str, Dict[str, Any]]) -> bool:
        """Evaluate if consensus was reached among participants."""
        valid_assessments = [
            assessment for assessment in participant_assessments.values()
            if "error" not in assessment
        ]

        if len(valid_assessments) < 2:
            return False

        # Check if confidence levels are aligned
        confidences = [
            assessment.get("confidence", 0.5)
            for assessment in valid_assessments
        ]

        # Consensus reached if all confidences are within 0.2 of each other
        max_confidence = max(confidences)
        min_confidence = min(confidences)

        return (max_confidence - min_confidence) < 0.2

    def _derive_final_decision(self, participant_assessments: Dict[str, Any], consensus_reached: bool) -> Dict[str, Any]:
        """Derive final decision from participant assessments."""
        valid_assessments = [
            (agent_name, assessment)
            for agent_name, assessment in participant_assessments.items()
            if "error" not in assessment
        ]

        if not valid_assessments:
            return {"decision": "no_valid_assessments", "reason": "No valid participant assessments available"}

        if consensus_reached:
            # If consensus reached, use the highest confidence assessment
            best_agent, best_assessment = max(
                valid_assessments,
                key=lambda x: x[1].get("confidence", 0.5)
            )

            return {
                "decision": "consensus_approach",
                "primary_agent": best_agent,
                "approach": best_assessment.get("assessment", ""),
                "confidence": best_assessment.get("confidence", 0.5),
                "reasoning": "Agents reached consensus, using highest confidence assessment"
            }
        else:
            # If no consensus, use weighted approach
            total_confidence = sum(assessment.get("confidence", 0.5) for _, assessment in valid_assessments)

            return {
                "decision": "weighted_consensus",
                "participants": [agent_name for agent_name, _ in valid_assessments],
                "average_confidence": total_confidence / len(valid_assessments) if valid_assessments else 0.5,
                "reasoning": "No full consensus, using weighted approach from all participants"
            }

    def _calculate_consensus_confidence(self, participant_assessments: Dict[str, Any]) -> float:
        """Calculate overall confidence level for consensus."""
        valid_assessments = [
            assessment.get("confidence", 0.5)
            for assessment in participant_assessments.values()
            if "error" not in assessment
        ]

        if not valid_assessments:
            return 0.0

        return sum(valid_assessments) / len(valid_assessments)

    def _document_reasoning_process(self, participant_assessments: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Document the reasoning process for consensus building."""
        process = []

        for agent_name, assessment in participant_assessments.items():
            if "error" not in assessment:
                process.append({
                    "agent": agent_name,
                    "assessment": assessment.get("assessment", ""),
                    "confidence": assessment.get("confidence", 0.5),
                    "reasoning": assessment.get("reasoning", ""),
                    "specialist_view": assessment.get("specialist_view", "")
                })

        return process

    async def _execute_collaborative_actions(self, context: Dict[str, Any], collaborative_decisions: Dict[str, Any]) -> Dict[str, Any]:
        """Execute actions determined through collaboration."""
        logger.debug("Executing collaborative actions...")

        execution_results = {}

        for decision_type, decision in collaborative_decisions.items():
            logger.info("Executing collaborative action: {}", decision_type)

            try:
                # Execute the collaborative decision
                result = await self._execute_collaborative_action(context, decision_type, decision)
                execution_results[decision_type] = result
            except Exception as e:
                logger.error("Failed to execute collaborative action {}: {}", decision_type, e)
                execution_results[decision_type] = {"success": False, "error": str(e)}

        logger.info("Collaborative actions executed: {} actions completed", len(execution_results))
        return execution_results

    async def _execute_collaborative_action(self, context: Dict[str, Any], action_type: str, decision: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a specific collaborative action."""
        # This would execute the actual collaborative action
        # For now, return a success result
        return {
            "success": True,
            "action_type": action_type,
            "decision": decision,
            "timestamp": datetime.now()
        }

    async def _build_agent_consensus(self, context: Dict[str, Any], execution_results: Dict[str, Any]) -> Dict[str, Any]:
        """Build final consensus from all agent interactions."""
        logger.debug("Building final agent consensus...")

        # Check if we already have a consensus result from earlier collaboration
        if "multi_agent_consensus" in execution_results:
            consensus_execution = execution_results["multi_agent_consensus"]
            consensus_data = consensus_execution.get("decision", consensus_execution)
            return {
                "consensus_reached": consensus_data.get("consensus_reached", False),
                "final_decision": consensus_data.get("final_decision"),
                "confidence": consensus_data.get("confidence", 0.5),
                "participants": list(consensus_data.get("participant_assessments", {}).keys()),
            }

        # Otherwise, build consensus from execution results
        return {
            "consensus_reached": True,
            "final_decision": {
                "decision": "collaborative_analysis_complete",
                "reasoning": "Agents collaborated successfully to complete analysis"
            },
            "confidence": 0.8,
            "participants": list(self.agents.keys())
        }

    def _record_coordination_metrics(self, coordination_id: str, coordination_time: float, success: bool) -> None:
        """Record metrics for coordination session."""
        self.collaboration_metrics["total_collaborations"] += 1
        if success:
            self.collaboration_metrics["successful_consensus"] += 1
        else:
            self.collaboration_metrics["failed_consensus"] += 1

        # Update average time
        total_time = (
            self.collaboration_metrics["average_consensus_time"] *
            (self.collaboration_metrics["total_collaborations"] - 1) + coordination_time
        )
        self.collaboration_metrics["average_consensus_time"] = total_time / self.collaboration_metrics["total_collaborations"]

    def get_coordination_statistics(self) -> Dict[str, Any]:
        """Get statistics about multi-agent coordination."""
        agent_summaries = {}
        for agent_name, agent in self.agents.items():
            agent_summaries[agent_name] = agent.get_performance_summary()

        return {
            "coordination_metrics": self.collaboration_metrics,
            "agent_summaries": agent_summaries,
            "total_agents": len(self.agents),
            "consensus_history_length": len(self.consensus_history),
            "recent_consensus_success": sum(
                1 for c in self.consensus_history[-10:] if c.consensus_reached
            ) if self.consensus_history else 0
        }


# Global coordinator instance
agent_coordinator = MultiAgentCoordinator()
