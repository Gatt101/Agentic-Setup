"use client";

import { useUser } from "@clerk/nextjs";
import { motion, useReducedMotion } from "framer-motion";
import { Loader2 } from "lucide-react";
import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  DASHBOARD_ROUTES,
  ROLE_COOKIE_NAME,
  type AppRole,
} from "@/lib/constants";
import { parseRole } from "@/lib/rbac";
import { BoneIcon } from "@/icons/BoneIcon";
import { HospitalIcon } from "@/icons/HospitalIcon";

type CardDefinition = {
  icon: () => JSX.Element;
  points: string[];
  role: AppRole;
  title: string;
};

const cards: CardDefinition[] = [
  {
    icon: BoneIcon,
    points: [
      "Triage-oriented case review flow",
      "Patient history and report-centered workspace",
      "Faster decision support for orthopedic follow-up",
    ],
    role: "doctor",
    title: "Doctor",
  },
  {
    icon: HospitalIcon,
    points: [
      "Plain-language report understanding",
      "Clear urgency and next-step guidance",
      "Nearby orthopedic care direction",
    ],
    role: "patient",
    title: "Patient",
  },
];

function readExistingRole(user: ReturnType<typeof useUser>["user"]): AppRole | null {
  if (!user) {
    return null;
  }

  const unsafeRole = parseRole(
    (user.unsafeMetadata as Record<string, unknown> | undefined)?.role
  );
  if (unsafeRole) {
    return unsafeRole;
  }

  const publicRole = parseRole(
    (user.publicMetadata as Record<string, unknown> | undefined)?.role
  );
  if (publicRole) {
    return publicRole;
  }

  return null;
}

export function RoleSelectionScreen() {
  const prefersReducedMotion = useReducedMotion();
  const { isLoaded, user } = useUser();
  const [selectedRole, setSelectedRole] = useState<AppRole | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const existingRole = useMemo(() => readExistingRole(user), [user]);

  const handleSelectRole = async (role: AppRole) => {
    if (!isLoaded || !user) {
      return;
    }

    setSelectedRole(role);
    setErrorMessage(null);

    try {
      const unsafeMetadata = (user.unsafeMetadata ?? {}) as Record<string, unknown>;
      await user.update({
        unsafeMetadata: {
          ...unsafeMetadata,
          role,
        },
      });

      // eslint-disable-next-line react-hooks/immutability
      document.cookie = `${ROLE_COOKIE_NAME}=${role}; Path=/; Max-Age=2592000; SameSite=Lax`;

      await user.reload();
      window.location.assign(DASHBOARD_ROUTES[role]);
    } catch {
      setErrorMessage("Unable to save role right now. Please try again.");
      setSelectedRole(null);
    }
  };

  return (
    <main className="relative flex min-h-[calc(100vh-4rem)] items-center justify-center overflow-hidden px-6 py-12">
      <div
        aria-hidden="true"
        className="absolute inset-0 bg-[radial-gradient(circle_at_10%_10%,rgba(79,93,149,0.18),transparent_32%),radial-gradient(circle_at_85%_20%,rgba(107,139,115,0.2),transparent_35%),linear-gradient(180deg,#f3f6ff_0%,#f8faf7_45%,#f8f9fb_100%)] dark:bg-[radial-gradient(circle_at_10%_10%,rgba(143,162,255,0.2),transparent_32%),radial-gradient(circle_at_85%_20%,rgba(152,182,162,0.24),transparent_35%),linear-gradient(180deg,#040815_0%,#09111f_45%,#06090f_100%)]"
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 bg-[linear-gradient(to_right,rgba(15,23,42,0.04)_1px,transparent_1px),linear-gradient(to_bottom,rgba(15,23,42,0.04)_1px,transparent_1px)] bg-[size:36px_36px] [mask-image:radial-gradient(circle_at_center,black_42%,transparent_84%)] dark:bg-[linear-gradient(to_right,rgba(148,163,184,0.08)_1px,transparent_1px),linear-gradient(to_bottom,rgba(148,163,184,0.08)_1px,transparent_1px)]"
      />

      <motion.section
        animate={{ opacity: 1, y: 0 }}
        className="relative w-full max-w-4xl rounded-3xl border border-white/60 bg-white/60 p-7 shadow-[0_25px_80px_rgba(15,23,42,0.2)] backdrop-blur-xl dark:border-slate-700/60 dark:bg-slate-900/55 dark:shadow-[0_25px_80px_rgba(2,8,23,0.5)] sm:p-10"
        initial={{ opacity: 0, y: prefersReducedMotion ? 0 : 14 }}
        transition={{ duration: 0.45, ease: "easeOut" }}
      >
        <div className="text-center">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[var(--color-secondary)]">
            Account Setup
          </p>
          <h1 className="mt-3 text-3xl font-semibold text-slate-900 dark:text-slate-100 sm:text-4xl">
            Choose your workspace role
          </h1>
          <p className="mx-auto mt-3 max-w-2xl text-sm leading-relaxed text-slate-600 dark:text-slate-300 sm:text-base">
            Select how you want OrthoAssist configured for this account. You can
            change it later.
          </p>
          {existingRole ? (
            <p className="mt-3 text-xs font-medium text-slate-500 dark:text-slate-400">
              Current role: <span className="uppercase tracking-[0.12em]">{existingRole}</span>
            </p>
          ) : null}
        </div>

        <div className="mt-8 grid gap-4 md:grid-cols-2">
          {cards.map((card, index) => {
            const isLoading = selectedRole === card.role;
            return (
              <motion.article
                className="rounded-2xl border border-slate-200/90 bg-white/75 p-6 shadow-[0_8px_24px_rgba(15,23,42,0.12)] backdrop-blur-md transition-transform duration-200 hover:-translate-y-0.5 dark:border-slate-700/90 dark:bg-slate-900/70 dark:shadow-[0_8px_24px_rgba(2,8,23,0.45)]"
                initial={{ opacity: 0, y: prefersReducedMotion ? 0 : 12 }}
                key={card.role}
                transition={{
                  duration: 0.35,
                  delay: prefersReducedMotion ? 0 : index * 0.08,
                  ease: "easeOut",
                }}
                viewport={{ once: true, amount: 0.45 }}
                whileInView={{ opacity: 1, y: 0 }}
              >
                <div className="flex items-center gap-3">
                  <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-100 text-[var(--color-primary)] dark:bg-slate-800">
                    <card.icon />
                  </span>
                  <h2 className="text-xl font-semibold text-slate-900 dark:text-slate-100">
                    {card.title}
                  </h2>
                </div>

                <ul className="mt-4 space-y-2 text-sm text-slate-700 dark:text-slate-300">
                  {card.points.map((point) => (
                    <li className="flex items-start gap-2" key={point}>
                      <span className="mt-1.5 h-2 w-2 flex-none rounded-full bg-[var(--color-secondary)]" />
                      <span>{point}</span>
                    </li>
                  ))}
                </ul>

                <Button
                  className="mt-6 h-10 w-full rounded-xl text-sm font-semibold"
                  disabled={Boolean(selectedRole)}
                  onClick={() => void handleSelectRole(card.role)}
                  type="button"
                >
                  {isLoading ? (
                    <span className="inline-flex items-center gap-2">
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Saving...
                    </span>
                  ) : (
                    `Continue as ${card.title}`
                  )}
                </Button>
              </motion.article>
            );
          })}
        </div>

        {errorMessage ? (
          <p className="mt-5 text-center text-sm text-red-600 dark:text-red-400">
            {errorMessage}
          </p>
        ) : null}
      </motion.section>
    </main>
  );
}
