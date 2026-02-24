"use client";

import {
  PromptInput,
  PromptInputActionAddAttachments,
  PromptInputActionMenu,
  PromptInputActionMenuContent,
  PromptInputActionMenuTrigger,
  PromptInputFooter,
  PromptInputHeader,
  PromptInputMessage,
  PromptInputSubmit,
  PromptInputTextarea,
  PromptInputTools,
  usePromptInputAttachments,
} from "@/components/ai-elements/prompt-input";
import { FileTextIcon, ImageIcon, PlusIcon, XIcon } from "lucide-react";

function ChatInputAttachments() {
  const attachments = usePromptInputAttachments();

  if (attachments.files.length === 0) {
    return null;
  }

  return (
    <PromptInputHeader className="gap-2 border-b border-slate-200 px-3 pb-2 pt-2 dark:border-slate-800/80">
      {attachments.files.map((file) => {
        const isImage = file.mediaType?.startsWith("image/");
        const name =
          typeof file.filename === "string" && file.filename.trim()
            ? file.filename
            : "Attachment";

        return (
          <div
            className="flex items-center gap-1 rounded-full border border-slate-300 bg-slate-50 px-2 py-1 text-xs text-slate-700 dark:border-slate-700 dark:bg-slate-900/80 dark:text-slate-200"
            key={file.id}
          >
            {isImage ? (
              <ImageIcon className="size-3.5" />
            ) : (
              <FileTextIcon className="size-3.5" />
            )}
            <span className="max-w-40 truncate">{name}</span>
            <button
              aria-label={`Remove ${name}`}
              className="rounded-full p-0.5 text-slate-500 transition-colors hover:bg-slate-200 hover:text-slate-700 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-slate-100"
              onClick={() => attachments.remove(file.id)}
              type="button"
            >
              <XIcon className="size-3.5" />
            </button>
          </div>
        );
      })}
    </PromptInputHeader>
  );
}

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
      className="rounded-xl border border-slate-200 bg-white/95 dark:border-slate-800 dark:bg-slate-950/70"
      maxFiles={4}
      multiple
      onSubmit={handleSubmit}
      syncHiddenInput={false}
    >
      <ChatInputAttachments />
      <PromptInputTextarea
        className="min-h-[130px] text-[15px] leading-relaxed text-slate-800 placeholder:text-slate-400 dark:text-slate-100 dark:placeholder:text-slate-500"
        disabled={disabled}
        placeholder={placeholder}
      />
      <PromptInputFooter className="border-slate-200 border-t pt-2 dark:border-slate-800/80">
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
