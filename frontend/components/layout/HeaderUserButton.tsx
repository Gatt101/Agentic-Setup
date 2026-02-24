"use client";

import dynamic from "next/dynamic";

const UserButton = dynamic(
  () => import("@clerk/nextjs").then((mod) => mod.UserButton),
  {
    loading: () => (
      <div
        aria-hidden
        className="h-8 w-8 animate-pulse rounded-full bg-slate-200 dark:bg-slate-700"
      />
    ),
    ssr: false,
  }
);

export function HeaderUserButton() {
  return <UserButton afterSignOutUrl="/" />;
}
