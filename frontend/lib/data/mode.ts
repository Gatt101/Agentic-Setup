export type DataSourceMode = "api" | "mock";

const rawMode = (process.env.NEXT_PUBLIC_DATA_SOURCE ?? "mock")
  .toLowerCase()
  .trim();

export const DATA_SOURCE_MODE: DataSourceMode =
  rawMode === "api" ? "api" : "mock";

export const USE_MOCK_DATA = DATA_SOURCE_MODE === "mock";

export const DATA_MODE_QUERY_PARAM = "data";

export function parseDataSourceMode(
  value: string | string[] | null | undefined
): DataSourceMode | null {
  if (Array.isArray(value)) {
    return parseDataSourceMode(value[0] ?? null);
  }

  const normalized = (value ?? "").toLowerCase().trim();
  if (normalized === "mock") {
    return "mock";
  }
  if (normalized === "api" || normalized === "live" || normalized === "real") {
    return "api";
  }
  return null;
}

export function resolveDataSourceMode(
  override?: string | string[] | null
): DataSourceMode {
  return parseDataSourceMode(override) ?? DATA_SOURCE_MODE;
}

export function getDataSourceLabelForMode(mode: DataSourceMode): string {
  return mode === "api" ? "LIVE" : "MOCK";
}

