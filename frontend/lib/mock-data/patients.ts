import type { PatientRecord } from "@/lib/data/types";

export const doctorPatientsMockData: PatientRecord[] = [
  {
    age: 42,
    id: "PT-1001",
    lastStudy: "2026-02-21",
    name: "Anita Rao",
    riskLevel: "AMBER",
    summary: "Possible distal radius fracture with moderate displacement.",
  },
  {
    age: 31,
    id: "PT-1002",
    lastStudy: "2026-02-20",
    name: "Nikhil Sharma",
    riskLevel: "GREEN",
    summary: "No acute fracture signs. Follow-up for pain progression.",
  },
  {
    age: 59,
    id: "PT-1003",
    lastStudy: "2026-02-18",
    name: "Priya Menon",
    riskLevel: "RED",
    summary: "Suspected tibial plateau fracture, urgent orthopedic review.",
  },
  {
    age: 47,
    id: "PT-1004",
    lastStudy: "2026-02-17",
    name: "Rahul Verma",
    riskLevel: "AMBER",
    summary: "Comminuted metacarpal fracture pattern, intervention planning.",
  },
];

