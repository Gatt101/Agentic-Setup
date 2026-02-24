"use client";

import { motion } from "framer-motion";
import {
    FileText,
    LayoutDashboard,
    LogOut,
    MapPin,
    MessageSquare,
    Settings,
    Users,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import React, { useState } from "react";

import { HeaderUserButton } from "@/components/layout/HeaderUserButton";
import {
    Sidebar,
    SidebarBody,
    SidebarLink,
} from "@/components/ui/sidebar";
import type { AppRole } from "@/lib/constants";
import { cn } from "@/lib/utils";

type SidebarProps = {
  role: AppRole;
};

const doctorLinks = [
  {
    label: "Dashboard",
    href: "/dashboard/doctor",
    icon: <LayoutDashboard className="h-5 w-5 shrink-0" />,
  },
  {
    label: "Patients",
    href: "/dashboard/doctor/patients",
    icon: <Users className="h-5 w-5 shrink-0" />,
  },
  {
    label: "Reports",
    href: "/dashboard/doctor/reports",
    icon: <FileText className="h-5 w-5 shrink-0" />,
  },
  {
    label: "Chat",
    href: "/dashboard/doctor/chat",
    icon: <MessageSquare className="h-5 w-5 shrink-0" />,
  },
  {
    label: "Settings",
    href: "/dashboard/doctor/settings",
    icon: <Settings className="h-5 w-5 shrink-0" />,
  },
];

const patientLinks = [
  {
    label: "Dashboard",
    href: "/dashboard/patient",
    icon: <LayoutDashboard className="h-5 w-5 shrink-0" />,
  },
  {
    label: "Reports",
    href: "/dashboard/patient/reports",
    icon: <FileText className="h-5 w-5 shrink-0" />,
  },
  {
    label: "Chat",
    href: "/dashboard/patient/chat",
    icon: <MessageSquare className="h-5 w-5 shrink-0" />,
  },
  {
    label: "Nearby Care",
    href: "/dashboard/patient/nearby",
    icon: <MapPin className="h-5 w-5 shrink-0" />,
  },
];

function OrthoLogo({ open }: { open: boolean }) {
  return (
    <Link
      href="/"
      className="relative z-20 flex items-center gap-2 py-1 text-sm font-semibold text-slate-900 dark:text-slate-100 select-none"
    >
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-[var(--color-primary)] text-white text-xs font-bold shadow-sm">
        OA
      </div>
      <motion.span
        animate={{
          display: open ? "inline-block" : "none",
          opacity: open ? 1 : 0,
        }}
        className="whitespace-pre font-semibold text-slate-900 dark:text-slate-100"
      >
        OrthoAssist
      </motion.span>
    </Link>
  );
}

export function AppSidebar({ role }: SidebarProps) {
  const [open, setOpen] = useState(false);
  const pathname = usePathname();
  const links = role === "doctor" ? doctorLinks : patientLinks;

  return (
    <Sidebar open={open} setOpen={setOpen}>
      <SidebarBody className="justify-between gap-8">
        <div className="flex flex-1 flex-col overflow-x-hidden overflow-y-auto">
          <OrthoLogo open={open} />
          <nav className="mt-8 flex flex-col gap-1">
            {links.map((link) => (
              <SidebarLink
                key={link.href}
                link={{
                  ...link,
                  icon: React.cloneElement(
                    link.icon as React.ReactElement<{ className?: string }>,
                    {
                      className: cn(
                        "h-5 w-5 shrink-0 transition-colors",
                        pathname === link.href || pathname.startsWith(link.href + "/")
                          ? "text-[var(--color-primary)]"
                          : "text-slate-500 dark:text-slate-400",
                      ),
                    },
                  ),
                }}
                className={cn(
                  pathname === link.href || pathname.startsWith(link.href + "/")
                    ? "bg-[var(--color-primary)]/10 dark:bg-[var(--color-primary)]/15"
                    : "",
                )}
              />
            ))}
          </nav>
        </div>
        <div className="flex flex-col gap-2">
          <SidebarLink
            link={{
              label: "Back to Home",
              href: "/",
              icon: (
                <LogOut className="h-5 w-5 shrink-0 text-slate-500 dark:text-slate-400" />
              ),
            }}
          />
          <div className="flex items-center gap-2 py-2 px-2">
            <div className="shrink-0">
              <HeaderUserButton />
            </div>
            <motion.span
              animate={{
                display: open ? "inline-block" : "none",
                opacity: open ? 1 : 0,
              }}
              className="text-sm font-medium text-slate-700 dark:text-slate-200 whitespace-pre capitalize"
            >
              {role}
            </motion.span>
          </div>
        </div>
      </SidebarBody>
    </Sidebar>
  );
}
