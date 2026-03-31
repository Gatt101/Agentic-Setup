from __future__ import annotations

from typing import Any, Dict, List
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from loguru import logger

from agents.agent_coordinator import agent_coordinator
from agents.base_agent import BaseAgent, AgentGoal


router = APIRouter(tags=["multi_agent"])


@router.post("/multi_agent/analyze")
async def multi_agent_analysis(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Perform multi-agent analysis with autonomous collaboration.

    This endpoint demonstrates true agentic behavior where specialized agents
    perceive, reason, formulate goals, collaborate, and reach consensus independently.
    """
    try:
        logger.info("Starting multi-agent analysis for session {}", context.get("session_id", "unknown"))

        # Coordinate multi-agent analysis
        result = await agent_coordinator.coordinate_analysis(context)

        return result

    except Exception as e:
        logger.error("Multi-agent analysis failed: {}", e)
        raise HTTPException(status_code=500, detail=f"Multi-agent analysis failed: {str(e)}")


@router.get("/multi_agent/status")
async def get_multi_agent_status() -> Dict[str, Any]:
    """
    Get status of all autonomous agents.

    Provides real-time information about agent activities, goals, and performance.
    """
    try:
        coordinator_stats = agent_coordinator.get_coordination_statistics()

        return {
            "coordinator_status": "active",
            "timestamp": datetime.now().isoformat(),
            "statistics": coordinator_stats,
            "agent_details": {
                agent_name: {
                    "status": "active",
                    "active_goals": len([g for g in agent.goals.values() if g.status == "in_progress"]),
                    "completed_goals": len([g for g in agent.goals.values() if g.status == "completed"]),
                    "message_queue_length": len(agent.message_queue),
                    "current_tasks": agent.current_tasks
                }
                for agent_name, agent in agent_coordinator.agents.items()
            }
        }

    except Exception as e:
        logger.error("Failed to get multi-agent status: {}", e)
        raise HTTPException(status_code=500, detail=f"Failed to get multi-agent status: {str(e)}")


@router.get("/multi_agent/goals")
async def get_agent_goals(
    agent_name: str = Query(None)
) -> Dict[str, Any]:
    """
    Get goals formulated by agents.

    Shows what autonomous goals agents have formulated and their current status.
    """
    try:
        if agent_name:
            if agent_name not in agent_coordinator.agents:
                raise HTTPException(status_code=404, detail=f"Agent {agent_name} not found")

            agent = agent_coordinator.agents[agent_name]
            goals_list = [
                {
                    "goal_id": goal.goal_id,
                    "description": goal.description,
                    "priority": goal.priority,
                    "objective": goal.objective,
                    "success_criteria": goal.success_criteria,
                    "progress": goal.progress,
                    "status": goal.status,
                    "created_at": goal.created_at.isoformat(),
                    "is_urgent": goal.is_urgent(),
                    "is_overdue": goal.is_overdue()
                }
                for goal in agent.goals.values()
            ]

            return {
                "agent_name": agent_name,
                "goals": goals_list,
                "total_goals": len(goals_list),
                "active_goals": len([g for g in agent.goals.values() if g.status == "in_progress"])
            }
        else:
            # Get goals from all agents
            all_goals = {}
            for agent_name, agent in agent_coordinator.agents.items():
                goals_list = [
                    {
                        "goal_id": goal.goal_id,
                        "description": goal.description,
                        "priority": goal.priority,
                        "status": goal.status,
                        "progress": goal.progress
                    }
                    for goal in agent.goals.values()
                ]
                all_goals[agent_name] = goals_list

            total_goals = sum(len(goals) for goals in all_goals.values())
            active_goals = sum(
                len([g for g in agent.coordinator.agents[agent_name].goals.values() if g.status == "in_progress"])
                for agent_name in agent_coordinator.agents.keys()
            )

            return {
                "all_agent_goals": all_goals,
                "total_goals": total_goals,
                "active_goals": active_goals,
                "agents_with_goals": len([agent_name for agent_name, goals in all_goals.items() if goals])
            }

    except Exception as e:
        logger.error("Failed to get agent goals: {}", e)
        raise HTTPException(status_code=500, detail=f"Failed to get agent goals: {str(e)}")


@router.get("/multi_agent/performance")
async def get_agent_performance() -> Dict[str, Any]:
    """
    Get performance metrics for all autonomous agents.

    Provides insights into agent effectiveness, collaboration success, and learning progress.
    """
    try:
        coordinator_stats = agent_coordinator.get_coordination_statistics()

        performance_summary = {
            "coordination_metrics": coordinator_stats["coordination_metrics"],
            "individual_agent_performance": coordinator_stats["agent_summaries"],
            "system_health": {
                "total_agents": coordinator_stats["total_agents"],
                "consensus_success_rate": (
                    coordinator_stats["coordination_metrics"]["successful_consensus"] /
                    coordinator_stats["coordination_metrics"]["total_collaborations"]
                    if coordinator_stats["coordination_metrics"]["total_collaborations"] > 0
                    else 0.0
                ),
                "average_coordination_time": coordinator_stats["coordination_metrics"]["average_consensus_time"],
                "recent_consensus_success": coordinator_stats["recent_consensus_success"]
            }
        }

        return performance_summary

    except Exception as e:
        logger.error("Failed to get agent performance: {}", e)
        raise HTTPException(status_code=500, detail=f"Failed to get agent performance: {str(e)}")


@router.get("/multi_agent/consensus/history")
async def get_consensus_history(
    limit: int = Query(10, ge=1, le=50, description="Number of recent consensus results to return")
) -> Dict[str, Any]:
    """
    Get history of agent consensus building.

    Shows how agents have collaborated and reached consensus in previous analyses.
    """
    try:
        history = agent_coordinator.consensus_history[-limit:] if agent_coordinator.consensus_history else []

        consensus_history_list = [
            {
                "consensus_id": consensus.consensus_id,
                "topic": consensus.topic,
                "participants": consensus.participants,
                "consensus_reached": consensus.consensus_reached,
                "confidence": round(consensus.confidence, 3),
                "timestamp": consensus.timestamp.isoformat(),
                "final_decision": consensus.final_decision,
                "participant_count": len(consensus.participants)
            }
            for consensus in history
        ]

        return {
            "total_history_length": len(agent_coordinator.consensus_history),
            "returned_count": len(consensus_history_list),
            "consensus_history": consensus_history_list,
            "success_rate": (
                sum(1 for c in agent_coordinator.consensus_history if c.consensus_reached) /
                len(agent_coordinator.consensus_history)
                if agent_coordinator.consensus_history
                else 0.0
            )
        }

    except Exception as e:
        logger.error("Failed to get consensus history: {}", e)
        raise HTTPException(status_code=500, detail=f"Failed to get consensus history: {str(e)}")


@router.get("/multi_agent/collaboration/analyze")
async def analyze_collaboration_patterns(
    days: int = Query(7, ge=1, le=30, description="Number of days to analyze")
) -> Dict[str, Any]:
    """
    Analyze collaboration patterns between agents.

    Provides insights into how agents collaborate, which collaborations are most successful,
    and areas for improvement in multi-agent coordination.
    """
    try:
        # Analyze consensus history for patterns
        recent_consensus = [
            c for c in agent_coordinator.consensus_history
            if (datetime.now() - c.timestamp).days <= days
        ]

        if not recent_consensus:
            return {
                "analysis_period_days": days,
                "total_consensus_events": 0,
                "patterns_found": [],
                "collaboration_frequency": {},
                "success_patterns": [],
                "failure_patterns": []
            }

        # Analyze patterns
        collaboration_frequency = {}
        success_patterns = []
        failure_patterns = []

        for consensus in recent_consensus:
            # Track collaboration frequency
            participants = tuple(sorted(consensus.participants))
            collaboration_frequency[participants] = collaboration_frequency.get(participants, 0) + 1

            # Identify success patterns
            if consensus.consensus_reached:
                success_patterns.append({
                    "participants": consensus.participants,
                    "confidence": consensus.confidence,
                    "decision_type": consensus.final_decision.get("decision", "unknown")
                })
            else:
                failure_patterns.append({
                    "participants": consensus.participants,
                    "confidence": consensus.confidence,
                    "reasoning_length": len(consensus.reasoning_process)
                })

        # Find most successful patterns
        successful_participant_combos = {}
        for pattern in success_patterns:
            participants_key = tuple(sorted(pattern["participants"]))
            if participants_key not in successful_participant_combos:
                successful_participant_combos[participants_key] = {"count": 0, "avg_confidence": 0, "confidences": []}

            successful_participant_combos[participants_key]["count"] += 1
            successful_participant_combos[participants_key]["confidences"].append(pattern["confidence"])

        # Calculate average confidence for successful combos
        for combo in successful_participant_combos.values():
            combo["avg_confidence"] = sum(combo["confidences"]) / len(combo["confidences"])

        return {
            "analysis_period_days": days,
            "total_consensus_events": len(recent_consensus),
            "collaboration_frequency": {
                "-".join(participants): count
                for participants, count in collaboration_frequency.items()
            },
            "most_successful_collaborations": sorted(
                [
                    {
                        "participants": list(combo),
                        "success_count": data["count"],
                        "average_confidence": round(data["avg_confidence"], 3)
                    }
                    for combo, data in successful_participant_combos.items()
                ],
                key=lambda x: x["success_count"],
                reverse=True
            )[:5],
            "success_rate": round(
                sum(1 for c in recent_consensus if c.consensus_reached) / len(recent_consensus),
                3
            ),
            "average_confidence": round(
                sum(c.confidence for c in recent_consensus) / len(recent_consensus),
                3
            ),
            "patterns_found": len(success_patterns) + len(failure_patterns)
        }

    except Exception as e:
        logger.error("Failed to analyze collaboration patterns: {}", e)
        raise HTTPException(status_code=500, detail=f"Failed to analyze collaboration patterns: {str(e)}")


@router.post("/multi_agent/simulation")
async def simulate_collaborative_case(
    case_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Simulate a complete multi-agent collaborative case analysis.

    This demonstrates the full autonomous agent system with goal formulation,
    collaboration, consensus building, and decision making.
    """
    try:
        logger.info("Simulating collaborative case: {}", case_data.get("case_description", "unknown"))

        # Prepare context for multi-agent analysis
        context = {
            "session_id": case_data.get("session_id", "simulation_session"),
            "case_description": case_data.get("case_description", ""),
            "image_data": case_data.get("image_data"),
            "symptoms": case_data.get("symptoms"),
            "patient_info": case_data.get("patient_info", {}),
            "location": case_data.get("location"),
            "urgency": case_data.get("urgency", "medium")
        }

        # Run full multi-agent coordination
        result = await agent_coordinator.coordinate_analysis(context)

        # Add simulation metadata
        result["simulation_metadata"] = {
            "case_description": case_data.get("case_description"),
            "simulation_timestamp": datetime.now().isoformat(),
            "agents_involved": len(agent_coordinator.agents),
            "collaboration_type": "fully_autonomous"
        }

        return result

    except Exception as e:
        logger.error("Collaborative case simulation failed: {}", e)
        raise HTTPException(status_code=500, detail=f"Collaborative case simulation failed: {str(e)}")