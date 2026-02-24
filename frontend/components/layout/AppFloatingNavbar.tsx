"use client";

import { SignedIn, SignedOut } from "@clerk/nextjs";
import { House, MessageSquare, UserRound } from "lucide-react";
import { usePathname } from "next/navigation";

import { FloatingNav } from "@/components/ui/floating-navbar";

export function AppFloatingNavbar() {
  const pathname = usePathname();

  if (
    pathname.startsWith("/dashboard") ||
    pathname.startsWith("/select-role")
  ) {
    return null;
  }

  const navItems =
    pathname === "/"
      ? [
          {
            icon: (
              <House className="h-4 w-4 text-neutral-500 dark:text-white" />
            ),
            link: "/",
            name: "Home",
          },
          {
            icon: (
              <UserRound className="h-4 w-4 text-neutral-500 dark:text-white" />
            ),
            link: "#workflow",
            name: "Workflow",
          },
          {
            icon: (
              <MessageSquare className="h-4 w-4 text-neutral-500 dark:text-white" />
            ),
            link: "#start",
            name: "Start",
          },
        ]
      : [
          {
            icon: (
              <House className="h-4 w-4 text-neutral-500 dark:text-white" />
            ),
            link: "/",
            name: "Home",
          },
          {
            icon: (
              <UserRound className="h-4 w-4 text-neutral-500 dark:text-white" />
            ),
            link: "/sign-in",
            name: "Log in",
          },
          {
            icon: (
              <MessageSquare className="h-4 w-4 text-neutral-500 dark:text-white" />
            ),
            link: "/sign-up",
            name: "Sign up",
          },
        ];

  return (
    <>
      <SignedOut>
        <FloatingNav ctaHref="/sign-in" ctaLabel="Login" navItems={navItems} />
      </SignedOut>
      <SignedIn>
        <FloatingNav
          ctaHref="/dashboard"
          ctaLabel="Dashboard"
          navItems={navItems}
        />
      </SignedIn>
    </>
  );
}
