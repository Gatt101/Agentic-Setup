import { auth } from "@clerk/nextjs/server";
import { getDoctorPatients } from "@/lib/data/loaders";

const riskClassName: Record<"AMBER" | "GREEN" | "RED", string> = {
  AMBER:
    "border-amber-300 bg-amber-50 text-amber-800 dark:border-amber-600 dark:bg-amber-900/30 dark:text-amber-200",
  GREEN:
    "border-emerald-300 bg-emerald-50 text-emerald-800 dark:border-emerald-600 dark:bg-emerald-900/30 dark:text-emerald-200",
  RED: "border-rose-300 bg-rose-50 text-rose-800 dark:border-rose-600 dark:bg-rose-900/30 dark:text-rose-200",
};

export default async function DoctorPatientsPage() {
  const { userId, redirectToSignIn } = await auth();
  if (!userId) {
    return redirectToSignIn();
  }

  const patients = await getDoctorPatients(userId);

  return (
    <main className="space-y-4 p-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-100">
          Patients
        </h1>
        <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">
          Monitor active orthopedic cases and prioritize high-risk studies.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {patients.length === 0 ? (
          <p className="col-span-full text-center text-sm text-slate-500 dark:text-slate-400 py-12">
            No patients found. Patients will appear here once they interact through chat sessions.
          </p>
        ) : (
          patients.map((patient) => (
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
            <p className="mt-3 text-sm text-slate-700 dark:text-slate-300">
              {patient.summary}
            </p>
            <p className="mt-3 text-xs font-medium text-slate-500 dark:text-slate-400">
              Last Study: {patient.lastStudy}
            </p>
          </article>
          ))
        )}
      </div>
    </main>
  );
}
