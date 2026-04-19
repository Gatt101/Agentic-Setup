import { DoctorPatientsPanel } from "@/components/patients/DoctorPatientsPanel";
import { getDoctorPatients } from "@/lib/data/loaders";
import { DATA_MODE_QUERY_PARAM, resolveDataSourceMode } from "@/lib/data/mode";
import { auth } from "@clerk/nextjs/server";

type SearchParams = Promise<Record<string, string | string[] | undefined>>;

export default async function DoctorPatientsPage({
  searchParams,
}: {
  searchParams?: SearchParams;
}) {
  const params = searchParams ? await searchParams : {};
  const mode = resolveDataSourceMode(params[DATA_MODE_QUERY_PARAM]);
  const { userId } = await auth();
  const patients = await getDoctorPatients(userId ?? undefined, { mode });

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

      <DoctorPatientsPanel actorId={userId ?? ""} initialPatients={patients} />
    </main>
  );
}

