"use client";

import {
  PromptInput,
  PromptInputActionAddAttachments,
  PromptInputActionMenu,
  PromptInputActionMenuContent,
  PromptInputActionMenuTrigger,
  PromptInputFooter,
  PromptInputMessage,
  PromptInputSubmit,
  PromptInputTextarea,
  PromptInputTools,
} from "@/components/ai-elements/prompt-input";
import { PlusIcon } from "lucide-react";

type ChatInputProps = {
  disabled?: boolean;
  isSubmitting?: boolean;
  onSend: (message: PromptInputMessage) => void;
  onStop?: () => void;
  placeholder?: string;
};

export function ChatInput({
  disabled = false,
  isSubmitting = false,
  onSend,
  onStop,
  placeholder = "Ask about the X-ray, triage, or next steps...",
}: ChatInputProps) {
  const handleSubmit = (message: PromptInputMessage) => {
    const trimmed = message.text.trim();
    const hasFiles = message.files.length > 0;

    if (!trimmed && !hasFiles) {
      return;
    }

    onSend({
      ...message,
      text: trimmed,
    });
  };

  return (
    <PromptInput
      accept="image/*,.pdf,.doc,.docx"
      maxFiles={4}
      multiple
      onSubmit={handleSubmit}
      syncHiddenInput={false}
    >
      <PromptInputTextarea disabled={disabled} placeholder={placeholder} />
      <PromptInputFooter>
        <PromptInputTools>
          <PromptInputActionMenu>
            <PromptInputActionMenuTrigger
              disabled={disabled}
              tooltip="Add attachment"
            >
              <PlusIcon className="size-4" />
            </PromptInputActionMenuTrigger>
            <PromptInputActionMenuContent>
              <PromptInputActionAddAttachments />
            </PromptInputActionMenuContent>
          </PromptInputActionMenu>
        </PromptInputTools>
        <PromptInputSubmit
          disabled={disabled && !isSubmitting}
          onStop={onStop}
          status={isSubmitting ? "submitted" : "ready"}
        />
      </PromptInputFooter>
    </PromptInput>
  );
}
