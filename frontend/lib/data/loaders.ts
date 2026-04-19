import { doctorDashboardMockData } from "@/lib/mock-data/doctor-dashboard";
import { nearbyCareMockData } from "@/lib/mock-data/nearby-care";
import { doctorPatientsMockData } from "@/lib/mock-data/patients";
import {
    doctorReportsMockData,
    patientReportsMockData,
} from "@/lib/mock-data/reports";

import {
  DATA_SOURCE_MODE,
  getDataSourceLabelForMode,
  type DataSourceMode,
} from "./mode";
import type {
    DoctorDashboardData,
    DashboardMetric,
    MonthlyCasePoint,
    TurnaroundPoint,
    TriageDistributionPoint,
    NearbyCareCenter,
    PatientRecord,
    ReportRecord,
} from "./types";

type DoctorDashboardApiResponse = Partial<DoctorDashboardData>;

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api";

type DataLoaderOptions = {
  mode?: DataSourceMode;
};

function cloneData<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

function emptyDoctorDashboardData(base: DoctorDashboardData): DoctorDashboardData {
  return {
    summary: base.summary.map((item) => ({
      ...item,
      value: item.label === "Avg Turnaround" ? "0.0h" : "0",
      change: "Live data unavailable",
    })),
    monthlyCases: base.monthlyCases.map((item) => ({
      ...item,
      total: 0,
      critical: 0,
    })),
    triageDistribution: base.triageDistribution.map((item) => ({
      ...item,
      count: 0,
    })),
    reportTurnaround: base.reportTurnaround.map((item) => ({
      ...item,
      avgHours: 0,
    })),
    alerts: ["Live mode is enabled but dashboard data is currently unavailable."],
  };
}

function resolveMode(options?: DataLoaderOptions): DataSourceMode {
  return options?.mode ?? DATA_SOURCE_MODE;
}

function shouldUseMockData(options?: DataLoaderOptions): boolean {
  return resolveMode(options) === "mock";
}

async function fetchApi<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(`API request failed: ${path}`);
  }

  return (await response.json()) as T;
}

export function getDataSourceLabel(options?: DataLoaderOptions): string {
  return getDataSourceLabelForMode(resolveMode(options));
}

export async function getDoctorDashboardData(
  actorId?: string,
  options?: DataLoaderOptions
): Promise<DoctorDashboardData> {
  const base = cloneData(doctorDashboardMockData);

  if (shouldUseMockData(options) || !actorId) {
    return base;
  }

  try {
    const params = new URLSearchParams({ actor_id: actorId, actor_role: "doctor" });
    const live = await fetchApi<DoctorDashboardApiResponse>(
      `/dashboard/doctor/overview?${params}`
    );

    const summary: DashboardMetric[] = Array.isArray(live.summary)
      ? live.summary.map((item, index) => ({
          label: String(item?.label ?? base.summary[index]?.label ?? "Metric"),
          value: String(item?.value ?? base.summary[index]?.value ?? "0"),
          change: String(item?.change ?? base.summary[index]?.change ?? ""),
        }))
      : base.summary;

    const monthlyCases: MonthlyCasePoint[] = Array.isArray(live.monthlyCases)
      ? live.monthlyCases.map((item, index) => ({
          month: String(item?.month ?? base.monthlyCases[index]?.month ?? `M${index + 1}`),
          total: Number(item?.total ?? base.monthlyCases[index]?.total ?? 0),
          critical: Number(item?.critical ?? base.monthlyCases[index]?.critical ?? 0),
        }))
      : base.monthlyCases;

    const triageDistribution: TriageDistributionPoint[] = Array.isArray(live.triageDistribution)
      ? live.triageDistribution.map((item, index) => ({
          level: (["RED", "AMBER", "GREEN"].includes(String(item?.level))
            ? item?.level
            : base.triageDistribution[index]?.level ?? "GREEN") as TriageDistributionPoint["level"],
          count: Number(item?.count ?? base.triageDistribution[index]?.count ?? 0),
          color: String(item?.color ?? base.triageDistribution[index]?.color ?? "#6b8b73"),
        }))
      : base.triageDistribution;

    const reportTurnaround: TurnaroundPoint[] = Array.isArray(live.reportTurnaround)
      ? live.reportTurnaround.map((item, index) => ({
          week: String(item?.week ?? base.reportTurnaround[index]?.week ?? `W${index + 1}`),
          avgHours: Number(item?.avgHours ?? base.reportTurnaround[index]?.avgHours ?? 0),
        }))
      : base.reportTurnaround;

    const alerts = Array.isArray(live.alerts)
      ? live.alerts.map((item) => String(item))
      : base.alerts;

    return {
      summary,
      monthlyCases,
      triageDistribution,
      reportTurnaround,
      alerts,
    };
  } catch {
    return emptyDoctorDashboardData(base);
  }
}

export async function getDoctorPatients(
  actorId?: string,
  options?: DataLoaderOptions
): Promise<PatientRecord[]> {
  // Mock mode serves fixtures; live mode reads backend and returns [] on failure.
  if (shouldUseMockData(options) || !actorId) {
    return cloneData(doctorPatientsMockData);
  }

  try {
    const params = new URLSearchParams({ actor_id: actorId, actor_role: "doctor" });
    const raw = await fetchApi<Record<string, unknown>[]>(`/patients?${params}`);
    return raw.map((p) => ({
      id: String(p.id ?? ""),
      name: String(p.name ?? "Unknown"),
      age: Number(p.age ?? 0),
      lastStudy: String(p.lastStudy ?? ""),
      riskLevel: (["RED", "AMBER", "GREEN"].includes(String(p.riskLevel)) ? p.riskLevel : "GREEN") as PatientRecord["riskLevel"],
      summary: String(p.summary ?? ""),
    }));
  } catch {
    return [];
  }
}

export async function getDoctorReports(
  actorId?: string,
  options?: DataLoaderOptions
): Promise<ReportRecord[]> {
  // Mock mode serves fixtures; live mode reads backend and returns [] on failure.
  if (shouldUseMockData(options) || !actorId) {
    return cloneData(doctorReportsMockData);
  }

  try {
    const params = new URLSearchParams({ actor_id: actorId, actor_role: "doctor" });
    const raw = await fetchApi<Record<string, unknown>[]>(`/reports/list?${params}`);
    return raw.map((r) => ({
      id: String(r.id ?? ""),
      patientName: String(r.patientName ?? "Unknown"),
      title: String(r.title ?? "Report"),
      pdfUrl: r.pdfUrl ? String(r.pdfUrl) : undefined,
      severity: (["RED", "AMBER", "GREEN"].includes(String(r.severity)) ? r.severity : "GREEN") as ReportRecord["severity"],
      status: (["draft", "reviewing", "finalized"].includes(String(r.status)) ? r.status : "finalized") as ReportRecord["status"],
      createdAt: String(r.createdAt ?? new Date().toISOString()),
    }));
  } catch {
    return [];
  }
}

export async function getPatientReports(
  actorId?: string,
  options?: DataLoaderOptions
): Promise<ReportRecord[]> {
  // Mock mode serves fixtures; live mode reads backend and returns [] on failure.
  if (shouldUseMockData(options) || !actorId) {
    return cloneData(patientReportsMockData);
  }

  try {
    const params = new URLSearchParams({ actor_id: actorId, actor_role: "patient" });
    const raw = await fetchApi<Record<string, unknown>[]>(`/reports/list?${params}`);
    return raw.map((r) => ({
      id: String(r.id ?? ""),
      patientName: String(r.patientName ?? "You"),
      title: String(r.title ?? "Report"),
      pdfUrl: r.pdfUrl ? String(r.pdfUrl) : undefined,
      severity: (["RED", "AMBER", "GREEN"].includes(String(r.severity)) ? r.severity : "GREEN") as ReportRecord["severity"],
      status: (["draft", "reviewing", "finalized"].includes(String(r.status)) ? r.status : "finalized") as ReportRecord["status"],
      createdAt: String(r.createdAt ?? new Date().toISOString()),
    }));
  } catch {
    return [];
  }
}

export async function getNearbyCareCenters(): Promise<NearbyCareCenter[]> {
  return cloneData(nearbyCareMockData);
}
