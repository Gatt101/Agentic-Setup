"use client";

import {
    Message,
    MessageContent,
    MessageResponse,
} from "@/components/ai-elements/message";
import type { AgentTraceStep, ChatAttachment } from "@/hooks/useChat";
import { cn } from "@/lib/utils";

import { AttachmentPreview } from "./AttachmentPreview";

export type ChatRole = "assistant" | "user";

type MessageBubbleProps = {
  attachment?: ChatAttachment;
  content: string;
  role: ChatRole;
  trace?: AgentTraceStep[];
};

/** Strip trailing `\n\nReport: <url>` lines injected by the backend and return them separately.
 * Handles both absolute (https://...) and relative (/storage/...) URLs. */
function extractReportUrl(text: string): { body: string; reportUrl: string | null } {
  // Match both absolute URLs (https://...) and relative paths (/storage/...)
  const match = text.match(/\n\nReport:\s*((?:https?:\/\/|\/)\S+)\s*$/);
  if (!match) return { body: text, reportUrl: null };
  let url = match[1];
  // Relative path — prepend the backend origin so the browser fetches from the API server
  if (url.startsWith('/')) {
    const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000/api';
    // Strip the /api suffix to get the bare origin (e.g. http://localhost:8000)
    const origin = apiBase.replace(/\/api\/?$/, '');
    url = `${origin}${url}`;
  }
  return { body: text.slice(0, match.index), reportUrl: url };
}

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
  const { body, reportUrl } = !isUser ? extractReportUrl(content) : { body: content, reportUrl: null };

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
          {body ? (
            isUser ? (
              <p className="m-0 whitespace-pre-wrap text-[15px] leading-relaxed">{body}</p>
            ) : (
              <MessageResponse className="text-[15px] leading-relaxed">{body}</MessageResponse>
            )
          ) : null}
          {reportUrl ? (
            <a
              href={reportUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-3 flex w-fit items-center gap-2 rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-sm font-medium text-blue-700 transition-colors hover:bg-blue-100 dark:border-blue-700 dark:bg-blue-900/30 dark:text-blue-300 dark:hover:bg-blue-900/50"
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                <polyline points="14 2 14 8 20 8"/>
                <line x1="12" y1="18" x2="12" y2="12"/>
                <line x1="9" y1="15" x2="15" y2="15"/>
              </svg>
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
