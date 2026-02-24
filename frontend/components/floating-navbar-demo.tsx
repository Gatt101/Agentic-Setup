"use client";

import React from "react";
import { House, MessageSquare, UserRound } from "lucide-react";

import { FloatingNav } from "@/components/ui/floating-navbar";

export default function FloatingNavDemo() {
  const navItems = [
    {
      icon: <House className="h-4 w-4 text-neutral-500 dark:text-white" />,
      link: "/",
      name: "Home",
    },
    {
      icon: <UserRound className="h-4 w-4 text-neutral-500 dark:text-white" />,
      link: "#about",
      name: "About",
    },
    {
      icon: (
        <MessageSquare className="h-4 w-4 text-neutral-500 dark:text-white" />
      ),
      link: "#contact",
      name: "Contact",
    },
  ];

  return (
    <div className="relative w-full translate-z-0">
      <FloatingNav navItems={navItems} />
      <DummyContent />
    </div>
  );
}

const DummyContent = () => {
  return (
    <div className="relative grid h-[40rem] w-full grid-cols-1 rounded-md border border-neutral-200 bg-white dark:border-white/[0.2] dark:bg-black">
      <p className="mt-40 text-center text-4xl font-bold text-neutral-600 dark:text-white">
        Scroll back up to reveal Navbar
      </p>
      <div className="bg-grid-black/[0.1] dark:bg-grid-white/[0.2] absolute inset-0" />
    </div>
  );
};
