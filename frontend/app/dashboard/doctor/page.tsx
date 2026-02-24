import { DoctorDashboardOverview } from "@/components/dashboard/DoctorDashboardOverview";
import {
  getDataSourceLabel,
  getDoctorDashboardData,
} from "@/lib/data/loaders";

export default async function DoctorHomePage() {
  const data = await getDoctorDashboardData();
  const dataSourceLabel = getDataSourceLabel();

  return <DoctorDashboardOverview data={data} dataSourceLabel={dataSourceLabel} />;
}
