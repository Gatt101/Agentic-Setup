"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

export type ChatRole = "assistant" | "user";

export type ChatAttachment = {
  dataUrl?: string;
  mediaType?: string;
  name: string;
};

export type AgentTraceStep = {
  active_agent?: string;
  iteration?: number;
  tool_calls?: string[];
  tool_name?: string;
  type?: string;
};

export type ChatMessage = {
  attachment?: ChatAttachment;
  content: string;
  id: string;
  trace?: AgentTraceStep[];
  role: ChatRole;
};

export type ChatSessionSummary = {
  chat_id: string;
  created_at: string;
  doctor_id?: string | null;
  last_message_at: string;
  owner_role: string;
  patient_id: string;
  title: string;
};

type ChatApiResponse = {
  annotated_image_base64?: string;
  agent_trace?: AgentTraceStep[];
  chat_id?: string;
  detail?: string;
  final_response?: string;
  message_id?: string;
  session_id?: string;
};

type ChatSessionCreateResponse = {
  chat_id: string;
  title: string;
};

type ChatMessageRecord = {
  agent_trace?: AgentTraceStep[];
  annotated_image_base64?: string | null;
  attachment_data_url?: string | null;
  chat_id: string;
  content: string;
  message_id: string;
  sender_role: string;
};

type TraceApiResponse = {
  status?: string;
  trace?: AgentTraceStep[];
};

type UseChatOptions = {
  actorId: string;
  actorName?: string | null;
  actorRole: "doctor" | "patient";
  initialChatId?: string | null;
  openingMessage: string;
  patientId?: string | null;
};

type SendMessageInput = {
  attachment?: string | null;
  attachmentMeta?: ChatAttachment | null;
  text: string;
};

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api";
const RAW_CHAT_TIMEOUT_MS = Number(process.env.NEXT_PUBLIC_CHAT_TIMEOUT_MS ?? 60000);
const CHAT_TIMEOUT_MS = Number.isFinite(RAW_CHAT_TIMEOUT_MS) && RAW_CHAT_TIMEOUT_MS > 0
  ? Math.max(30000, RAW_CHAT_TIMEOUT_MS)
  : 60000;

function createMessageId(prefix: string): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return `${prefix}-${crypto.randomUUID()}`;
  }
  return `${prefix}-${Date.now().toString(36)}`;
}

function deriveChatTitle(text: string): string {
  const cleaned = text.replace(/\s+/g, " ").trim();
  if (!cleaned) {
    return "X-ray Analysis";
  }
  return cleaned.length > 70 ? `${cleaned.slice(0, 70).trimEnd()}...` : cleaned;
}

function toChatMessage(record: ChatMessageRecord): ChatMessage {
  const sender = record.sender_role === "assistant" ? "assistant" : "user";
  let attachment: ChatAttachment | undefined;

  if (sender === "user" && record.attachment_data_url) {
    attachment = {
      dataUrl: record.attachment_data_url,
      mediaType: record.attachment_data_url.startsWith("data:image/") ? "image/png" : undefined,
      name: "Uploaded attachment",
    };
  }
  if (sender === "assistant" && record.annotated_image_base64) {
    attachment = {
      dataUrl: `data:image/png;base64,${record.annotated_image_base64}`,
      mediaType: "image/png",
      name: "Annotated X-ray",
    };
  }

  return {
    attachment,
    content: record.content,
    id: record.message_id || createMessageId(sender),
    role: sender,
    trace: Array.isArray(record.agent_trace) ? record.agent_trace : undefined,
  };
}

export function useChat({ actorId, actorName, actorRole, initialChatId, openingMessage, patientId }: UseChatOptions) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [liveTrace, setLiveTrace] = useState<AgentTraceStep[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [chatId, setChatId] = useState<string | null>(initialChatId ?? null);

  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    setChatId(initialChatId ?? null);
  }, [initialChatId]);

  useEffect(() => {
    const load = async () => {
      if (isLoading) {
        return;
      }

      if (!chatId) {
        setMessages([
          {
            content: openingMessage,
            id: "opening-assistant-message",
            role: "assistant",
          },
        ]);
        return;
      }

      try {
        const response = await fetch(
          `${API_BASE_URL}/chat/sessions/${chatId}/messages?actor_id=${encodeURIComponent(actorId)}&actor_role=${encodeURIComponent(actorRole)}`,
          { cache: "no-store" }
        );
        if (!response.ok) {
          throw new Error("Failed to load chat history.");
        }
        const payload = (await response.json()) as ChatMessageRecord[];
        const mapped = payload.map(toChatMessage);
        setMessages(mapped.length > 0 ? mapped : [{ content: openingMessage, id: "opening-assistant-message", role: "assistant" }]);
      } catch (errorValue) {
        const fallback = errorValue instanceof Error ? errorValue.message : "Failed to load chat history.";
        setError(fallback);
      }
    };

    void load();
  }, [actorId, actorRole, chatId, isLoading, openingMessage]);

  const appendAssistantMessage = useCallback(
    (content: string, attachment?: ChatAttachment, trace?: AgentTraceStep[]) => {
      setMessages((previous) => [
        ...previous,
        {
          attachment,
          content,
          id: createMessageId("assistant"),
          trace,
          role: "assistant",
        },
      ]);
    },
    []
  );

  const ensureChatSession = useCallback(async (preferredTitle: string): Promise<string> => {
    if (chatId) {
      return chatId;
    }

    const response = await fetch(`${API_BASE_URL}/chat/sessions`, {
      body: JSON.stringify({
        actor_id: actorId,
        actor_role: actorRole,
        patient_id: patientId ?? undefined,
        title: deriveChatTitle(preferredTitle),
      }),
      headers: { "Content-Type": "application/json" },
      method: "POST",
    });

    if (!response.ok) {
      let errorMessage = "Unable to create chat session.";
      try {
        const payload = (await response.json()) as { detail?: string };
        if (typeof payload.detail === "string" && payload.detail.trim()) {
          errorMessage = payload.detail.trim();
        }
      } catch {
        // keep default message
      }
      throw new Error(errorMessage);
    }

    const payload = (await response.json()) as ChatSessionCreateResponse;
    setChatId(payload.chat_id);
    return payload.chat_id;
  }, [actorId, actorRole, chatId, patientId]);

  const sendMessage = useCallback(
    async ({ text: rawText, attachment, attachmentMeta }: SendMessageInput) => {
      const text = rawText.trim();
      const hasAttachment = Boolean(attachment || attachmentMeta);

      if ((!text && !hasAttachment) || isLoading) {
        return;
      }

      const userMessage = text || (hasAttachment ? "Uploaded an attachment for analysis." : "");
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
      setLiveTrace([]);

      const currentChatId = await ensureChatSession(userMessage);
      const controller = new AbortController();
      abortRef.current = controller;
      const timeoutHandle = setTimeout(() => {
        controller.abort();
      }, CHAT_TIMEOUT_MS);

      const pollTrace = async () => {
        try {
          const traceResponse = await fetch(
            `${API_BASE_URL}/chat/sessions/${currentChatId}/trace?actor_id=${encodeURIComponent(actorId)}&actor_role=${encodeURIComponent(actorRole)}`,
            { cache: "no-store" }
          );
          if (!traceResponse.ok) {
            return;
          }
          const tracePayload = (await traceResponse.json()) as TraceApiResponse;
          if (Array.isArray(tracePayload.trace)) {
            setLiveTrace(tracePayload.trace);
          }
        } catch {
          // Ignore polling errors while main request is in-flight.
        }
      };

      const traceInterval = setInterval(() => {
        void pollTrace();
      }, 700);
      void pollTrace();

      try {
        const response = await fetch(`${API_BASE_URL}/chat/sessions/${currentChatId}/messages`, {
          body: JSON.stringify({
            actor_id: actorId,
            actor_name: actorName ?? undefined,
            actor_role: actorRole,
            attachment: attachment ?? undefined,
            message: text || "Please analyze the attached file.",
            patient_id: patientId ?? undefined,
            session_id: currentChatId,
          }),
          cache: "no-store",
          headers: { "Content-Type": "application/json" },
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
            // keep default
          }
          throw new Error(errorMessage);
        }

        const payload = (await response.json()) as ChatApiResponse;
        if (payload.chat_id) {
          setChatId(payload.chat_id);
        }

        const annotatedImage = typeof payload.annotated_image_base64 === "string" && payload.annotated_image_base64.trim()
          ? payload.annotated_image_base64.trim()
          : null;

        const assistantAttachment = annotatedImage
          ? {
              dataUrl: `data:image/png;base64,${annotatedImage}`,
              mediaType: "image/png",
              name: "Annotated X-ray",
            }
          : undefined;

        const trace = Array.isArray(payload.agent_trace)
          ? payload.agent_trace.filter((item) => typeof item === "object" && item !== null)
          : undefined;

        setLiveTrace([]);
        appendAssistantMessage(payload.final_response?.trim() || "No response generated.", assistantAttachment, trace);
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
        clearInterval(traceInterval);
        clearTimeout(timeoutHandle);
        if (abortRef.current === controller) {
          abortRef.current = null;
        }
        setLiveTrace([]);
        setIsLoading(false);
      }
    },
    [actorId, actorRole, appendAssistantMessage, ensureChatSession, isLoading, patientId]
  );

  const stop = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
  }, []);

  return useMemo(
    () => ({
      chatId,
      error,
      isLoading,
      liveTrace,
      messages,
      sendMessage,
      stop,
    }),
    [chatId, error, isLoading, liveTrace, messages, sendMessage, stop]
  );
}
