"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useTransition } from "react";

import {
  DATA_MODE_QUERY_PARAM,
  getDataSourceLabelForMode,
  resolveDataSourceMode,
  type DataSourceMode,
} from "@/lib/data/mode";

function nextHref(
  pathname: string,
  currentParams: URLSearchParams,
  mode: DataSourceMode
): string {
  const params = new URLSearchParams(currentParams.toString());
  params.set(DATA_MODE_QUERY_PARAM, mode);
  const serialized = params.toString();
  return serialized ? `${pathname}?${serialized}` : pathname;
}

export function DataSourceToggle() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [isPending, startTransition] = useTransition();

  const currentMode = resolveDataSourceMode(searchParams.get(DATA_MODE_QUERY_PARAM));

  const onChangeMode = (mode: DataSourceMode) => {
    if (mode === currentMode) {
      return;
    }
    const href = nextHref(pathname, searchParams, mode);
    startTransition(() => {
      router.replace(href, { scroll: false });
    });
  };

  const modeClassName = (mode: DataSourceMode): string =>
    [
      "rounded-full px-3 py-1 text-xs font-semibold tracking-wide transition-colors",
      currentMode === mode
        ? "bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900"
        : "text-slate-600 hover:bg-slate-200 dark:text-slate-300 dark:hover:bg-slate-700/70",
    ].join(" ");

  return (
    <div className="inline-flex items-center gap-2 rounded-full border border-slate-300 bg-white/90 p-1 text-slate-700 shadow-sm backdrop-blur dark:border-slate-700 dark:bg-slate-900/85 dark:text-slate-200">
      <span className="pl-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500 dark:text-slate-400">
        Data
      </span>
      <button
        aria-pressed={currentMode === "mock"}
        className={modeClassName("mock")}
        disabled={isPending}
        onClick={() => onChangeMode("mock")}
        type="button"
      >
        Mock
      </button>
      <button
        aria-pressed={currentMode === "api"}
        className={modeClassName("api")}
        disabled={isPending}
        onClick={() => onChangeMode("api")}
        type="button"
      >
        Live
      </button>
      <span className="pr-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500 dark:text-slate-400">
        {getDataSourceLabelForMode(currentMode)}
      </span>
    </div>
  );
}
