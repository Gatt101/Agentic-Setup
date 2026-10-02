"use client";

import { useAuth } from "@clerk/nextjs";
import { Download } from "lucide-react";
import { useState } from "react";

type SecureReportDownloadProps = {
  className?: string;
  label?: string;
  reportUrl: string;
};

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api";

function resolveReportUrl(reportUrl: string): string {
  if (/^https?:\/\//.test(reportUrl)) return reportUrl;
  const origin = API_BASE_URL.replace(/\/api\/?$/, "");
  return `${origin}${reportUrl.startsWith("/") ? reportUrl : `/${reportUrl}`}`;
}

export function SecureReportDownload({
  className,
  label = "Download draft PDF",
  reportUrl,
}: SecureReportDownloadProps) {
  const { getToken } = useAuth();
  const [isLoading, setIsLoading] = useState(false);

  const download = async () => {
    setIsLoading(true);
    try {
      const token = await getToken();
      if (!token) throw new Error("Authentication required.");
      const response = await fetch(resolveReportUrl(reportUrl), {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) throw new Error("Unable to download report.");

      const objectUrl = URL.createObjectURL(await response.blob());
      const anchor = document.createElement("a");
      anchor.href = objectUrl;
      anchor.download = "orthoassist-draft-report.pdf";
      anchor.click();
      URL.revokeObjectURL(objectUrl);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <button
      className={className}
      disabled={isLoading}
      onClick={() => void download()}
      type="button"
    >
      <Download className="h-4 w-4 shrink-0" />
      {isLoading ? "Preparing..." : label}
    </button>
  );
}
