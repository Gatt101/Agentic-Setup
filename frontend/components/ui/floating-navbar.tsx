"use client";

import React, { useState } from "react";
import {
  AnimatePresence,
  motion,
  useMotionValueEvent,
  useScroll,
} from "framer-motion";

import { cn } from "@/lib/utils";

export const FloatingNav = ({
  navItems,
  className,
  ctaHref = "/sign-in",
  ctaLabel = "Login",
}: {
  navItems: {
    icon?: JSX.Element;
    link: string;
    name: string;
  }[];
  className?: string;
  ctaHref?: string;
  ctaLabel?: string;
}) => {
  const { scrollYProgress } = useScroll();
  const [visible, setVisible] = useState(false);

  useMotionValueEvent(scrollYProgress, "change", (current) => {
    if (typeof current === "number") {
      const previous = scrollYProgress.getPrevious() ?? 0;
      const direction = current - previous;

      if (scrollYProgress.get() < 0.05) {
        setVisible(false);
      } else if (direction < 0) {
        setVisible(true);
      } else {
        setVisible(false);
      }
    }
  });

  return (
    <AnimatePresence mode="wait">
      <motion.div
        animate={{
          opacity: visible ? 1 : 0,
          y: visible ? 0 : -100,
        }}
        className={cn(
          "fixed inset-x-0 top-10 z-[5000] mx-auto flex max-w-fit items-center justify-center",
          className
        )}
        initial={{
          opacity: 1,
          y: -100,
        }}
        transition={{
          duration: 0.2,
        }}
      >
        <div className="flex items-center justify-center gap-2 rounded-full border border-white/10 bg-white/80 px-2 py-1.5 shadow-lg shadow-black/10 backdrop-blur-md dark:border-white/10 dark:bg-black/50">
          <div className="flex items-center gap-1">
            {navItems.map((navItem, idx: number) => (
              <a
                className={cn(
                  "relative flex items-center gap-1 rounded-full px-4 py-2 text-sm font-medium text-neutral-600 transition-colors hover:bg-neutral-100 hover:text-neutral-900 dark:text-neutral-300 dark:hover:bg-white/10 dark:hover:text-white"
                )}
                href={navItem.link}
                key={`link-${idx}`}
              >
                <span className="block sm:hidden">{navItem.icon}</span>
                <span className="hidden sm:block">{navItem.name}</span>
              </a>
            ))}
          </div>

          <div className="h-5 w-px bg-neutral-200 dark:bg-white/10" />

          <a
            className="relative rounded-full bg-neutral-900 px-4 py-2 text-sm font-medium text-white transition-all hover:bg-neutral-800 hover:shadow-lg hover:shadow-neutral-900/20 dark:bg-white dark:text-black dark:hover:bg-neutral-100 dark:hover:shadow-white/20"
            href={ctaHref}
          >
            <span>{ctaLabel}</span>
          </a>
        </div>
      </motion.div>
    </AnimatePresence>
  );
};

