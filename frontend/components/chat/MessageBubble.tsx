"use client";

import {
  Message,
  MessageContent,
} from "@/components/ai-elements/message";

export type ChatRole = "assistant" | "user";

type MessageBubbleProps = {
  content: string;
  role: ChatRole;
};

export function MessageBubble({ content, role }: MessageBubbleProps) {
  return (
    <Message from={role}>
      <MessageContent>
        <p className="m-0 whitespace-pre-wrap">{content}</p>
      </MessageContent>
    </Message>
  );
}
