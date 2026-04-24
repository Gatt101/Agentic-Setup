"use client";

import { SignInButton, SignUpButton } from "@clerk/nextjs";
import { motion, useReducedMotion } from "framer-motion";
import Link from "next/link";

import { AppResizableNavbar } from "@/components/layout/AppResizableNavbar";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { HeroParallax } from "@/components/ui/hero-parallax";
import { BoneIcon } from "@/icons/BoneIcon";
import { HospitalIcon } from "@/icons/HospitalIcon";
import { ReportIcon } from "@/icons/ReportIcon";
import { XrayIcon } from "@/icons/XrayIcon";

type IconComponent = () => JSX.Element;

type SectionNavLink = {
  href: string;
  label: string;
};

type WorkflowStep = {
  detail: string;
  description: string;
  icon: IconComponent;
  title: string;
};

type OutcomeMetric = {
  label: string;
  value: string;
};

type AudienceCard = {
  bullets: string[];
  description: string;
  icon: IconComponent;
  title: string;
};

const workflowSteps: WorkflowStep[] = [
  {
    detail: "DICOM, image, and PDF ready",
    description:
      "Add studies quickly with structured intake so each case starts with the right context.",
    icon: XrayIcon,
    title: "Upload Imaging",
  },
  {
    detail: "Explainable clinical summaries",
    description:
      "Receive concise findings, severity context, and triage-ready signals in one focused view.",
    icon: BoneIcon,
    title: "Get Structured Insight",
  },
  {
    detail: "Reports and care direction",
    description:
      "Generate patient-friendly reports and route urgent cases toward nearby orthopedic care.",
    icon: ReportIcon,
    title: "Generate Action",
  },
];

const audienceCards: AudienceCard[] = [
  {
    bullets: [
      "Patient history tracking for recurring cases",
      "Faster documentation and report preparation",
      "Decision support for triage and follow-up planning",
    ],
    description:
      "Built for orthopedic workflows where speed matters, but clinical clarity matters more.",
    icon: BoneIcon,
    title: "For Doctors",
  },
  {
    bullets: [
      "Plain-language report explanations",
      "Clear urgency guidance and next steps",
      "Nearby orthopedic care suggestions",
    ],
    description:
      "Accessible communication that helps patients understand what they should do next.",
    icon: HospitalIcon,
    title: "For Patients",
  },
];

const trustBullets = [
  "Privacy-first handling of medical data and uploads",
  "Explainable outputs designed for clinical review",
  "Clinical disclaimer pathways for high-risk scenarios",
  "Structured audit trail support for operational teams",
];

const sectionNavLinks: SectionNavLink[] = [
  { href: "#workflow", label: "Workflow" },
  { href: "#audience", label: "Doctors & Patients" },
  { href: "#trust", label: "Trust & Safety" },
  { href: "#start", label: "Get Started" },
];

const outcomeMetrics: OutcomeMetric[] = [
  { label: "Case Intake", value: "Under 2 min" },
  { label: "Clinical Summary", value: "Structured output" },
  { label: "Audience Modes", value: "Doctor + Patient" },
  { label: "Workflow Fit", value: "Ortho-first" },
];

const productLinks = [
  { href: "#workflow", label: "Workflow" },
  { href: "#audience", label: "Doctor & Patient Roles" },
  { href: "#trust", label: "Trust & Safety" },
];

const platformLinks = [
  { href: "/sign-up", label: "Create Account" },
  { href: "/sign-in", label: "Log in" },
  { href: "/dashboard", label: "Open Dashboard" },
];

const containerClassName = "mx-auto w-full max-w-6xl px-6";

const orthoProducts = [
  {
    title: "X-Ray Analysis",
    link: "#",
    thumbnail: "/images/X-rayAnalysis.png",
  },
  {
    title: "Clinical Reporting",
    link: "#",
    thumbnail: "/images/ClinicalReporting.png",
  },
  {
    title: "Patient Communication",
    link: "#",
    thumbnail: "/images/PatientCommunication.png",
  },
  {
    title: "Triage Assistance",
    link: "#",
    thumbnail: "/images/TriageAssistance.png",
  },
  {
    title: "Orthopedic Insights",
    link: "#",
    thumbnail: "/images/OrthopedicInsights.png",
  },
  {
    title: "Knowledge Base",
    link: "#",
    thumbnail: "/images/KnowledgeBase.png",
  },
  {
    title: "Nearby Clinics",
    link: "#",
    thumbnail: "/images/NearbyClinics.png",
  },
  {
    title: "Treatment Plans",
    link: "#",
    thumbnail: "/images/TreatmentPlans.png",
  },
  {
    title: "PDF Reports",
    link: "#",
    thumbnail: "/images/PDFReports.png",
  },
  {
    title: "Fracture Detection",
    link: "#",
    thumbnail: "/images/X-rayAnalysis.png",
  },
];

function SectionIntro({
  eyebrow,
  subtitle,
  title,
}: {
  eyebrow: string;
  subtitle: string;
  title: string;
}) {
  return (
    <div className="mx-auto max-w-3xl text-center">
      <p className="text-xs font-semibold uppercase tracking-[0.24em] text-[var(--color-secondary)]">
        {eyebrow}
      </p>
      <h2
        className="landing-heading-font mt-3 text-3xl leading-tight text-slate-900 sm:text-4xl dark:text-slate-100"
      >
        {title}
      </h2>
      <p className="mt-4 text-base leading-relaxed text-slate-600 dark:text-slate-300">
        {subtitle}
      </p>
    </div>
  );
}

function MockProductFrame() {
  return (
    <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-[0_20px_55px_rgba(15,23,42,0.14)] dark:border-slate-800 dark:bg-slate-900 dark:shadow-[0_20px_55px_rgba(2,8,23,0.5)]">
      <div className="flex items-center justify-between rounded-2xl border border-slate-200 bg-slate-50 px-4 py-2 text-xs text-slate-500 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300">
        <div className="flex items-center gap-2">
          <span className="h-2 w-2 rounded-full bg-slate-300 dark:bg-slate-600" />
          <span className="h-2 w-2 rounded-full bg-slate-300 dark:bg-slate-600" />
          <span className="h-2 w-2 rounded-full bg-slate-300 dark:bg-slate-600" />
        </div>
        <p>OrthoAssist Clinical Workspace</p>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-[1.25fr_1fr]">
        <div className="overflow-hidden rounded-2xl border border-slate-200 dark:border-slate-700">
          <div className="flex items-center justify-between border-slate-200 border-b bg-white px-4 py-3 text-sm dark:border-slate-700 dark:bg-slate-900">
            <div className="flex items-center gap-2 text-slate-700 dark:text-slate-200">
              <XrayIcon />
              <span className="font-medium">X-ray Panel</span>
            </div>
            <span className="text-xs text-slate-500 dark:text-slate-400">Study #XR-2047</span>
          </div>
          <div className="relative h-52 bg-gradient-to-br from-slate-100 via-slate-50 to-cyan-50 p-4 dark:from-slate-900 dark:via-slate-900 dark:to-slate-800">
            <div className="absolute inset-0 bg-[linear-gradient(to_right,rgba(148,163,184,0.15)_1px,transparent_1px),linear-gradient(to_bottom,rgba(148,163,184,0.15)_1px,transparent_1px)] bg-[size:18px_18px] dark:bg-[linear-gradient(to_right,rgba(148,163,184,0.1)_1px,transparent_1px),linear-gradient(to_bottom,rgba(148,163,184,0.1)_1px,transparent_1px)]" />
            <div className="relative h-full rounded-xl border border-slate-200 bg-white/70 p-4 backdrop-blur-sm dark:border-slate-700 dark:bg-slate-900/70">
              <div className="flex h-full items-center justify-center rounded-lg border border-dashed border-slate-300 bg-slate-50/80 text-sm text-slate-500 dark:border-slate-600 dark:bg-slate-800/70 dark:text-slate-300">
                Distal radius region highlighted
              </div>
            </div>
          </div>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-900">
          <div className="flex items-center gap-2 text-sm font-medium text-slate-700 dark:text-slate-200">
            <BoneIcon />
            Clinical Assistant
          </div>
          <div className="mt-3 space-y-2 text-sm">
            <div className="rounded-xl bg-slate-100 p-3 text-slate-700 dark:bg-slate-800 dark:text-slate-200">
              Fracture pattern likely involves distal radius with moderate displacement.
            </div>
            <div className="rounded-xl bg-[rgba(79,93,149,0.1)] p-3 text-slate-700 dark:bg-[rgba(143,162,255,0.22)] dark:text-slate-100">
              Recommend urgent ortho consultation and immobilization guidance.
            </div>
          </div>
        </div>
      </div>

      <div className="mt-4 grid gap-4 sm:grid-cols-[1fr_auto]">
        <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 dark:border-slate-700 dark:bg-slate-800">
          <div className="flex items-center gap-2 text-sm font-medium text-slate-700 dark:text-slate-100">
            <ReportIcon />
            Report Summary
          </div>
          <ul className="mt-2 space-y-1 text-sm text-slate-600 dark:text-slate-300">
            <li>Structured finding with confidence context</li>
            <li>Patient-readable explanation and care plan</li>
            <li>Referral-ready note for orthopedic follow-up</li>
          </ul>
        </div>
        <div className="flex items-center justify-between gap-3 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          <HospitalIcon />
          <span className="font-medium">Triage: Amber</span>
        </div>
      </div>
    </div>
  );
}

function LandingSectionNav() {
  return (
    <nav aria-label="Landing Sections" className="relative mt-12">
      <div className="mx-auto flex w-full max-w-5xl flex-wrap items-center justify-center gap-2 rounded-2xl border border-slate-200 bg-white/90 p-2 shadow-[0_12px_22px_rgba(15,23,42,0.08)] backdrop-blur-sm dark:border-slate-800 dark:bg-slate-900/90 dark:shadow-[0_12px_22px_rgba(2,8,23,0.45)]">
        {sectionNavLinks.map((link) => (
          <a
            className="rounded-lg px-3 py-2 text-sm font-medium text-slate-600 transition-colors hover:bg-slate-100 hover:text-slate-900 dark:text-slate-300 dark:hover:bg-slate-800 dark:hover:text-slate-100"
            href={link.href}
            key={link.href}
          >
            {link.label}
          </a>
        ))}
      </div>
    </nav>
  );
}

function OutcomeStrip() {
  return (
    <div className="mt-10 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      {outcomeMetrics.map((metric) => (
        <div
          className="rounded-xl border border-slate-200 bg-white/90 px-4 py-3 text-center shadow-[0_6px_16px_rgba(15,23,42,0.06)] transition-transform duration-200 hover:-translate-y-0.5 dark:border-slate-700 dark:bg-slate-900/90 dark:shadow-[0_6px_16px_rgba(2,8,23,0.4)]"
          key={metric.label}
        >
          <p className="text-lg font-semibold text-slate-900 dark:text-slate-100">{metric.value}</p>
          <p className="mt-1 text-xs font-medium uppercase tracking-[0.14em] text-slate-500 dark:text-slate-400">
            {metric.label}
          </p>
        </div>
      ))}
    </div>
  );
}

function LandingFooter() {
  return (
    <footer className={`${containerClassName} relative pt-14`}>
      <div className="rounded-2xl border border-slate-200 bg-white/90 p-6 dark:border-slate-800 dark:bg-slate-900/90">
        <div className="grid gap-8 md:grid-cols-3">
          <div>
            <p className="font-semibold text-lg text-slate-900 dark:text-slate-100">
              OrthoAssist
            </p>
            <p className="mt-3 text-sm leading-relaxed text-slate-600 dark:text-slate-300">
              Clinical workflow software for orthopedic imaging review, structured insights, and patient-friendly communication.
            </p>
          </div>

          <div>
            <p className="font-semibold text-sm uppercase tracking-[0.14em] text-slate-500 dark:text-slate-400">
              Product
            </p>
            <ul className="mt-3 space-y-2 text-sm text-slate-700 dark:text-slate-300">
              {productLinks.map((item) => (
                <li key={item.label}>
                  <a
                    className="transition-colors hover:text-slate-900 dark:hover:text-slate-100"
                    href={item.href}
                  >
                    {item.label}
                  </a>
                </li>
              ))}
            </ul>
          </div>

          <div>
            <p className="font-semibold text-sm uppercase tracking-[0.14em] text-slate-500 dark:text-slate-400">
              Platform
            </p>
            <ul className="mt-3 space-y-2 text-sm text-slate-700 dark:text-slate-300">
              {platformLinks.map((item) => (
                <li key={item.label}>
                  <Link
                    className="transition-colors hover:text-slate-900 dark:hover:text-slate-100"
                    href={item.href}
                  >
                    {item.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        </div>

        <div className="mt-8 border-slate-200 border-t pt-4 text-xs text-slate-500 dark:border-slate-800 dark:text-slate-400">
          <p>2026 OrthoAssist. Clinical decision support software for orthopedic workflows.</p>
        </div>
      </div>
    </footer>
  );
}

export function LandingPage() {
  const prefersReducedMotion = useReducedMotion();
  const yOffset = prefersReducedMotion ? 0 : 20;

  return (
    <main
      className="relative overflow-hidden bg-[radial-gradient(circle_at_10%_10%,rgba(79,93,149,0.12),transparent_34%),radial-gradient(circle_at_90%_15%,rgba(107,139,115,0.16),transparent_34%),#f7f8f8] pb-24 dark:bg-[radial-gradient(circle_at_10%_10%,rgba(143,162,255,0.16),transparent_34%),radial-gradient(circle_at_90%_15%,rgba(152,182,162,0.18),transparent_34%),#050913]"
    >
      <AppResizableNavbar />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 bg-[linear-gradient(to_right,rgba(15,23,42,0.04)_1px,transparent_1px),linear-gradient(to_bottom,rgba(15,23,42,0.04)_1px,transparent_1px)] bg-[size:40px_40px] [mask-image:radial-gradient(circle_at_center,black_45%,transparent_85%)] dark:bg-[linear-gradient(to_right,rgba(148,163,184,0.08)_1px,transparent_1px),linear-gradient(to_bottom,rgba(148,163,184,0.08)_1px,transparent_1px)]"
      />

      {/* ── Hero Parallax ─────────────────────────────────────── */}
      <HeroParallax
        products={orthoProducts}
        header={
          <div className="relative z-20 mx-auto w-full max-w-7xl px-6 pt-10 pb-20 md:pt-16 md:pb-36">
            <motion.div
              animate={{ opacity: 1, y: 0 }}
              initial={{ opacity: 0, y: yOffset }}
              transition={{ duration: 0.5, ease: "easeOut" }}
            >
              <p className="w-fit rounded-full border border-[var(--color-primary)]/30 bg-[var(--color-primary)]/8 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-[var(--color-primary)] mb-6">
                Orthopedic Clinical AI
              </p>
              <h1 className="landing-heading-font text-4xl leading-tight text-slate-900 sm:text-5xl md:text-7xl dark:text-slate-100">
                OrthoAssist
                <span className="mt-2 block text-[var(--color-primary)]">
                  AI-Powered Orthopedic{" "}
                  <br className="hidden md:block" />
                  Clinical Platform
                </span>
              </h1>
              <p className="mt-6 max-w-2xl text-base leading-relaxed text-slate-600 sm:text-lg md:text-xl dark:text-slate-300">
                Analyze X-rays, generate structured reports, and guide orthopedic
                care with clarity and clinical confidence.
              </p>
              <div className="mt-8 flex flex-wrap items-center gap-3">
                <SignUpButton forceRedirectUrl="/select-role" mode="redirect">
                  <Button
                    className="h-11 rounded-xl px-6 text-sm font-semibold !bg-[var(--color-primary)] !text-white hover:!bg-[#445188]"
                    type="button"
                  >
                    Get Started
                  </Button>
                </SignUpButton>
                <SignInButton forceRedirectUrl="/select-role" mode="redirect">
                  <Button
                    className="h-11 rounded-xl border-slate-300 bg-white/90 px-6 text-sm font-semibold text-slate-800 hover:bg-white dark:border-slate-700 dark:bg-slate-900/90 dark:text-slate-100 dark:hover:bg-slate-800"
                    type="button"
                    variant="outline"
                  >
                    Log in
                  </Button>
                </SignInButton>
                <Dialog>
                  <DialogTrigger asChild>
                    <Button
                      className="h-11 rounded-xl border-slate-300 bg-white/90 px-5 text-sm font-semibold text-slate-800 hover:bg-white dark:border-slate-700 dark:bg-slate-900/90 dark:text-slate-100 dark:hover:bg-slate-800"
                      type="button"
                      variant="outline"
                    >
                      View Demo
                    </Button>
                  </DialogTrigger>
                  <DialogContent className="border-slate-200 bg-white/95 sm:max-w-md dark:border-slate-800 dark:bg-slate-950/95">
                    <DialogHeader>
                      <DialogTitle className="text-slate-900 dark:text-slate-100">
                        Demo Coming Soon
                      </DialogTitle>
                      <DialogDescription className="text-slate-600 dark:text-slate-300">
                        We&apos;ll get a guided OrthoAssist demo to you soon.
                      </DialogDescription>
                    </DialogHeader>
                    <DialogFooter>
                      <DialogClose asChild>
                        <Button
                          className="h-10 rounded-lg px-5 text-sm font-semibold"
                          type="button"
                        >
                          Close
                        </Button>
                      </DialogClose>
                    </DialogFooter>
                  </DialogContent>
                </Dialog>
              </div>
              <div className="mt-10 grid gap-3 sm:grid-cols-2 max-w-lg">
                <div className="rounded-xl border border-slate-200 bg-white/80 backdrop-blur-sm px-4 py-3 text-sm text-slate-700 dark:border-slate-700 dark:bg-slate-900/80 dark:text-slate-300">
                  <p className="font-semibold text-slate-900 dark:text-slate-100">Workflow-first</p>
                  <p className="mt-1">Designed around orthopedic clinical flow.</p>
                </div>
                <div className="rounded-xl border border-slate-200 bg-white/80 backdrop-blur-sm px-4 py-3 text-sm text-slate-700 dark:border-slate-700 dark:bg-slate-900/80 dark:text-slate-300">
                  <p className="font-semibold text-slate-900 dark:text-slate-100">Dual audience</p>
                  <p className="mt-1">Doctor precision, patient-friendly output.</p>
                </div>
              </div>
            </motion.div>
          </div>
        }
      />

      {/* ── Section Nav + Metrics ──────────────────────────────── */}
      <div className={`${containerClassName} relative pb-20 pt-4`}>
        <LandingSectionNav />
        <OutcomeStrip />
      </div>

      <motion.section
        className={`${containerClassName} relative scroll-mt-28 py-16`}
        id="workflow"
        initial={{ opacity: 0, y: yOffset }}
        transition={{ duration: 0.45, ease: "easeOut" }}
        viewport={{ once: true, amount: 0.2 }}
        whileInView={{ opacity: 1, y: 0 }}
      >
        <SectionIntro
          eyebrow="Clinical Workflow"
          subtitle="OrthoAssist keeps orthopedic teams on a clear path from image intake to decision-ready output."
          title="From X-ray to Actionable Insight"
        />
        <div className="mt-10 grid gap-4 md:grid-cols-3">
          {workflowSteps.map((step, index) => (
            <motion.div
              className="rounded-2xl border border-slate-200 bg-white p-5 shadow-[0_8px_24px_rgba(15,23,42,0.08)] transition-transform duration-200 hover:-translate-y-0.5 dark:border-slate-700 dark:bg-slate-900 dark:shadow-[0_8px_24px_rgba(2,8,23,0.45)]"
              key={step.title}
              initial={{ opacity: 0, y: yOffset }}
              transition={{
                duration: 0.35,
                delay: prefersReducedMotion ? 0 : index * 0.08,
                ease: "easeOut",
              }}
              viewport={{ once: true, amount: 0.35 }}
              whileInView={{ opacity: 1, y: 0 }}
            >
              <div className="flex items-center justify-between">
                <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-100 text-[var(--color-primary)] dark:bg-slate-800">
                  <step.icon />
                </span>
                <span className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-400 dark:text-slate-500">
                  Step {index + 1}
                </span>
              </div>
              <h3 className="mt-4 text-lg font-semibold text-slate-900 dark:text-slate-100">
                {step.title}
              </h3>
              <p className="mt-2 text-sm leading-relaxed text-slate-600 dark:text-slate-300">
                {step.description}
              </p>
              <p className="mt-4 text-xs font-medium text-[var(--color-secondary)]">{step.detail}</p>
            </motion.div>
          ))}
        </div>
      </motion.section>

      <motion.section
        className={`${containerClassName} relative scroll-mt-28 py-16`}
        id="audience"
        initial={{ opacity: 0, y: yOffset }}
        transition={{ duration: 0.45, ease: "easeOut" }}
        viewport={{ once: true, amount: 0.2 }}
        whileInView={{ opacity: 1, y: 0 }}
      >
        <SectionIntro
          eyebrow="Role-Aware Experience"
          subtitle="A shared platform with role-specific workflows for clinical teams and patient communication."
          title="Built for Doctors, Accessible for Patients"
        />
        <div className="mt-10 grid gap-4 lg:grid-cols-2">
          {audienceCards.map((card, index) => (
            <motion.div
              className="rounded-3xl border border-slate-200 bg-white p-6 shadow-[0_8px_24px_rgba(15,23,42,0.08)] transition-transform duration-200 hover:-translate-y-0.5 dark:border-slate-700 dark:bg-slate-900 dark:shadow-[0_8px_24px_rgba(2,8,23,0.45)]"
              key={card.title}
              initial={{ opacity: 0, y: yOffset }}
              transition={{
                duration: 0.35,
                delay: prefersReducedMotion ? 0 : index * 0.1,
                ease: "easeOut",
              }}
              viewport={{ once: true, amount: 0.35 }}
              whileInView={{ opacity: 1, y: 0 }}
            >
              <div className="flex items-center gap-3 text-slate-900 dark:text-slate-100">
                <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-slate-100 text-[var(--color-primary)] dark:bg-slate-800">
                  <card.icon />
                </span>
                <h3 className="text-xl font-semibold">{card.title}</h3>
              </div>
              <p className="mt-4 text-sm leading-relaxed text-slate-600 dark:text-slate-300">
                {card.description}
              </p>
              <ul className="mt-5 space-y-2 text-sm text-slate-700 dark:text-slate-300">
                {card.bullets.map((bullet) => (
                  <li className="flex items-start gap-2" key={bullet}>
                    <span className="mt-1.5 h-2 w-2 flex-none rounded-full bg-[var(--color-secondary)]" />
                    <span>{bullet}</span>
                  </li>
                ))}
              </ul>
            </motion.div>
          ))}
        </div>
      </motion.section>

      <motion.section
        className={`${containerClassName} relative scroll-mt-28 py-16`}
        id="trust"
        initial={{ opacity: 0, y: yOffset }}
        transition={{ duration: 0.45, ease: "easeOut" }}
        viewport={{ once: true, amount: 0.2 }}
        whileInView={{ opacity: 1, y: 0 }}
      >
        <div className="rounded-3xl border border-slate-200 bg-white p-8 shadow-[0_12px_30px_rgba(15,23,42,0.08)] sm:p-10 dark:border-slate-700 dark:bg-slate-900 dark:shadow-[0_12px_30px_rgba(2,8,23,0.5)]">
          <SectionIntro
            eyebrow="Trust & Safety"
            subtitle="Healthcare workflows require clear boundaries, operational transparency, and accountable guidance."
            title="Built with Clinical Responsibility"
          />
          <div className="mx-auto mt-8 grid max-w-4xl gap-3">
            {trustBullets.map((item, index) => (
              <motion.div
                className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
                key={item}
                initial={{ opacity: 0, y: yOffset }}
                transition={{
                  duration: 0.35,
                  delay: prefersReducedMotion ? 0 : index * 0.08,
                  ease: "easeOut",
                }}
                viewport={{ once: true, amount: 0.35 }}
                whileInView={{ opacity: 1, y: 0 }}
              >
                {item}
              </motion.div>
            ))}
          </div>
        </div>
      </motion.section>

      <motion.section
        className={`${containerClassName} relative scroll-mt-28 pt-16`}
        id="start"
        initial={{ opacity: 0, y: yOffset }}
        transition={{ duration: 0.45, ease: "easeOut" }}
        viewport={{ once: true, amount: 0.3 }}
        whileInView={{ opacity: 1, y: 0 }}
      >
        <div className="rounded-3xl border border-slate-200 bg-[linear-gradient(135deg,#f1f4ff_0%,#f6faf8_45%,#fff7e6_100%)] px-6 py-10 text-center sm:px-10 sm:py-12 dark:border-slate-700 dark:bg-[linear-gradient(135deg,#171e37_0%,#132228_45%,#2e2516_100%)]">
          <h2 className="landing-heading-font text-3xl text-slate-900 sm:text-4xl dark:text-slate-100">
            Ready to bring clinical-grade orthopedic support to your workflow?
          </h2>
          <p className="mx-auto mt-4 max-w-2xl text-sm leading-relaxed text-slate-600 sm:text-base dark:text-slate-300">
            Start with OrthoAssist and move from fragmented case handling to consistent, decision-ready orthopedic workflows.
          </p>
          <div className="mt-7 flex flex-wrap items-center justify-center gap-3">
            <SignUpButton forceRedirectUrl="/select-role" mode="redirect">
              <Button
                className="h-11 rounded-xl px-6 text-sm font-semibold !bg-[var(--color-primary)] !text-white hover:!bg-[#445188]"
                type="button"
              >
                Get Started
              </Button>
            </SignUpButton>
            <SignInButton forceRedirectUrl="/select-role" mode="redirect">
              <Button
                className="h-11 rounded-xl border-slate-300 bg-white px-6 text-sm font-semibold text-slate-800 hover:bg-slate-100 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100 dark:hover:bg-slate-800"
                type="button"
                variant="outline"
              >
                Log in
              </Button>
            </SignInButton>
          </div>
        </div>
      </motion.section>
      <LandingFooter />
    </main>
  );
}
