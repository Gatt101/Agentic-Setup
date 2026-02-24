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
import { useChat } from "@/hooks/useChat";
import { MessageCircleIcon } from "lucide-react";
import { useMemo } from "react";

import { ChatInput } from "./ChatInput";
import { MessageBubble } from "./MessageBubble";

type ChatWindowMode = "doctor" | "patient";

type ChatWindowProps = {
  mode: ChatWindowMode;
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
): Promise<string | null> {
  if (files.length === 0) {
    return null;
  }

  const preferredFile =
    files.find(
      (file) =>
        typeof file.mediaType === "string" &&
        (file.mediaType.startsWith("image/") || isSupportedDocType(file.mediaType))
    ) ?? files[0];

  if (typeof preferredFile.url !== "string") {
    return null;
  }

  if (preferredFile.url.startsWith("data:")) {
    return preferredFile.url;
  }

  if (preferredFile.url.startsWith("blob:")) {
    return await blobUrlToDataUrl(preferredFile.url);
  }

  return null;
}

export function ChatWindow({ mode }: ChatWindowProps) {
  const { messages, isLoading, error, sendMessage, stop } = useChat({
    openingMessage: openingMessageByMode[mode],
  });

  const handleSend = async (message: PromptInputMessage) => {
    const attachment = await pickAttachmentPayload(message.files);
    void sendMessage({
      attachment,
      text: message.text,
    });
  };

  const exportableMessages = useMemo(
    () => messages.map(({ content, role }) => ({ content, role })),
    [messages]
  );

  return (
    <section className="flex h-[calc(100vh-16rem)] min-h-[560px] flex-col gap-4">
      <Card className="relative flex min-h-0 flex-1 overflow-hidden p-0">
        <Conversation className="w-full">
          <ConversationContent className="gap-4">
            {messages.length === 0 ? (
              <ConversationEmptyState
                description="Ask your first question to start analysis."
                icon={<MessageCircleIcon className="size-5" />}
                title="No messages yet"
              />
            ) : (
              messages.map((message) => (
                <MessageBubble
                  content={message.content}
                  key={message.id}
                  role={message.role}
                />
              ))
            )}
            {isLoading ? (
              <MessageBubble content="Working on your request..." role="assistant" />
            ) : null}
            {error ? (
              <p className="text-xs text-red-600 dark:text-red-400">{error}</p>
            ) : null}
          </ConversationContent>
          <ConversationScrollButton />
          <ConversationDownload messages={exportableMessages} />
        </Conversation>
      </Card>

      <Card className="p-2">
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
