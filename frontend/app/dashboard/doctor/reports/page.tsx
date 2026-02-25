import { getDoctorReports } from "@/lib/data/loaders";
import { FileTextIcon } from "lucide-react";

const severityClassName: Record<"AMBER" | "GREEN" | "RED", string> = {
  AMBER:
    "border-amber-300 bg-amber-50 text-amber-800 dark:border-amber-600 dark:bg-amber-900/30 dark:text-amber-200",
  GREEN:
    "border-emerald-300 bg-emerald-50 text-emerald-800 dark:border-emerald-600 dark:bg-emerald-900/30 dark:text-emerald-200",
  RED: "border-rose-300 bg-rose-50 text-rose-800 dark:border-rose-600 dark:bg-rose-900/30 dark:text-rose-200",
};

export default async function DoctorReportsPage() {
  const reports = await getDoctorReports();

  return (
    <main className="space-y-4 p-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-100">
          Doctor Reports
        </h1>
        <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">
          Review report status and severity before final submission.
        </p>
      </div>

      <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white dark:border-slate-700 dark:bg-slate-900">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300">
            <tr>
              <th className="px-4 py-3 font-semibold">Report</th>
              <th className="px-4 py-3 font-semibold">Patient</th>
              <th className="px-4 py-3 font-semibold">Status</th>
              <th className="px-4 py-3 font-semibold">Severity</th>
              <th className="px-4 py-3 font-semibold">Created</th>
              <th className="px-4 py-3 font-semibold">Actions</th>
            </tr>
          </thead>
          <tbody>
            {reports.map((report) => (
              <tr
                className="border-slate-200 border-t dark:border-slate-700"
                key={report.id}
              >
                <td className="px-4 py-3">
                  <p className="font-medium text-slate-900 dark:text-slate-100">
                    {report.title}
                  </p>
                  <p className="text-xs text-slate-500 dark:text-slate-400">{report.id}</p>
                </td>
                <td className="px-4 py-3 text-slate-700 dark:text-slate-300">
                  {report.patientName}
                </td>
                <td className="px-4 py-3">
                  <span className="rounded-full border border-slate-300 px-2 py-1 text-xs font-medium capitalize text-slate-700 dark:border-slate-600 dark:text-slate-300">
                    {report.status}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <span
                    className={`rounded-full border px-2 py-1 text-xs font-semibold uppercase ${severityClassName[report.severity]}`}
                  >
                    {report.severity}
                  </span>
                </td>
                <td className="px-4 py-3 text-slate-600 dark:text-slate-300">
                  {new Date(report.createdAt).toLocaleString()}
                </td>
                <td className="px-4 py-3">
                  <a
                    href={`${process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/api$/, "") ?? "http://localhost:8000"}/reports/${report.id}.pdf`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--color-primary)]/30 bg-[var(--color-primary)]/10 px-3 py-1.5 text-xs font-medium text-[var(--color-primary)] transition-colors hover:bg-[var(--color-primary)]/20 dark:border-[var(--color-primary)]/40 dark:bg-[var(--color-primary)]/15 dark:hover:bg-[var(--color-primary)]/25"
                  >
                    <FileTextIcon className="size-3.5" />
                    View PDF
                  </a>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </main>
  );
}
