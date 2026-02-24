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
          {content ? (
            isUser ? (
              <p className="m-0 whitespace-pre-wrap text-[15px] leading-relaxed">{content}</p>
            ) : (
              <MessageResponse className="text-[15px] leading-relaxed">{content}</MessageResponse>
            )
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
