"use client";

import {
    Conversation,
    ConversationContent,
    ConversationDownload,
    ConversationEmptyState,
    ConversationScrollButton,
} from "@/components/ai-elements/conversation";
import type { PromptInputMessage } from "@/components/ai-elements/prompt-input";
import { Card } from "@/components/ui/card";
import { type ChatAttachment, useChat } from "@/hooks/useChat";
import { useUser } from "@clerk/nextjs";
import { MessageCircleIcon } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo } from "react";

import {
    Reasoning,
    ReasoningContent,
    ReasoningTrigger,
} from "@/components/ai-elements/reasoning";
import type { AgentTraceStep } from "@/hooks/useChat";

import { ChatInput } from "./ChatInput";
import { MessageBubble } from "./MessageBubble";

type ChatWindowMode = "doctor" | "patient";

type ChatWindowProps = {
  actorId: string;
  mode: ChatWindowMode;
  patientId?: string;
};

function buildOpeningMessage(mode: ChatWindowMode, name?: string | null): string {
  const salutation =
    name
      ? mode === "doctor"
        ? `Hello, Dr. ${name}! 👋`
        : `Hello, ${name}! 👋`
      : mode === "doctor"
        ? "Hello, Doctor! 👋"
        : "Hello! 👋";

  if (mode === "doctor") {
    return (
      `${salutation} I'm **OrthoAssist**, your AI-powered orthopedic assistant.\n\n` +
      `Before we start, please share your **patient's details** so I can personalise the analysis and include them in any generated reports:\n\n` +
      `- **Full Name**\n` +
      `- **Age**\n` +
      `- **Gender** (Male / Female / Other)\n\n` +
      `You can type them in one go, e.g.:\n` +
      `> *Name: John Smith, Age: 45, Gender: Male*\n\n` +
      `Once you've shared those, upload an X-ray or describe the case and I'll begin the analysis!`
    );
  }

  return (
    `${salutation} I'm **OrthoAssist**, your AI-powered orthopedic assistant.\n\n` +
    `Before we start, please share a few details so I can personalise your analysis and any reports generated for you:\n\n` +
    `- **Your Full Name**\n` +
    `- **Age**\n` +
    `- **Gender** (Male / Female / Other)\n\n` +
    `You can type them in one go, e.g.:\n` +
    `> *Name: Sarah Jones, Age: 34, Gender: Female*\n\n` +
    `After that, upload your X-ray image and I'll analyse it for you!`
  );
}

function isSupportedDocType(mediaType: string | undefined): boolean {
  if (!mediaType) {
    return false;
  }
  return (
    mediaType === "application/pdf" ||
    mediaType === "application/msword" ||
    mediaType ===
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
  );
}

function blobToDataUrl(blob: Blob): Promise<string | null> {
  return new Promise((resolve) => {
    const reader = new FileReader();
    reader.onloadend = () =>
      resolve(typeof reader.result === "string" ? reader.result : null);
    reader.onerror = () => resolve(null);
    reader.readAsDataURL(blob);
  });
}

async function blobUrlToDataUrl(url: string): Promise<string | null> {
  try {
    const response = await fetch(url);
    if (!response.ok) {
      return null;
    }
    const blob = await response.blob();
    return await blobToDataUrl(blob);
  } catch {
    return null;
  }
}

async function pickAttachmentPayload(
  files: PromptInputMessage["files"]
): Promise<{ payload: string | null; preview: ChatAttachment | null }> {
  if (files.length === 0) {
    return {
      payload: null,
      preview: null,
    };
  }

  const preferredFile =
    files.find(
      (file) =>
        typeof file.mediaType === "string" &&
        (file.mediaType.startsWith("image/") || isSupportedDocType(file.mediaType))
    ) ?? files[0];

  const name =
    typeof preferredFile.filename === "string" && preferredFile.filename.trim()
      ? preferredFile.filename
      : "Attachment";

  if (typeof preferredFile.url !== "string") {
    return {
      payload: null,
      preview: {
        mediaType: preferredFile.mediaType,
        name,
      },
    };
  }

  if (preferredFile.url.startsWith("data:")) {
    return {
      payload: preferredFile.url,
      preview: {
        dataUrl: preferredFile.url,
        mediaType: preferredFile.mediaType,
        name,
      },
    };
  }

  if (preferredFile.url.startsWith("blob:")) {
    const dataUrl = await blobUrlToDataUrl(preferredFile.url);
    return {
      payload: dataUrl,
      preview: {
        dataUrl: dataUrl ?? undefined,
        mediaType: preferredFile.mediaType,
        name,
      },
    };
  }

  return {
    payload: null,
    preview: {
      mediaType: preferredFile.mediaType,
      name,
    },
  };
}

function formatTraceForReasoning(step: AgentTraceStep): string {
  if (step.type === "supervisor_decision") {
    const agent = step.active_agent || "agent";
    const calls =
      Array.isArray(step.tool_calls) && step.tool_calls.length > 0
        ? step.tool_calls.join(", ")
        : "planning";
    return `**${agent}** → ${calls}`;
  }
  if (step.type === "tool_execution") {
    return `Running **${step.tool_name || "tool"}**`;
  }
  return JSON.stringify(step);
}

export function ChatWindow({ actorId, mode, patientId }: ChatWindowProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const currentChatId = searchParams.get("chat_id");
  const { user } = useUser();
  const actorName = user?.fullName ?? user?.firstName ?? undefined;
  const patientIdFromQuery = searchParams.get("patient_id") || undefined;

  const { chatId, messages, isLoading, liveTrace, error, sendMessage, stop } = useChat({
    actorId,
    actorRole: mode,
    actorName: actorName ?? undefined,
    initialChatId: currentChatId,
    openingMessage: buildOpeningMessage(mode, actorName),
    patientId: patientId ?? patientIdFromQuery,
  });

  useEffect(() => {
    if (!chatId || chatId === currentChatId) {
      return;
    }
    const params = new URLSearchParams(searchParams.toString());
    params.set("chat_id", chatId);
    router.replace(`?${params.toString()}`);
  }, [chatId, currentChatId, router, searchParams]);

  const handleSend = async (message: PromptInputMessage) => {
    const attachmentSelection = await pickAttachmentPayload(message.files);
    void sendMessage({
      attachment: attachmentSelection.payload,
      attachmentMeta: attachmentSelection.preview,
      text: message.text,
    });
  };

  const exportableMessages = useMemo(
    () => messages.map(({ content, role }) => ({ content, role })),
    [messages]
  );

  return (
    <section className="flex h-[calc(100vh-11rem)] min-h-[460px] max-h-[820px] flex-col gap-3">
      <Card className="relative flex min-h-0 flex-1 overflow-hidden border-slate-200/90 bg-gradient-to-b from-white to-slate-50 p-0 shadow-[0_12px_30px_rgba(15,23,42,0.08)] dark:border-slate-800 dark:bg-gradient-to-b dark:from-slate-950 dark:to-slate-900/70 dark:shadow-[0_12px_30px_rgba(2,8,23,0.45)]">
        <Conversation className="w-full">
          <ConversationContent className="gap-3 px-4 py-5 sm:px-6">
            {messages.length === 0 ? (
              <ConversationEmptyState
                description="Ask your first question to start analysis."
                icon={<MessageCircleIcon className="size-5" />}
                title="No messages yet"
              />
            ) : (
              messages.map((message) => (
                <MessageBubble
                  attachment={message.attachment}
                  content={message.content}
                  key={message.id}
                  role={message.role}
                  trace={message.trace}
                />
              ))
            )}
            {isLoading ? (
              <div className="flex items-start gap-3">
                <div className="max-w-[72ch] rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-sm dark:border-slate-700 dark:bg-slate-900/80">
                  <Reasoning isStreaming={isLoading}>
                    <ReasoningTrigger />
                    <ReasoningContent>
                      {liveTrace.length > 0
                        ? liveTrace
                            .map(
                              (step: AgentTraceStep, i: number) =>
                                `${i + 1}. ${formatTraceForReasoning(step)}`
                            )
                            .join("\n")
                        : "Analyzing your request..."}
                    </ReasoningContent>
                  </Reasoning>
                </div>
              </div>
            ) : null}
            {error ? (
              <p className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700 dark:border-red-900/60 dark:bg-red-950/30 dark:text-red-300">
                {error}
              </p>
            ) : null}
          </ConversationContent>
          <ConversationScrollButton className="border-slate-300 bg-white/90 text-slate-700 hover:bg-white dark:border-slate-700 dark:bg-slate-900/85 dark:text-slate-200 dark:hover:bg-slate-800" />
          <ConversationDownload
            className="border-slate-300 bg-white/90 text-slate-700 hover:bg-white dark:border-slate-700 dark:bg-slate-900/85 dark:text-slate-200 dark:hover:bg-slate-800"
            messages={exportableMessages}
          />
        </Conversation>
      </Card>

      <Card className="border-slate-200/90 bg-white/95 p-2 shadow-[0_10px_24px_rgba(15,23,42,0.06)] dark:border-slate-800 dark:bg-slate-950/80 dark:shadow-[0_10px_24px_rgba(2,8,23,0.45)]">
        <ChatInput
          disabled={isLoading}
          isSubmitting={isLoading}
          onSend={handleSend}
          onStop={stop}
          placeholder={
            mode === "doctor"
              ? "Ask for differential, triage, or report-ready summary..."
              : "Ask what this means, severity, and what to do next..."
          }
        />
      </Card>
    </section>
  );
}
