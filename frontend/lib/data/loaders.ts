import { doctorDashboardMockData } from "@/lib/mock-data/doctor-dashboard";
import { nearbyCareMockData } from "@/lib/mock-data/nearby-care";
import { doctorPatientsMockData } from "@/lib/mock-data/patients";
import {
    doctorReportsMockData,
    patientReportsMockData,
} from "@/lib/mock-data/reports";

import { DATA_SOURCE_MODE, USE_MOCK_DATA } from "./mode";
import type {
    DoctorDashboardData,
    NearbyCareCenter,
    PatientRecord,
    ReportRecord,
} from "./types";

type MetricsResponse = {
  active_sessions: number;
  stored_reports: number;
};

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api";

function cloneData<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
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

export function getDataSourceLabel(): string {
  return DATA_SOURCE_MODE.toUpperCase();
}

export async function getDoctorDashboardData(): Promise<DoctorDashboardData> {
  const base = cloneData(doctorDashboardMockData);

  if (USE_MOCK_DATA) {
    return base;
  }

  try {
    const metrics = await fetchApi<MetricsResponse>("/metrics");
    base.summary = base.summary.map((item) => {
      if (item.label === "Cases Reviewed") {
        return { ...item, value: String(Math.max(metrics.active_sessions, 0)) };
      }
      if (item.label === "Reports In Progress") {
        return { ...item, value: String(Math.max(metrics.stored_reports, 0)) };
      }
      return item;
    });
    return base;
  } catch {
    return base;
  }
}

export async function getDoctorPatients(actorId?: string): Promise<PatientRecord[]> {
  // Always keep mock data wired; switch to real data by setting NEXT_PUBLIC_DATA_SOURCE=api
  if (USE_MOCK_DATA || !actorId) {
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
    // fallback to mock on API error so the UI never breaks
    return cloneData(doctorPatientsMockData);
  }
}

export async function getDoctorReports(actorId?: string): Promise<ReportRecord[]> {
  // Always keep mock data wired; switch to real data by setting NEXT_PUBLIC_DATA_SOURCE=api
  if (USE_MOCK_DATA || !actorId) {
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
    return cloneData(doctorReportsMockData);
  }
}

export async function getPatientReports(actorId?: string): Promise<ReportRecord[]> {
  // Always keep mock data wired; switch to real data by setting NEXT_PUBLIC_DATA_SOURCE=api
  if (USE_MOCK_DATA || !actorId) {
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
    return cloneData(patientReportsMockData);
  }
}

export async function getNearbyCareCenters(): Promise<NearbyCareCenter[]> {
  return cloneData(nearbyCareMockData);
}
