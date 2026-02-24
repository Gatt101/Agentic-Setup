import type { ReactNode } from "react";

export function Modal({ children }: { children: ReactNode }) {
  return <div className="rounded-xl border border-slate-200 bg-white p-4">{children}</div>;
}
