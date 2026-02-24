import type { ReportRecord } from "@/lib/data/types";

export const doctorReportsMockData: ReportRecord[] = [
  {
    createdAt: "2026-02-24T09:20:00Z",
    id: "REP-9001",
    patientName: "Anita Rao",
    severity: "AMBER",
    status: "reviewing",
    title: "Right Wrist X-ray Follow-up",
  },
  {
    createdAt: "2026-02-23T14:10:00Z",
    id: "REP-9002",
    patientName: "Nikhil Sharma",
    severity: "GREEN",
    status: "finalized",
    title: "Left Hand Trauma Screening",
  },
  {
    createdAt: "2026-02-23T11:35:00Z",
    id: "REP-9003",
    patientName: "Priya Menon",
    severity: "RED",
    status: "draft",
    title: "Knee Injury Acute Assessment",
  },
];

export const patientReportsMockData: ReportRecord[] = [
  {
    createdAt: "2026-02-24T09:20:00Z",
    id: "PREP-1401",
    patientName: "You",
    severity: "AMBER",
    status: "reviewing",
    title: "Latest Wrist Study",
  },
  {
    createdAt: "2026-01-19T15:55:00Z",
    id: "PREP-1338",
    patientName: "You",
    severity: "GREEN",
    status: "finalized",
    title: "Follow-up Recovery Check",
  },
];

