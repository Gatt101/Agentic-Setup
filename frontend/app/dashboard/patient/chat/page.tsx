import { ChatWindow } from "@/components/chat/ChatWindow";

export default function PatientChatPage() {
  return (
    <main className="mx-auto w-full max-w-[1400px] space-y-5 p-6">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight text-slate-900 dark:text-slate-100">
          Patient Assistant
        </h1>
        <p className="mt-1 text-sm font-medium text-slate-600 dark:text-slate-300">
          Ask questions in plain language and get practical next steps.
        </p>
      </div>
      <ChatWindow mode="patient" />
    </main>
  );
}
