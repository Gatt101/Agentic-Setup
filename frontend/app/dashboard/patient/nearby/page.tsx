import { getNearbyCareCenters } from "@/lib/data/loaders";

export default async function PatientNearbyPage() {
  const centers = await getNearbyCareCenters();

  return (
    <main className="space-y-4 p-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-100">
          Nearby Orthopedic Care
        </h1>
        <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">
          Suggested centers based on urgency and availability.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {centers.map((center) => (
          <article
            className="rounded-2xl border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-900"
            key={center.id}
          >
            <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">
              {center.name}
            </h2>
            <p className="mt-1 text-sm text-slate-700 dark:text-slate-300">
              Specialty: {center.specialty}
            </p>
            <p className="text-sm text-slate-700 dark:text-slate-300">
              Distance: {center.distanceKm} km
            </p>
            <p className="text-sm text-slate-700 dark:text-slate-300">
              Estimated wait: {center.waitEstimate}
            </p>
          </article>
        ))}
      </div>
    </main>
  );
}
