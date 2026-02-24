import type { AppRole } from "@/lib/constants";
import { HeaderUserButton } from "@/components/layout/HeaderUserButton";

type HeaderProps = {
  role: AppRole;
};

export function Header({ role }: HeaderProps) {
  return (
    <header className="flex items-center justify-between border-b border-slate-200 bg-white px-4 py-3">
      <div>
        <h2 className="font-semibold text-sm uppercase tracking-wide text-slate-700">
          {role} dashboard
        </h2>
      </div>
      <HeaderUserButton />
    </header>
  );
}
