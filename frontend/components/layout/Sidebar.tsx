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
import Image from "next/image";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import React, { useEffect, useState } from "react";

import { HeaderUserButton } from "@/components/layout/HeaderUserButton";
import {
    Sidebar,
    SidebarBody,
    SidebarLink,
} from "@/components/ui/sidebar";
import orthoIconS from "@/icons/ortho_icon_s.png";
import type { AppRole } from "@/lib/constants";
import { cn } from "@/lib/utils";

type SidebarProps = {
  role: AppRole;
  userId: string;
};

type ChatSessionSummary = {
  chat_id: string;
  title: string;
};

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api";

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
      <Image
        alt="OrthoAssist"
        className="h-8 w-8 shrink-0 rounded-xl object-cover ring-1 ring-slate-300/80 shadow-sm dark:ring-slate-700/80"
        height={32}
        src={orthoIconS}
        width={32}
      />
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

export function AppSidebar({ role, userId }: SidebarProps) {
  const [open, setOpen] = useState(false);
  const [chatSessions, setChatSessions] = useState<ChatSessionSummary[]>([]);
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const activeChatId = searchParams.get("chat_id");
  const links = role === "doctor" ? doctorLinks : patientLinks;
  const chatBaseHref = role === "doctor" ? "/dashboard/doctor/chat" : "/dashboard/patient/chat";

  useEffect(() => {
    const loadSessions = async () => {
      try {
        const response = await fetch(
          `${API_BASE_URL}/chat/sessions?actor_id=${encodeURIComponent(userId)}&actor_role=${encodeURIComponent(role)}`,
          { cache: "no-store" }
        );
        if (!response.ok) {
          return;
        }
        const payload = (await response.json()) as ChatSessionSummary[];
        setChatSessions(Array.isArray(payload) ? payload.slice(0, 8) : []);
      } catch {
        // Ignore sidebar session fetch errors.
      }
    };

    void loadSessions();
    const shouldPoll = pathname.includes("/chat");
    if (!shouldPoll) {
      return;
    }

    const interval = setInterval(() => {
      void loadSessions();
    }, 3000);

    return () => {
      clearInterval(interval);
    };
  }, [activeChatId, pathname, role, userId]);

  return (
    <Sidebar open={open} setOpen={setOpen}>
      <SidebarBody className="justify-between gap-8">
        <div className="flex flex-1 flex-col overflow-x-hidden">
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
                          : "text-slate-500 dark:text-slate-300",
                      ),
                    },
                  ),
                }}
                className={cn(
                  pathname === link.href || pathname.startsWith(link.href + "/")
                    ? "bg-[var(--color-primary)]/10 dark:bg-[var(--color-primary)]/20"
                    : "",
                )}
              />
            ))}

            {pathname.includes("/chat") && chatSessions.length > 0 ? (
              <div className="mt-3">
                <p className="px-2 text-[11px] font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">
                  Recent Chats
                </p>
                <div className="mt-1 max-h-48 overflow-y-auto space-y-1 pr-1 [&::-webkit-scrollbar]:hidden" style={{ scrollbarWidth: 'none', msOverflowStyle: 'none' }}>
                  {chatSessions.map((session) => {
                    const href = `${chatBaseHref}?chat_id=${encodeURIComponent(session.chat_id)}`;
                    const isActive = activeChatId === session.chat_id;
                    return (
                      <SidebarLink
                        key={session.chat_id}
                        link={{
                          href,
                          icon: <MessageSquare className="h-4 w-4 shrink-0" />,
                          label: session.title || "Untitled chat",
                        }}
                        className={cn(isActive ? "bg-[var(--color-primary)]/10 dark:bg-[var(--color-primary)]/20" : "")}
                      />
                    );
                  })}
                </div>
              </div>
            ) : null}
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
