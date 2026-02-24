import type { DoctorDashboardData } from "@/lib/data/types";

export const doctorDashboardMockData: DoctorDashboardData = {
  alerts: [
    "2 red-triage cases require immediate escalation review.",
    "Average report turnaround increased by 1.4h this week.",
    "One study flagged for low image quality and re-upload.",
  ],
  monthlyCases: [
    { critical: 6, month: "Jan", total: 34 },
    { critical: 4, month: "Feb", total: 29 },
    { critical: 7, month: "Mar", total: 38 },
    { critical: 5, month: "Apr", total: 31 },
    { critical: 8, month: "May", total: 42 },
    { critical: 6, month: "Jun", total: 37 },
  ],
  reportTurnaround: [
    { avgHours: 6.1, week: "W1" },
    { avgHours: 5.3, week: "W2" },
    { avgHours: 6.8, week: "W3" },
    { avgHours: 5.7, week: "W4" },
  ],
  summary: [
    { change: "+8% vs last month", label: "Cases Reviewed", value: "211" },
    { change: "-12% vs last month", label: "Critical Findings", value: "22" },
    { change: "+3 pending", label: "Reports In Progress", value: "17" },
    { change: "Target < 6h", label: "Avg Turnaround", value: "5.9h" },
  ],
  triageDistribution: [
    { color: "#d99525", count: 61, level: "AMBER" },
    { color: "#4f5d95", count: 22, level: "RED" },
    { color: "#6b8b73", count: 128, level: "GREEN" },
  ],
};

