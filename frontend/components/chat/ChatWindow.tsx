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
import { MessageCircleIcon } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo } from "react";

import { ChatInput } from "./ChatInput";
import { MessageBubble } from "./MessageBubble";

type ChatWindowMode = "doctor" | "patient";

type ChatWindowProps = {
  actorId: string;
  mode: ChatWindowMode;
  patientId?: string;
};

const openingMessageByMode: Record<ChatWindowMode, string> = {
  doctor:
    "I am ready to assist with orthopedic triage, differential context, and report drafting.",
  patient:
    "I can help explain your report in plain language and suggest practical next steps.",
};

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

export function ChatWindow({ actorId, mode, patientId }: ChatWindowProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const currentChatId = searchParams.get("chat_id");
  const patientIdFromQuery = searchParams.get("patient_id") || undefined;

  const { chatId, messages, isLoading, liveTrace, error, sendMessage, stop } = useChat({
    actorId,
    actorRole: mode,
    initialChatId: currentChatId,
    openingMessage: openingMessageByMode[mode],
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
              <MessageBubble
                content="Working on your request..."
                role="assistant"
                trace={liveTrace}
              />
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
