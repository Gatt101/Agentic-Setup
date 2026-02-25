"use client";

import { Button } from "@/components/ui/button";
import type { PatientRecord } from "@/lib/data/types";
import { useMemo, useState } from "react";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api";

const riskClassName: Record<"AMBER" | "GREEN" | "RED", string> = {
  AMBER:
    "border-amber-300 bg-amber-50 text-amber-800 dark:border-amber-600 dark:bg-amber-900/30 dark:text-amber-200",
  GREEN:
    "border-emerald-300 bg-emerald-50 text-emerald-800 dark:border-emerald-600 dark:bg-emerald-900/30 dark:text-emerald-200",
  RED: "border-rose-300 bg-rose-50 text-rose-800 dark:border-rose-600 dark:bg-rose-900/30 dark:text-rose-200",
};

type DoctorPatientsPanelProps = {
  actorId: string;
  initialPatients: PatientRecord[];
};

export function DoctorPatientsPanel({ actorId, initialPatients }: DoctorPatientsPanelProps) {
  const [patients, setPatients] = useState<PatientRecord[]>(initialPatients);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const hasPatients = useMemo(() => patients.length > 0, [patients.length]);

  const onDeletePatient = async (patient: PatientRecord) => {
    const confirmed = window.confirm(
      `Delete patient "${patient.name}" (${patient.id})?\n\nThis will remove the patient record and linked reports.`
    );
    if (!confirmed || deletingId) {
      return;
    }

    setDeletingId(patient.id);
    setError(null);
    try {
      const params = new URLSearchParams({ actor_id: actorId, actor_role: "doctor" });
      const response = await fetch(
        `${API_BASE_URL}/patients/${encodeURIComponent(patient.id)}?${params.toString()}`,
        {
          method: "DELETE",
          cache: "no-store",
        }
      );
      if (!response.ok) {
        let message = "Failed to delete patient.";
        try {
          const payload = (await response.json()) as { detail?: string };
          if (payload.detail && payload.detail.trim()) {
            message = payload.detail.trim();
          }
        } catch {
          // keep default message
        }
        throw new Error(message);
      }

      setPatients((previous) => previous.filter((item) => item.id !== patient.id));
    } catch (err) {
      setError(err instanceof Error && err.message ? err.message : "Failed to delete patient.");
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <div className="space-y-4">
      {error ? (
        <p className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-900/60 dark:bg-red-950/30 dark:text-red-300">
          {error}
        </p>
      ) : null}

      {!hasPatients ? (
        <div className="rounded-xl border border-slate-200 bg-white p-5 text-sm text-slate-600 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300">
          No patients available.
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {patients.map((patient) => (
            <article
              className="rounded-2xl border border-slate-200 bg-white p-4 shadow-[0_8px_20px_rgba(15,23,42,0.06)] dark:border-slate-700 dark:bg-slate-900 dark:shadow-[0_8px_20px_rgba(2,8,23,0.4)]"
              key={patient.id}
            >
              <div className="flex items-start justify-between gap-2">
                <div>
                  <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">
                    {patient.name}
                  </h2>
                  <p className="text-xs text-slate-500 dark:text-slate-400">
                    {patient.id} • Age {patient.age}
                  </p>
                </div>
                <span
                  className={`rounded-full border px-2 py-1 text-xs font-semibold uppercase ${riskClassName[patient.riskLevel]}`}
                >
                  {patient.riskLevel}
                </span>
              </div>

              <p className="mt-3 text-sm text-slate-700 dark:text-slate-300">{patient.summary}</p>
              <p className="mt-3 text-xs font-medium text-slate-500 dark:text-slate-400">
                Last Study: {patient.lastStudy}
              </p>

              <div className="mt-4 flex justify-end">
                <Button
                  variant="destructive"
                  size="sm"
                  disabled={deletingId === patient.id}
                  onClick={() => void onDeletePatient(patient)}
                >
                  {deletingId === patient.id ? "Deleting..." : "Delete Patient"}
                </Button>
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}

