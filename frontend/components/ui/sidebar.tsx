"use client";
import { cn } from "@/lib/utils";
import { AnimatePresence, motion } from "framer-motion";
import { Menu, X } from "lucide-react";
import React, { createContext, useContext, useState } from "react";

interface Links {
  label: string;
  href: string;
  icon: React.JSX.Element | React.ReactNode;
}

interface SidebarContextProps {
  open: boolean;
  setOpen: React.Dispatch<React.SetStateAction<boolean>>;
  animate: boolean;
}

const SidebarContext = createContext<SidebarContextProps | undefined>(undefined);

export const useSidebar = () => {
  const context = useContext(SidebarContext);
  if (!context) {
    throw new Error("useSidebar must be used within a SidebarProvider");
  }
  return context;
};

export const SidebarProvider = ({
  children,
  open: openProp,
  setOpen: setOpenProp,
  animate = true,
}: {
  children: React.ReactNode;
  open?: boolean;
  setOpen?: React.Dispatch<React.SetStateAction<boolean>>;
  animate?: boolean;
}) => {
  const [openState, setOpenState] = useState(false);

  const open = openProp !== undefined ? openProp : openState;
  const setOpen = setOpenProp !== undefined ? setOpenProp : setOpenState;

  return (
    <SidebarContext.Provider value={{ open, setOpen, animate: animate }}>
      {children}
    </SidebarContext.Provider>
  );
};

export const Sidebar = ({
  children,
  open,
  setOpen,
  animate,
}: {
  children: React.ReactNode;
  open?: boolean;
  setOpen?: React.Dispatch<React.SetStateAction<boolean>>;
  animate?: boolean;
}) => {
  return (
    <SidebarProvider open={open} setOpen={setOpen} animate={animate}>
      {children}
    </SidebarProvider>
  );
};

export const SidebarBody = (props: React.ComponentProps<typeof motion.div>) => {
  return (
    <>
      <DesktopSidebar {...props} />
      <MobileSidebar {...(props as React.ComponentProps<"div">)} />
    </>
  );
};

export const DesktopSidebar = ({
  className,
  children,
  ...props
}: React.ComponentProps<typeof motion.div>) => {
  const { open, setOpen, animate } = useSidebar();
  return (
    <motion.div
      className={cn(
        "hidden h-full shrink-0 border-r border-slate-200 bg-white px-4 py-4 md:flex md:flex-col dark:border-slate-800 dark:bg-slate-950",
        className,
      )}
      animate={{
        width: animate ? (open ? "240px" : "64px") : "240px",
      }}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      {...props}
    >
      {children}
    </motion.div>
  );
};

export const MobileSidebar = ({
  className,
  children,
  ...props
}: React.ComponentProps<"div">) => {
  const { open, setOpen } = useSidebar();
  return (
    <div
      className={cn(
        "z-40 flex h-12 w-full flex-row items-center justify-between border-slate-200 border-b bg-white px-4 dark:border-slate-800 dark:bg-slate-950 md:hidden",
      )}
      {...props}
    >
      <div className="flex justify-end z-20 w-full">
        <Menu
          className="text-slate-700 dark:text-slate-200 cursor-pointer"
          onClick={() => setOpen(!open)}
        />
      </div>
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ x: "-100%", opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: "-100%", opacity: 0 }}
            transition={{
              duration: 0.3,
              ease: "easeInOut",
            }}
            className={cn(
              "fixed inset-0 z-[100] flex h-full w-72 flex-col justify-between bg-white p-8 shadow-2xl dark:bg-slate-950",
              className,
            )}
          >
            <div
              className="absolute right-6 top-6 z-50 text-slate-700 dark:text-slate-200 cursor-pointer"
              onClick={() => setOpen(!open)}
            >
              <X />
            </div>
            {children}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

export const SidebarLink = ({
  link,
  className,
  ...props
}: {
  link: Links;
  className?: string;
}) => {
  const { open, animate } = useSidebar();
  return (
    <a
      href={link.href}
      className={cn(
        "group/sidebar flex items-center justify-start gap-2 rounded-lg px-2 py-2 transition-colors hover:bg-slate-100 dark:hover:bg-slate-800/80",
        className,
      )}
      {...props}
    >
      <span className="shrink-0 text-slate-600 dark:text-slate-300">{link.icon}</span>
      <motion.span
        animate={{
          display: animate ? (open ? "inline-block" : "none") : "inline-block",
          opacity: animate ? (open ? 1 : 0) : 1,
        }}
        className="text-slate-700 dark:text-slate-200 text-sm font-medium group-hover/sidebar:translate-x-0.5 transition duration-150 whitespace-pre inline-block !p-0 !m-0"
      >
        {link.label}
      </motion.span>
    </a>
  );
};
