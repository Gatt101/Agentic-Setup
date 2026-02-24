import { DATA_SOURCE_MODE } from "@/lib/data/mode";

export default function DoctorSettingsPage() {
  return (
    <main className="space-y-4 p-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-100">
          Doctor Settings
        </h1>
        <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">
          Runtime configuration used for current frontend preview.
        </p>
      </div>

      <section className="rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-700 dark:bg-slate-900">
        <p className="text-sm text-slate-700 dark:text-slate-300">
          Data source mode is currently set to{" "}
          <span className="font-semibold uppercase">{DATA_SOURCE_MODE}</span>.
        </p>
        <p className="mt-2 text-sm text-slate-600 dark:text-slate-400">
          Change <code>NEXT_PUBLIC_DATA_SOURCE</code> to <code>api</code> or{" "}
          <code>mock</code> in your env, then restart the frontend server.
        </p>
      </section>
    </main>
  );
}
