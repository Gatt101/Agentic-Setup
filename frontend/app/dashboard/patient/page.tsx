import { getPatientReports } from "@/lib/data/loaders";

export default async function PatientHomePage() {
  const reports = await getPatientReports();

  const latestReport = reports[0];

  return (
    <main className="space-y-4 p-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-100">
          Patient Dashboard
        </h1>
        <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">
          Understand your latest report and review follow-up guidance.
        </p>
      </div>

      {latestReport ? (
        <section className="rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-700 dark:bg-slate-900">
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500 dark:text-slate-400">
            Latest report
          </p>
          <h2 className="mt-2 text-xl font-semibold text-slate-900 dark:text-slate-100">
            {latestReport.title}
          </h2>
          <p className="mt-2 text-sm text-slate-700 dark:text-slate-300">
            Status: <span className="font-medium capitalize">{latestReport.status}</span>
          </p>
          <p className="text-sm text-slate-700 dark:text-slate-300">
            Severity: <span className="font-medium">{latestReport.severity}</span>
          </p>
        </section>
      ) : null}
    </main>
  );
}
