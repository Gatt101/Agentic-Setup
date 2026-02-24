"use client";

import { FileTextIcon, ImageIcon, PaperclipIcon } from "lucide-react";

import type { ChatAttachment } from "@/hooks/useChat";

type AttachmentPreviewProps = {
  attachment: ChatAttachment;
};

function isImageAttachment(attachment: ChatAttachment): boolean {
  if (attachment.mediaType?.startsWith("image/")) {
    return true;
  }
  return attachment.dataUrl?.startsWith("data:image/") ?? false;
}

export function AttachmentPreview({ attachment }: AttachmentPreviewProps) {
  const imageAttachment = isImageAttachment(attachment);
  const openableHref = attachment.dataUrl;

  return (
    <div className="mt-2 w-full max-w-sm rounded-lg border border-slate-200 bg-slate-50/70 p-2 dark:border-slate-700 dark:bg-slate-900/40">
      {imageAttachment && attachment.dataUrl ? (
        <img
          alt={attachment.name}
          className="max-h-[420px] w-full rounded-md bg-slate-950 object-contain"
          src={attachment.dataUrl}
        />
      ) : null}
      <div className="mt-2 flex items-center gap-2 text-xs text-slate-700 dark:text-slate-200">
        {imageAttachment ? (
          <ImageIcon className="size-4 shrink-0" />
        ) : attachment.mediaType?.includes("pdf") ||
          attachment.mediaType?.includes("word") ? (
          <FileTextIcon className="size-4 shrink-0" />
        ) : (
          <PaperclipIcon className="size-4 shrink-0" />
        )}
        <span className="line-clamp-1">{attachment.name}</span>
      </div>
      {!imageAttachment && openableHref ? (
        <a
          className="mt-1 inline-block text-xs font-medium text-slate-700 underline-offset-2 hover:underline dark:text-slate-200"
          href={openableHref}
          rel="noreferrer"
          target="_blank"
        >
          Open attachment
        </a>
      ) : null}
    </div>
  );
}
