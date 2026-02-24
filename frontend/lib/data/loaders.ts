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

export async function getDoctorPatients(): Promise<PatientRecord[]> {
  return cloneData(doctorPatientsMockData);
}

export async function getDoctorReports(): Promise<ReportRecord[]> {
  return cloneData(doctorReportsMockData);
}

export async function getPatientReports(): Promise<ReportRecord[]> {
  return cloneData(patientReportsMockData);
}

export async function getNearbyCareCenters(): Promise<NearbyCareCenter[]> {
  return cloneData(nearbyCareMockData);
}

