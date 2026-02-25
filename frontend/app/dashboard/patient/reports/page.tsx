import { getPatientReports } from "@/lib/data/loaders";
import { FileTextIcon } from "lucide-react";

export default async function PatientReportsPage() {
  const reports = await getPatientReports();

  return (
    <main className="space-y-4 p-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-100">
          My Reports
        </h1>
        <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">
          Review your report history and current severity status.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {reports.map((report) => (
          <article
            className="rounded-2xl border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-900"
            key={report.id}
          >
            <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">
              {report.title}
            </h2>
            <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">{report.id}</p>
            <p className="mt-3 text-sm text-slate-700 dark:text-slate-300">
              Generated: {new Date(report.createdAt).toLocaleString()}
            </p>
            <p className="text-sm text-slate-700 dark:text-slate-300">
              Status: <span className="font-medium capitalize">{report.status}</span>
            </p>
            <p className="text-sm text-slate-700 dark:text-slate-300">
              Severity: <span className="font-medium">{report.severity}</span>
            </p>
            <a
              href={`${process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/api$/, "") ?? "http://localhost:8000"}/reports/${report.id}.pdf`}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-3 inline-flex items-center gap-1.5 rounded-lg border border-[var(--color-primary)]/30 bg-[var(--color-primary)]/10 px-3 py-2 text-sm font-medium text-[var(--color-primary)] transition-colors hover:bg-[var(--color-primary)]/20 dark:border-[var(--color-primary)]/40 dark:bg-[var(--color-primary)]/15 dark:hover:bg-[var(--color-primary)]/25"
            >
              <FileTextIcon className="size-4" />
              View Report
            </a>
          </article>
        ))}
      </div>
    </main>
  );
}
