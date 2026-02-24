export type DashboardMetric = {
  change: string;
  label: string;
  value: string;
};

export type MonthlyCasePoint = {
  critical: number;
  month: string;
  total: number;
};

export type TriageDistributionPoint = {
  color: string;
  count: number;
  level: "AMBER" | "GREEN" | "RED";
};

export type TurnaroundPoint = {
  avgHours: number;
  week: string;
};

export type DoctorDashboardData = {
  alerts: string[];
  monthlyCases: MonthlyCasePoint[];
  reportTurnaround: TurnaroundPoint[];
  summary: DashboardMetric[];
  triageDistribution: TriageDistributionPoint[];
};

export type PatientRecord = {
  age: number;
  id: string;
  lastStudy: string;
  name: string;
  riskLevel: "AMBER" | "GREEN" | "RED";
  summary: string;
};

export type ReportRecord = {
  createdAt: string;
  id: string;
  patientName: string;
  severity: "AMBER" | "GREEN" | "RED";
  status: "draft" | "finalized" | "reviewing";
  title: string;
};

export type NearbyCareCenter = {
  distanceKm: number;
  id: string;
  name: string;
  specialty: string;
  waitEstimate: string;
};

