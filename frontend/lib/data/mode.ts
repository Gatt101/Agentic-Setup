export type DataSourceMode = "api" | "mock";

const rawMode = (process.env.NEXT_PUBLIC_DATA_SOURCE ?? "mock")
  .toLowerCase()
  .trim();

export const DATA_SOURCE_MODE: DataSourceMode =
  rawMode === "api" ? "api" : "mock";

export const USE_MOCK_DATA = DATA_SOURCE_MODE === "mock";

