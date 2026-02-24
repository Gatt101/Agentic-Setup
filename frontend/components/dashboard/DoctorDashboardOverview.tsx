"use client";

import type { DoctorDashboardData } from "@/lib/data/types";

type DoctorDashboardOverviewProps = {
  data: DoctorDashboardData;
  dataSourceLabel: string;
};

type Point = { x: number; y: number };

function scaleY(value: number, maxValue: number, chartHeight: number): number {
  if (maxValue <= 0) {
    return chartHeight;
  }
  return chartHeight - (value / maxValue) * chartHeight;
}

function buildPolyline(points: Point[]): string {
  return points.map((point) => `${point.x},${point.y}`).join(" ");
}

function MonthlyTrendChart({ data }: { data: DoctorDashboardData["monthlyCases"] }) {
  const width = 560;
  const height = 220;
  const paddingX = 18;
  const chartWidth = width - paddingX * 2;
  const maxValue = Math.max(
    ...data.map((item) => Math.max(item.total, item.critical)),
    1
  );

  const totalPoints = data.map((item, index) => {
    const x = paddingX + (index / Math.max(data.length - 1, 1)) * chartWidth;
    const y = scaleY(item.total, maxValue, height);
    return { x, y };
  });

  const criticalPoints = data.map((item, index) => {
    const x = paddingX + (index / Math.max(data.length - 1, 1)) * chartWidth;
    const y = scaleY(item.critical, maxValue, height);
    return { x, y };
  });

  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50 p-3 dark:border-slate-700 dark:bg-slate-800">
      <svg
        aria-label="Monthly total and critical trend"
        className="h-56 w-full"
        viewBox={`0 0 ${width} ${height + 34}`}
      >
        <line stroke="#cbd5e1" strokeDasharray="5 6" x1={paddingX} x2={width - paddingX} y1={height} y2={height} />
        <polyline
          fill="none"
          points={buildPolyline(totalPoints)}
          stroke="#4f5d95"
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth="3.5"
        />
        <polyline
          fill="none"
          points={buildPolyline(criticalPoints)}
          stroke="#d99525"
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth="3"
        />

        {totalPoints.map((point, index) => (
          <g key={`point-${data[index]?.month}`}>
            <circle cx={point.x} cy={point.y} fill="#4f5d95" r="4.5" />
            <circle cx={criticalPoints[index]?.x} cy={criticalPoints[index]?.y} fill="#d99525" r="4" />
            <text
              fill="#64748b"
              fontSize="11"
              textAnchor="middle"
              x={point.x}
              y={height + 20}
            >
              {data[index]?.month}
            </text>
          </g>
        ))}
      </svg>
      <div className="mt-2 flex items-center gap-4 text-xs text-slate-600 dark:text-slate-300">
        <span className="inline-flex items-center gap-1">
          <span className="h-2.5 w-2.5 rounded-full bg-[#4f5d95]" />
          Total Cases
        </span>
        <span className="inline-flex items-center gap-1">
          <span className="h-2.5 w-2.5 rounded-full bg-[#d99525]" />
          Critical
        </span>
      </div>
    </div>
  );
}

function TriageDonut({
  data,
}: {
  data: DoctorDashboardData["triageDistribution"];
}) {
  const total = data.reduce((sum, item) => sum + item.count, 0);
  const segments = data.map((item) => `${item.color} ${(item.count / total) * 100}%`);
  const gradient = `conic-gradient(${segments.join(", ")})`;

  return (
    <div className="grid gap-4 lg:grid-cols-[220px_1fr]">
      <div className="flex items-center justify-center">
        <div
          className="relative h-44 w-44 rounded-full"
          style={{ background: gradient }}
        >
          <div className="absolute inset-[18%] flex items-center justify-center rounded-full bg-white text-sm font-semibold text-slate-700 dark:bg-slate-900 dark:text-slate-200">
            {total} cases
          </div>
        </div>
      </div>

      <ul className="space-y-2 text-sm">
        {data.map((item) => (
          <li
            className="flex items-center justify-between rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 dark:border-slate-700 dark:bg-slate-800"
            key={item.level}
          >
            <span className="inline-flex items-center gap-2 font-medium text-slate-700 dark:text-slate-200">
              <span
                className="h-2.5 w-2.5 rounded-full"
                style={{ backgroundColor: item.color }}
              />
              {item.level}
            </span>
            <span className="text-slate-500 dark:text-slate-400">{item.count}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function TurnaroundBars({
  data,
}: {
  data: DoctorDashboardData["reportTurnaround"];
}) {
  const maxValue = Math.max(...data.map((item) => item.avgHours), 1);

  return (
    <div className="grid grid-cols-4 items-end gap-3 rounded-xl border border-slate-200 bg-slate-50 p-4 dark:border-slate-700 dark:bg-slate-800">
      {data.map((item) => {
        const height = `${Math.max((item.avgHours / maxValue) * 100, 8)}%`;
        return (
          <div className="flex flex-col items-center gap-2" key={item.week}>
            <div className="relative flex h-40 w-full items-end">
              <div
                className="w-full rounded-t-md bg-[var(--color-secondary)]"
                style={{ height }}
                title={`${item.avgHours}h`}
              />
            </div>
            <p className="text-xs font-medium text-slate-600 dark:text-slate-300">
              {item.week}
            </p>
            <p className="text-xs text-slate-500 dark:text-slate-400">{item.avgHours}h</p>
          </div>
        );
      })}
    </div>
  );
}

export function DoctorDashboardOverview({
  data,
  dataSourceLabel,
}: DoctorDashboardOverviewProps) {
  return (
    <main className="space-y-6 p-6">
      <section className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-100">
            Doctor Operations Dashboard
          </h1>
          <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">
            Visual overview of case load, triage mix, and reporting throughput.
          </p>
        </div>
        <span className="rounded-full border border-slate-300 bg-white px-3 py-1 text-xs font-semibold uppercase tracking-[0.14em] text-slate-600 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300">
          Data Mode: {dataSourceLabel}
        </span>
      </section>

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {data.summary.map((item) => (
          <article
            className="rounded-2xl border border-slate-200 bg-white p-4 shadow-[0_8px_22px_rgba(15,23,42,0.08)] dark:border-slate-700 dark:bg-slate-900 dark:shadow-[0_8px_22px_rgba(2,8,23,0.45)]"
            key={item.label}
          >
            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500 dark:text-slate-400">
              {item.label}
            </p>
            <p className="mt-3 text-3xl font-semibold text-slate-900 dark:text-slate-100">
              {item.value}
            </p>
            <p className="mt-1 text-sm text-[var(--color-secondary)]">{item.change}</p>
          </article>
        ))}
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        <article className="rounded-2xl border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-900">
          <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">
            Monthly Cases vs Critical Findings
          </h2>
          <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">
            Compare total studies with severe findings trend.
          </p>
          <div className="mt-4">
            <MonthlyTrendChart data={data.monthlyCases} />
          </div>
        </article>

        <article className="rounded-2xl border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-900">
          <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">
            Triage Distribution
          </h2>
          <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">
            Case mix split by urgency.
          </p>
          <div className="mt-4">
            <TriageDonut data={data.triageDistribution} />
          </div>
        </article>
      </section>

      <section className="grid gap-4 xl:grid-cols-[1.3fr_1fr]">
        <article className="rounded-2xl border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-900">
          <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">
            Report Turnaround (Hours)
          </h2>
          <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">
            Weekly average report completion time.
          </p>
          <div className="mt-4">
            <TurnaroundBars data={data.reportTurnaround} />
          </div>
        </article>

        <article className="rounded-2xl border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-900">
          <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">
            Operational Alerts
          </h2>
          <ul className="mt-4 space-y-3 text-sm text-slate-700 dark:text-slate-300">
            {data.alerts.map((alert) => (
              <li
                className="rounded-xl border border-slate-200 bg-slate-50 p-3 dark:border-slate-700 dark:bg-slate-800"
                key={alert}
              >
                {alert}
              </li>
            ))}
          </ul>
        </article>
      </section>
    </main>
  );
}

