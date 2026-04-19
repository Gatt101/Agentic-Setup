import { DoctorDashboardOverview } from "@/components/dashboard/DoctorDashboardOverview";
import {
  getDataSourceLabel,
  getDoctorDashboardData,
} from "@/lib/data/loaders";
import { DATA_MODE_QUERY_PARAM, resolveDataSourceMode } from "@/lib/data/mode";
import { auth } from "@clerk/nextjs/server";

type SearchParams = Promise<Record<string, string | string[] | undefined>>;

export default async function DoctorHomePage({
  searchParams,
}: {
  searchParams?: SearchParams;
}) {
  const params = searchParams ? await searchParams : {};
  const mode = resolveDataSourceMode(params[DATA_MODE_QUERY_PARAM]);
  const { userId } = await auth();

  const data = await getDoctorDashboardData(userId ?? undefined, { mode });
  const dataSourceLabel = getDataSourceLabel({ mode });

  return <DoctorDashboardOverview data={data} dataSourceLabel={dataSourceLabel} />;
}
