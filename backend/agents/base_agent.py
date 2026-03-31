from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Callable
from datetime import datetime
from uuid import uuid4
from dataclasses import dataclass, field

from loguru import logger

from services.groq_llm import get_supervisor_llm
from services.agent_learning import adaptive_supervisor
from services.probabilistic_reasoning import (
    confidence_estimator,
    probabilistic_reasoner,
    bayesian_updater
)


@dataclass
class AgentMessage:
    """Message exchanged between agents."""

    sender: str
    receiver: str
    message_type: str  # "request", "response", "notification", "consensus"
    content: Dict[str, Any]
    message_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = field(default_factory=datetime.now)
    priority: int = 1  # 1=high, 2=medium, 3=low
    confidence: float = 1.0
    requires_response: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary for transmission."""
        return {
            "sender": self.sender,
            "receiver": self.receiver,
            "message_type": self.message_type,
            "content": self.content,
            "message_id": self.message_id,
            "timestamp": self.timestamp.isoformat(),
            "priority": self.priority,
            "confidence": self.confidence,
            "requires_response": self.requires_response,
            "metadata": self.metadata
        }


@dataclass
class AgentGoal:
    """Goal that an agent can formulate and pursue."""

    goal_id: str
    description: str
    priority: str  # "urgent", "high", "medium", "low"
    objective: str
    success_criteria: List[str]
    deadline: Optional[datetime] = None
    parent_goal_id: Optional[str] = None
    sub_goals: List[str] = field(default_factory=list)
    progress: float = 0.0
    status: str = "pending"  # "pending", "in_progress", "completed", "failed"
    created_at: datetime = field(default_factory=datetime.now)

    def is_urgent(self) -> bool:
        """Check if goal is urgent."""
        return self.priority in ["urgent", "high"]

    def is_overdue(self) -> bool:
        """Check if goal is past deadline."""
        if self.deadline is None:
            return False
        return datetime.now() > self.deadline


@dataclass
class AgentCapabilities:
    """Define what an agent can do."""

    agent_name: str
    tool_capabilities: List[str]
    perception_abilities: List[str]  # "vision", "text", "structured_data"
    reasoning_level: str  # "basic", "advanced", "expert"
    collaboration_style: str  # "independent", "cooperative", "competitive"
    specialization_domains: List[str]
    confidence_ranges: Dict[str, tuple]  # tool_name -> (min_confidence, max_confidence)
    max_concurrent_tasks: int = 3


class BaseAgent(ABC):
    """Base class for autonomous specialized agents."""

    def __init__(self, capabilities: AgentCapabilities):
        self.capabilities = capabilities
        self.message_queue: List[AgentMessage] = []
        self.goals: Dict[str, AgentGoal] = {}
        self.message_handlers: Dict[str, Callable] = {}
        self.collaboration_history: List[Dict[str, Any]] = []
        self.current_tasks: List[str] = []
        self.performance_metrics = {
            "tasks_completed": 0,
            "tasks_failed": 0,
            "average_confidence": 0.0,
            "collaboration_success": 0,
            "collaboration_failures": 0
        }

        # Initialize belief for each capability
        for tool in capabilities.tool_capabilities:
            base_confidence = capabilities.confidence_ranges.get(tool, (0.7, 0.9))[0]
            bayesian_updater.initialize_belief(tool, base_confidence)

        self._register_message_handlers()

    def _register_message_handlers(self) -> None:
        """Register default message handlers."""
        self.message_handlers = {
            "request": self._handle_request,
            "response": self._handle_response,
            "notification": self._handle_notification,
            "consensus": self._handle_consensus
        }

    @abstractmethod
    async def perceive(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Perceive environment and gather information."""
        pass

    @abstractmethod
    async def reason(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Reason about situation and form decisions."""
        pass

    @abstractmethod
    async def act(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Execute actions in the environment."""
        pass

    async def receive_message(self, message: AgentMessage) -> None:
        """Receive and process incoming message."""
        self.message_queue.append(message)
        await self._process_message(message)

    async def _process_message(self, message: AgentMessage) -> None:
        """Process a single message based on its type."""
        handler = self.message_handlers.get(message.message_type)
        if handler:
            try:
                await handler(message)
            except Exception as e:
                logger.error(
                    "Agent {} failed to process message {}: {}",
                    self.capabilities.agent_name, message.message_id, e
                )

    async def _handle_request(self, message: AgentMessage) -> None:
        """Handle request message."""
        logger.info(
            "Agent {} received request from {}: {}",
            self.capabilities.agent_name, message.sender, message.content
        )

        # Process the request
        response = await self._respond_to_request(message)

        if message.requires_response:
            response_message = AgentMessage(
                sender=self.capabilities.agent_name,
                receiver=message.sender,
                message_type="response",
                content=response,
                in_reply_to=message.message_id,
                confidence=response.get("confidence", 1.0)
            )

            await self._send_message(response_message)

    async def _respond_to_request(self, request: AgentMessage) -> Dict[str, Any]:
        """Generate response to request."""
        # This should be implemented by specific agents
        return {
            "status": "acknowledged",
            "message": "Request received and being processed",
            "confidence": 0.8
        }

    async def _handle_response(self, message: AgentMessage) -> None:
        """Handle response message."""
        logger.info(
            "Agent {} received response from {}: {}",
            self.capabilities.agent_name, message.sender, message.content
        )
        # Process response and potentially take action

    async def _handle_notification(self, message: AgentMessage) -> None:
        """Handle notification message."""
        logger.info(
            "Agent {} received notification from {}: {}",
            self.capabilities.agent_name, message.sender, message.content
        )
        # Process notification (no response required)

    async def _handle_consensus(self, message: AgentMessage) -> None:
        """Handle consensus request from coordinator."""
        logger.info(
            "Agent {} received consensus request from {}: {}",
            self.capabilities.agent_name, message.sender, message.content
        )

        # Generate own assessment for consensus
        my_assessment = await self._generate_consensus_assessment(message.content)

        # Send back assessment
        response = AgentMessage(
            sender=self.capabilities.agent_name,
            receiver=message.sender,
            message_type="response",
            content={"assessment": my_assessment},
            confidence=my_assessment.get("confidence", 1.0)
        )

        await self._send_message(response)

    async def _generate_consensus_assessment(self, topic: Dict[str, Any]) -> Dict[str, Any]:
        """Generate assessment for consensus building."""
        # Default implementation - should be overridden by specialized agents
        return {
            "agent": self.capabilities.agent_name,
            "assessment": "pending_detailed_analysis",
            "confidence": 0.7,
            "reasoning": "Base agent assessment"
        }

    async def _send_message(self, message: AgentMessage) -> None:
        """Send message to another agent."""
        # This will be handled by the agent coordinator
        logger.info(
            "Agent {} sending message to {}: {}",
            message.sender, message.receiver, message.message_type
        )
        # Implementation depends on the coordination system

    async def formulate_goals(self, context: Dict[str, Any]) -> List[AgentGoal]:
        """Formulate goals based on current context."""
        goals = []

        # Analyze context to identify needed actions
        urgent_tasks = self._identify_urgent_tasks(context)
        for task in urgent_tasks:
            goal = AgentGoal(
                goal_id=f"{self.capabilities.agent_name}_goal_{len(self.goals)}",
                description=task["description"],
                priority="urgent",
                objective=task["objective"],
                success_criteria=task.get("success_criteria", []),
                created_at=datetime.now()
            )
            goals.append(goal)
            self.goals[goal.goal_id] = goal

        # Identify improvement opportunities
        improvements = self._identify_improvements(context)
        for improvement in improvements:
            goal = AgentGoal(
                goal_id=f"{self.capabilities.agent_name}_goal_{len(self.goals)}",
                description=improvement["description"],
                priority="medium",
                objective=improvement["objective"],
                success_criteria=improvement.get("success_criteria", []),
                created_at=datetime.now()
            )
            goals.append(goal)
            self.goals[goal.goal_id] = goal

        logger.info(
            "Agent {} formulated {} goals: {}",
            self.capabilities.agent_name, len(goals),
            [g.description for g in goals]
        )

        return goals

    def _identify_urgent_tasks(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Identify urgent tasks that need attention."""
        # Base implementation - should be overridden
        return []

    def _identify_improvements(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Identify opportunities for improvement."""
        # Base implementation - should be overridden
        return []

    async def select_action(self, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Select action based on reasoning and goals."""
        # Consider current goals
        active_goals = [g for g in self.goals.values() if g.status == "in_progress"]
        urgent_goals = [g for g in active_goals if g.is_urgent()]

        if urgent_goals:
            # Focus on urgent goals first
            goal = urgent_goals[0]
            action = await self._plan_action_for_goal(goal, context)
            return action
        elif active_goals:
            # Work on active goals
            goal = active_goals[0]
            action = await self._plan_action_for_goal(goal, context)
            return action
        else:
            # No active goals - could formulate new ones
            return None

    async def _plan_action_for_goal(self, goal: AgentGoal, context: Dict[str, Any]) -> Dict[str, Any]:
        """Plan action to achieve a specific goal."""
        # Base implementation - should be overridden
        return {
            "action_type": "unknown",
            "goal_id": goal.goal_id,
            "description": f"Action to achieve {goal.description}",
            "confidence": 0.7
        }

    async def execute_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Execute action and update learning."""
        action_type = action.get("action_type", "unknown")

        # Track task
        task_id = str(uuid4())
        self.current_tasks.append(task_id)

        try:
            # Execute the action
            result = await self.act(action)

            # Update metrics
            self.performance_metrics["tasks_completed"] += 1

            # Update beliefs
            success = result.get("success", False)
            if action_type in self.capabilities.tool_capabilities:
                bayesian_updater.update_belief(action_type, success)

            # Record collaboration if it was a collaborative action
            if action.get("collaborative"):
                if success:
                    self.performance_metrics["collaboration_success"] += 1
                else:
                    self.performance_metrics["collaboration_failures"] += 1

            logger.info(
                "Agent {} successfully executed action {}: {}",
                self.capabilities.agent_name, task_id, action_type
            )

            return result

        except Exception as e:
            # Record failure
            self.performance_metrics["tasks_failed"] += 1

            logger.error(
                "Agent {} failed to execute action {}: {}",
                self.capabilities.agent_name, task_id, e
            )

            return {
                "success": False,
                "error": str(e),
                "action": action_type
            }

        finally:
            # Remove from current tasks
            if task_id in self.current_tasks:
                self.current_tasks.remove(task_id)

    async def collaborate_with_agent(self, other_agent: BaseAgent, task: Dict[str, Any]) -> Dict[str, Any]:
        """Collaborate with another agent on a task."""
        logger.info(
            "Agent {} collaborating with {} on task: {}",
            self.capabilities.agent_name, other_agent.capabilities.agent_name, task
        )

        # Send collaboration request
        request = AgentMessage(
            sender=self.capabilities.agent_name,
            receiver=other_agent.capabilities.agent_name,
            message_type="request",
            content={
                "task_type": "collaboration",
                "task": task,
                "requested_capabilities": task.get("required_capabilities", [])
            },
            priority=1 if task.get("urgent") else 2
        )

        # Record collaboration
        self.collaboration_history.append({
            "partner": other_agent.capabilities.agent_name,
            "task": task,
            "timestamp": datetime.now(),
            "status": "initiated"
        })

        # Send the message (implementation depends on coordinator)
        await self._send_message(request)

        # Wait for response (timeout handling should be added)
        # This is simplified - real implementation would use async coordination

        return {
            "status": "collaboration_requested",
            "partner": other_agent.capabilities.agent_name,
            "task": task
        }

    def get_performance_summary(self) -> Dict[str, Any]:
        """Get summary of agent performance."""
        total_tasks = self.performance_metrics["tasks_completed"] + self.performance_metrics["tasks_failed"]
        success_rate = (
            self.performance_metrics["tasks_completed"] / total_tasks
            if total_tasks > 0 else 0.0
        )

        collaboration_rate = (
            self.performance_metrics["collaboration_success"] /
            (self.performance_metrics["collaboration_success"] + self.performance_metrics["collaboration_failures"])
            if (self.performance_metrics["collaboration_success"] + self.performance_metrics["collaboration_failures"]) > 0
            else 0.0
        )

        return {
            "agent_name": self.capabilities.agent_name,
            "tasks_completed": self.performance_metrics["tasks_completed"],
            "tasks_failed": self.performance_metrics["tasks_failed"],
            "success_rate": round(success_rate, 3),
            "collaboration_success": self.performance_metrics["collaboration_success"],
            "collaboration_failures": self.performance_metrics["collaboration_failures"],
            "collaboration_rate": round(collaboration_rate, 3),
            "active_goals": len([g for g in self.goals.values() if g.status == "in_progress"]),
            "completed_goals": len([g for g in self.goals.values() if g.status == "completed"]),
            "current_tasks": len(self.current_tasks),
            "message_queue_length": len(self.message_queue)
        }