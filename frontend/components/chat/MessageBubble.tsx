"use client";

import {
  Message,
  MessageContent,
} from "@/components/ai-elements/message";
import type { ChatAttachment } from "@/hooks/useChat";

import { AttachmentPreview } from "./AttachmentPreview";

export type ChatRole = "assistant" | "user";

type MessageBubbleProps = {
  attachment?: ChatAttachment;
  content: string;
  role: ChatRole;
};

export function MessageBubble({ attachment, content, role }: MessageBubbleProps) {
  return (
    <Message from={role}>
      <MessageContent>
        {content ? <p className="m-0 whitespace-pre-wrap">{content}</p> : null}
        {attachment ? <AttachmentPreview attachment={attachment} /> : null}
      </MessageContent>
    </Message>
  );
}
