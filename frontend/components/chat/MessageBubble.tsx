"use client";

import {
  Message,
  MessageContent,
  MessageResponse,
} from "@/components/ai-elements/message";
import type { AgentTraceStep, ChatAttachment } from "@/hooks/useChat";
import { cn } from "@/lib/utils";
import { DownloadIcon } from "lucide-react";

import { AttachmentPreview } from "./AttachmentPreview";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api";

function extractReportUrl(text: string): string | null {
  const match = text.match(/Report:\s*(\/reports\/[^\s]+\.pdf)/i);
  return match ? match[1] : null;
}

function stripReportLine(text: string): string {
  return text.replace(/\n*Report:\s*\/reports\/[^\s]+\.pdf/i, "").trimEnd();
}

export type ChatRole = "assistant" | "user";

type MessageBubbleProps = {
  attachment?: ChatAttachment;
  content: string;
  role: ChatRole;
  trace?: AgentTraceStep[];
};

function formatTraceStep(step: AgentTraceStep): string {
  if (step.type === "supervisor_decision") {
    const iteration = typeof step.iteration === "number" ? `iter ${step.iteration}` : "iter ?";
    const agent = step.active_agent || "unknown_agent";
    const calls = Array.isArray(step.tool_calls) && step.tool_calls.length > 0 ? step.tool_calls.join(", ") : "none";
    return `${iteration} | ${agent} | planned: ${calls}`;
  }
  if (step.type === "tool_execution") {
    return `executed: ${step.tool_name || "unknown_tool"}`;
  }
  return JSON.stringify(step);
}

export function MessageBubble({ attachment, content, role, trace }: MessageBubbleProps) {
  const isUser = role === "user";
  const reportUrl = !isUser ? extractReportUrl(content) : null;
  const displayContent = reportUrl ? stripReportLine(content) : content;

  return (
    <Message from={role}>
      <MessageContent className="group-[.is-user]:rounded-none group-[.is-user]:bg-transparent group-[.is-user]:px-0 group-[.is-user]:py-0">
        <div
          className={cn(
            "max-w-[72ch] rounded-2xl border px-4 py-3 shadow-sm",
            isUser
              ? "ml-auto border-[var(--color-primary)]/30 bg-[var(--color-primary)]/10 text-slate-900 dark:border-[var(--color-primary)]/40 dark:bg-[var(--color-primary)]/20 dark:text-slate-50"
              : "border-slate-200 bg-white text-slate-800 dark:border-slate-700 dark:bg-slate-900/80 dark:text-slate-100"
          )}
        >
          {displayContent ? (
            isUser ? (
              <p className="m-0 whitespace-pre-wrap text-[15px] leading-relaxed">{displayContent}</p>
            ) : (
              <MessageResponse className="text-[15px] leading-relaxed">{displayContent}</MessageResponse>
            )
          ) : null}
          {reportUrl ? (
            <a
              href={`${API_BASE_URL.replace(/\/api$/, "")}${reportUrl}`}
              target="_blank"
              rel="noopener noreferrer"
              download
              className="mt-3 inline-flex items-center gap-2 rounded-lg border border-[var(--color-primary)]/30 bg-[var(--color-primary)]/10 px-3 py-2 text-sm font-medium text-[var(--color-primary)] transition-colors hover:bg-[var(--color-primary)]/20 dark:border-[var(--color-primary)]/40 dark:bg-[var(--color-primary)]/15 dark:hover:bg-[var(--color-primary)]/25"
            >
              <DownloadIcon className="size-4" />
              Download Report (PDF)
            </a>
          ) : null}
          {attachment ? <AttachmentPreview attachment={attachment} /> : null}
          {role === "assistant" && Array.isArray(trace) && trace.length > 0 ? (
            <details className="mt-2 rounded-md border border-slate-200 bg-slate-50/70 p-2 text-xs text-slate-700 dark:border-slate-700 dark:bg-slate-900/40 dark:text-slate-200">
              <summary className="cursor-pointer font-medium">Agent trace</summary>
              <div className="mt-2 space-y-1">
                {trace.map((step, index) => (
                  <p className="m-0" key={`trace-${index.toString(36)}`}>
                    {index + 1}. {formatTraceStep(step)}
                  </p>
                ))}
              </div>
            </details>
          ) : null}
        </div>
      </MessageContent>
    </Message>
  );
}
