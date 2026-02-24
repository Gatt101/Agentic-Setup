"use client";

import {
  Message,
  MessageContent,
} from "@/components/ai-elements/message";
import type { ChatAttachment } from "@/hooks/useChat";
import { cn } from "@/lib/utils";

import { AttachmentPreview } from "./AttachmentPreview";

export type ChatRole = "assistant" | "user";

type MessageBubbleProps = {
  attachment?: ChatAttachment;
  content: string;
  role: ChatRole;
};

export function MessageBubble({ attachment, content, role }: MessageBubbleProps) {
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
          {content ? <p className="m-0 whitespace-pre-wrap text-[15px] leading-relaxed">{content}</p> : null}
          {attachment ? <AttachmentPreview attachment={attachment} /> : null}
        </div>
      </MessageContent>
    </Message>
  );
}
