"use client";

import { useState, useEffect } from "react";
import { Brain, Users, TrendingUp, Activity } from "lucide-react";

interface AgentDetail {
  status: string;
  active_goals: number;
  completed_goals: number;
  message_queue_length: number;
  current_tasks: number;
}

interface MultiAgentStatus {
  coordination_id?: string;
  agents_involved: string[];
  consensus_reached: boolean;
  confidence: number;
  coordination_time: number;
  total_agents: number;
  active_goals: number;
  agent_details: Record<string, AgentDetail>;
}

interface AgentGoal {
  goal_id: string;
  description: string;
  priority: string;
  status: string;
  progress: number;
  agent: string;
}

interface ConsensusHistory {
  consensus_id: string;
  topic: string;
  participants: string[];
  participant_count: number;
  consensus_reached: boolean;
  confidence: number;
  timestamp: string;
}

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null;

const asNumber = (value: unknown, fallback = 0): number =>
  typeof value === "number" && Number.isFinite(value) ? value : fallback;

const asString = (value: unknown, fallback = ""): string =>
  typeof value === "string" ? value : fallback;

const parseAgentDetail = (value: unknown): AgentDetail => {
  if (!isRecord(value)) {
    return {
      status: "unknown",
      active_goals: 0,
      completed_goals: 0,
      message_queue_length: 0,
      current_tasks: 0
    };
  }

  return {
    status: asString(value.status, "unknown"),
    active_goals: asNumber(value.active_goals),
    completed_goals: asNumber(value.completed_goals),
    message_queue_length: asNumber(value.message_queue_length),
    current_tasks: asNumber(value.current_tasks)
  };
};

const parseMultiAgentStatus = (value: unknown): MultiAgentStatus | null => {
  if (!isRecord(value)) return null;

  const rawAgentDetails = isRecord(value.agent_details) ? value.agent_details : {};
  const agentDetails: Record<string, AgentDetail> = Object.fromEntries(
    Object.entries(rawAgentDetails).map(([agentName, details]) => [agentName, parseAgentDetail(details)])
  );

  const statistics = isRecord(value.statistics) ? value.statistics : undefined;
  const coordinationMetrics =
    statistics && isRecord(statistics.coordination_metrics)
      ? statistics.coordination_metrics
      : undefined;

  const successfulConsensus = asNumber(coordinationMetrics?.successful_consensus);
  const totalCollaborations = asNumber(coordinationMetrics?.total_collaborations);
  const confidenceFromMetrics =
    totalCollaborations > 0 ? successfulConsensus / totalCollaborations : 0;

  const agentsInvolved =
    Array.isArray(value.agents_involved)
      ? value.agents_involved.filter((agent): agent is string => typeof agent === "string")
      : Object.keys(agentDetails);

  return {
    coordination_id:
      typeof value.coordination_id === "string" ? value.coordination_id : undefined,
    agents_involved: agentsInvolved,
    consensus_reached:
      typeof value.consensus_reached === "boolean"
        ? value.consensus_reached
        : successfulConsensus > 0,
    confidence: asNumber(value.confidence, confidenceFromMetrics),
    coordination_time: asNumber(
      value.coordination_time,
      asNumber(coordinationMetrics?.average_consensus_time)
    ),
    total_agents: asNumber(
      value.total_agents,
      asNumber(statistics?.total_agents, agentsInvolved.length)
    ),
    active_goals: asNumber(
      value.active_goals,
      Object.values(agentDetails).reduce((sum, details) => sum + details.active_goals, 0)
    ),
    agent_details: agentDetails
  };
};

const parseAgentGoals = (value: unknown): AgentGoal[] => {
  if (!isRecord(value) || !isRecord(value.all_agent_goals)) {
    return [];
  }

  const goalsByAgent = value.all_agent_goals;
  const flattenedGoals: AgentGoal[] = [];

  for (const [agentName, agentGoals] of Object.entries(goalsByAgent)) {
    if (!Array.isArray(agentGoals)) continue;

    agentGoals.forEach((goal, index) => {
      if (!isRecord(goal)) return;

      flattenedGoals.push({
        goal_id: asString(goal.goal_id, `${agentName}-${index}`),
        description: asString(goal.description, "Untitled goal"),
        priority: asString(goal.priority, "medium"),
        status: asString(goal.status, "pending"),
        progress: asNumber(goal.progress),
        agent: agentName
      });
    });
  }

  return flattenedGoals;
};

const parseConsensusHistory = (value: unknown): ConsensusHistory[] => {
  if (!isRecord(value) || !Array.isArray(value.consensus_history)) {
    return [];
  }

  return value.consensus_history.flatMap((entry, index) => {
    if (!isRecord(entry)) return [];

    const participants = Array.isArray(entry.participants)
      ? entry.participants.filter((participant): participant is string => typeof participant === "string")
      : [];

    return [
      {
        consensus_id: asString(entry.consensus_id, `consensus-${index}`),
        topic: asString(entry.topic, "Untitled consensus"),
        participants,
        participant_count: asNumber(entry.participant_count, participants.length),
        consensus_reached:
          typeof entry.consensus_reached === "boolean" ? entry.consensus_reached : false,
        confidence: asNumber(entry.confidence),
        timestamp: asString(entry.timestamp, "")
      }
    ];
  });
};

export default function MultiAgentInsights({ sessionId }: { sessionId: string }) {
  const [status, setStatus] = useState<MultiAgentStatus | null>(null);
  const [goals, setGoals] = useState<AgentGoal[]>([]);
  const [consensusHistory, setConsensusHistory] = useState<ConsensusHistory[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Fetch multi-agent status
    fetchMultiAgentStatus();
    // Fetch agent goals
    fetchAgentGoals();
    // Fetch consensus history
    fetchConsensusHistory();

    // Set up polling for real-time updates
    const interval = setInterval(() => {
      fetchMultiAgentStatus();
    }, 5000); // Poll every 5 seconds

    return () => clearInterval(interval);
  }, [sessionId]);

  const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api";

  async function fetchMultiAgentStatus() {
    try {
      const response = await fetch(`${API_BASE_URL}/multi_agent/status`);
      if (response.ok) {
        const data: unknown = await response.json();
        const parsedStatus = parseMultiAgentStatus(data);
        if (parsedStatus) {
          setStatus(parsedStatus);
        }
      }
    } catch (error) {
      console.error("Failed to fetch multi-agent status:", error);
    } finally {
      setLoading(false);
    }
  }

  async function fetchAgentGoals() {
    try {
      const response = await fetch(`${API_BASE_URL}/multi_agent/goals`);
      if (response.ok) {
        const data: unknown = await response.json();
        setGoals(parseAgentGoals(data));
      }
    } catch (error) {
      console.error("Failed to fetch agent goals:", error);
    }
  }

  async function fetchConsensusHistory() {
    try {
      const response = await fetch(`${API_BASE_URL}/multi_agent/consensus/history?limit=10`);
      if (response.ok) {
        const data: unknown = await response.json();
        setConsensusHistory(parseConsensusHistory(data));
      }
    } catch (error) {
      console.error("Failed to fetch consensus history:", error);
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case "pending":
        return "bg-yellow-100 text-yellow-800";
      case "in_progress":
        return "bg-blue-100 text-blue-800";
      case "completed":
        return "bg-green-100 text-green-800";
      case "failed":
        return "bg-red-100 text-red-800";
      default:
        return "bg-gray-100 text-gray-800";
    }
  };

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case "urgent":
        return "text-red-600 font-semibold";
      case "high":
        return "text-orange-600 font-semibold";
      case "medium":
        return "text-yellow-600";
      case "low":
        return "text-green-600";
      default:
        return "text-gray-600";
    }
  };

  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 0.8) return "text-green-600";
    if (confidence >= 0.6) return "text-yellow-600";
    return "text-red-600";
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
        <p className="ml-4 text-gray-600">Loading multi-agent status...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6 p-6">
      {/* Multi-Agent Status */}
      <div className="bg-white rounded-lg shadow-lg p-6">
        <div className="flex items-center gap-3 mb-6">
          <div className="p-3 bg-blue-100 rounded-lg">
            <Brain className="h-8 w-8 text-blue-600" />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-gray-900">Multi-Agent System Status</h2>
            <p className="text-sm text-gray-600">
              Real-time autonomous agent coordination and collaboration
            </p>
          </div>
        </div>

        {status && (
          <div className="space-y-4">
            {/* Coordination Metrics */}
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-gray-50 rounded-lg p-4">
                <div className="text-sm text-gray-600 mb-1">Agents Involved</div>
                <div className="text-2xl font-bold text-gray-900">
                  {status.agents_involved?.length || 0}
                </div>
              </div>

              <div className="bg-gray-50 rounded-lg p-4">
                <div className="text-sm text-gray-600 mb-1">Consensus Rate</div>
                <div className={`text-2xl font-bold ${getConfidenceColor(status.confidence)}`}>
                  {((status.confidence || 0) * 100).toFixed(0)}%
                </div>
              </div>

              <div className="bg-gray-50 rounded-lg p-4">
                <div className="text-sm text-gray-600 mb-1">Coordination Time</div>
                <div className="text-2xl font-bold text-gray-900">
                  {status.coordination_time?.toFixed(2) || 0}s
                </div>
              </div>

              <div className="bg-gray-50 rounded-lg p-4">
                <div className="text-sm text-gray-600 mb-1">Active Goals</div>
                <div className="text-2xl font-bold text-gray-900">
                  {status.active_goals || 0}
                </div>
              </div>
            </div>

            {/* Agent Details */}
            <div className="border-t pt-4">
              <h3 className="text-lg font-semibold text-gray-900 mb-3">Agent Details</h3>
              <div className="space-y-3">
                {Object.entries(status.agent_details).map(([agentName, details]) => (
                    <div key={agentName} className="bg-white border rounded-lg p-4">
                      <div className="flex items-center gap-2 mb-2">
                        <div className="p-2 bg-indigo-100 rounded-lg">
                          <Users className="h-5 w-5 text-indigo-600" />
                        </div>
                        <div>
                          <h4 className="text-lg font-semibold text-gray-900">
                            {agentName.replace("_", " ").toUpperCase()}
                          </h4>
                          <span className={`ml-2 px-3 py-1 rounded-full text-xs font-medium ${getStatusColor(details.status || "unknown")}`}>
                            {details.status?.toUpperCase() || "UNKNOWN"}
                          </span>
                        </div>
                      </div>

                      <div className="grid grid-cols-2 gap-4 text-sm">
                        <div>
                          <span className="text-gray-600">Active Goals:</span>
                          <span className="ml-2 font-semibold text-gray-900">
                            {details.active_goals || 0}
                          </span>
                        </div>
                        <div>
                          <span className="text-gray-600">Completed Goals:</span>
                          <span className="ml-2 font-semibold text-gray-900">
                            {details.completed_goals || 0}
                          </span>
                        </div>
                        <div>
                          <span className="text-gray-600">Current Tasks:</span>
                          <span className="ml-2 font-semibold text-gray-900">
                            {details.current_tasks || 0}
                          </span>
                        </div>
                        <div>
                          <span className="text-gray-600">Message Queue:</span>
                          <span className="ml-2 font-semibold text-gray-900">
                            {details.message_queue_length || 0}
                          </span>
                        </div>
                      </div>
                    </div>
                  ))
                }
              </div>
            </div>
          </div>
        )}

        {!status && (
          <div className="text-center py-12">
            <p className="text-gray-600">Multi-agent system not currently active</p>
          </div>
        )}
      </div>

      {/* Agent Goals */}
      <div className="bg-white rounded-lg shadow-lg p-6">
        <div className="flex items-center gap-3 mb-6">
          <div className="p-3 bg-green-100 rounded-lg">
            <TrendingUp className="h-8 w-8 text-green-600" />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-gray-900">Agent Goals</h2>
            <p className="text-sm text-gray-600">
              Self-formulated objectives from autonomous agents
            </p>
          </div>
        </div>

        {goals.length > 0 ? (
          <div className="space-y-3">
            {goals.map((goal) => (
              <div key={goal.goal_id} className="bg-white border rounded-lg p-4">
                <div className="flex items-start justify-between mb-2">
                  <div className="flex-1">
                    <div className="text-xs text-gray-600 mb-1">
                      {goal.agent?.toUpperCase() || "AGENT"}
                    </div>
                    <h4 className="text-lg font-semibold text-gray-900">
                      {goal.description}
                    </h4>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={`px-3 py-1 rounded-full text-xs font-medium ${getStatusColor(goal.status)}`}>
                      {goal.status?.toUpperCase() || "UNKNOWN"}
                    </span>
                    <span className={`text-xs font-medium ${getPriorityColor(goal.priority)}`}>
                      {goal.priority.toUpperCase()}
                    </span>
                  </div>
                </div>

                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-gray-600">Progress:</span>
                    <div className="flex-1 h-2 bg-gray-200 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-blue-600 transition-all duration-300"
                        style={{ width: `${goal.progress}%` }}
                      />
                    </div>
                    <span className="text-sm font-semibold text-gray-900">
                      {goal.progress.toFixed(0)}%
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-8">
            <p className="text-gray-600">No active agent goals found</p>
          </div>
        )}
      </div>

      {/* Consensus History */}
      <div className="bg-white rounded-lg shadow-lg p-6">
        <div className="flex items-center gap-3 mb-6">
          <div className="p-3 bg-purple-100 rounded-lg">
            <Activity className="h-8 w-8 text-purple-600" />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-gray-900">Recent Consensus</h2>
            <p className="text-sm text-gray-600">
              Agent collaboration and decision-making history
            </p>
          </div>
        </div>

        {consensusHistory.length > 0 ? (
          <div className="space-y-3">
            {consensusHistory.map((consensus) => (
              <div key={consensus.consensus_id} className="bg-white border rounded-lg p-4">
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <div className="text-xs text-gray-600 mb-1">
                      {new Date(consensus.timestamp).toLocaleString()}
                    </div>
                    <h4 className="text-lg font-semibold text-gray-900">
                      {consensus.topic.substring(0, 100)}...
                    </h4>
                  </div>
                  <div className="text-right">
                    <div className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${
                      consensus.consensus_reached
                        ? "bg-green-100 text-green-800"
                        : "bg-red-100 text-red-800"
                    }`}>
                      {consensus.consensus_reached ? "CONSENSUS" : "NO CONSENSUS"}
                    </div>
                    <div className={`ml-2 px-3 py-1 rounded-full text-sm font-semibold ${getConfidenceColor(consensus.confidence)}`}>
                      {consensus.confidence.toFixed(2)}
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <span className="text-gray-600">Participants:</span>
                    <div className="mt-1">
                      {consensus.participants.map((participant) => (
                        <span
                          key={participant}
                          className="inline-block bg-indigo-100 text-indigo-800 px-2 py-1 rounded text-xs font-medium mr-1 mb-1"
                        >
                          {participant.replace("_", " ").toUpperCase()}
                        </span>
                      ))}
                    </div>
                  </div>
                  <div>
                    <span className="text-gray-600">Participant Count:</span>
                    <div className="mt-1 text-2xl font-bold text-gray-900">
                      {consensus.participant_count}
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-8">
            <p className="text-gray-600">No consensus history available</p>
          </div>
        )}
      </div>
    </div>
  );
}
