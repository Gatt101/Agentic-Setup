import type { AppRole } from "@/lib/constants";
import { HeaderUserButton } from "@/components/layout/HeaderUserButton";

type HeaderProps = {
  role: AppRole;
};

export function Header({ role }: HeaderProps) {
  return (
    <header className="flex items-center justify-between border-slate-200 border-b bg-white/95 px-4 py-3 backdrop-blur dark:border-slate-800 dark:bg-slate-950/85">
      <div>
        <h2 className="text-sm font-semibold uppercase tracking-[0.14em] text-slate-700 dark:text-slate-200">
          {role} dashboard
        </h2>
      </div>
      <HeaderUserButton />
    </header>
  );
}
