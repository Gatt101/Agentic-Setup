"use client";

import { useCallback, useRef, useState } from "react";

export type ChatRole = "assistant" | "user";

export type ChatAttachment = {
  dataUrl?: string;
  mediaType?: string;
  name: string;
};

export type ChatMessage = {
  attachment?: ChatAttachment;
  content: string;
  id: string;
  role: ChatRole;
};

type ChatApiResponse = {
  detail?: string;
  final_response?: string;
  session_id?: string;
};

type UseChatOptions = {
  openingMessage: string;
};

type SendMessageInput = {
  attachment?: string | null;
  attachmentMeta?: ChatAttachment | null;
  text: string;
};

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api";
const RAW_CHAT_TIMEOUT_MS = Number(
  process.env.NEXT_PUBLIC_CHAT_TIMEOUT_MS ?? 60000
);
const CHAT_TIMEOUT_MS =
  Number.isFinite(RAW_CHAT_TIMEOUT_MS) && RAW_CHAT_TIMEOUT_MS > 0
    ? Math.max(30000, RAW_CHAT_TIMEOUT_MS)
    : 60000;

function createMessageId(prefix: string): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return `${prefix}-${crypto.randomUUID()}`;
  }
  return `${prefix}-${Date.now().toString(36)}`;
}

export function useChat({ openingMessage }: UseChatOptions) {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      content: openingMessage,
      id: "opening-assistant-message",
      role: "assistant",
    },
  ]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const sessionIdRef = useRef<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const appendAssistantMessage = useCallback((content: string) => {
    setMessages((previous) => [
      ...previous,
      {
        content,
        id: createMessageId("assistant"),
        role: "assistant",
      },
    ]);
  }, []);

  const sendMessage = useCallback(
    async ({ text: rawText, attachment, attachmentMeta }: SendMessageInput) => {
      const text = rawText.trim();
      const hasAttachment = Boolean(attachment || attachmentMeta);

      if ((!text && !hasAttachment) || isLoading) {
        return;
      }

      const userMessage =
        text || (hasAttachment ? "Uploaded an attachment for analysis." : "");

      setMessages((previous) => [
        ...previous,
        {
          attachment: attachmentMeta ?? undefined,
          content: userMessage,
          id: createMessageId("user"),
          role: "user",
        },
      ]);

      setIsLoading(true);
      setError(null);

      const controller = new AbortController();
      abortRef.current = controller;
      const timeoutHandle = setTimeout(() => {
        controller.abort();
      }, CHAT_TIMEOUT_MS);

      try {
        const response = await fetch(`${API_BASE_URL}/chat`, {
          body: JSON.stringify({
            attachment: attachment ?? undefined,
            message: text || "Please analyze the attached file.",
            session_id: sessionIdRef.current ?? undefined,
          }),
          cache: "no-store",
          headers: {
            "Content-Type": "application/json",
          },
          method: "POST",
          signal: controller.signal,
        });

        if (!response.ok) {
          let errorMessage = `Request failed with status ${response.status}`;
          try {
            const errorPayload = (await response.json()) as ChatApiResponse;
            if (typeof errorPayload.detail === "string" && errorPayload.detail.trim()) {
              errorMessage = errorPayload.detail.trim();
            }
          } catch {
            // Ignore parse failure and keep status-based message.
          }
          throw new Error(errorMessage);
        }

        const payload = (await response.json()) as ChatApiResponse;
        if (payload.session_id) {
          sessionIdRef.current = payload.session_id;
        }

        appendAssistantMessage(
          payload.final_response?.trim() || "No response generated."
        );
      } catch (errorValue) {
        const fallback =
          errorValue instanceof DOMException && errorValue.name === "AbortError"
            ? "The request timed out. Please try again."
            : errorValue instanceof Error && errorValue.message.trim()
              ? errorValue.message
              : "Chat request failed. Please try again.";
        setError(fallback);
        appendAssistantMessage(fallback);
      } finally {
        clearTimeout(timeoutHandle);
        if (abortRef.current === controller) {
          abortRef.current = null;
        }
        setIsLoading(false);
      }
    },
    [appendAssistantMessage, isLoading]
  );

  const stop = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
  }, []);

  return {
    error,
    isLoading,
    messages,
    sendMessage,
    stop,
  };
}
