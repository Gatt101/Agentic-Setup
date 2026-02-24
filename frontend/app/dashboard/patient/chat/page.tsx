import { ChatWindow } from "@/components/chat/ChatWindow";

export default function PatientChatPage() {
  return (
    <main className="space-y-4 p-6">
      <div>
        <h1 className="font-semibold text-2xl">Patient Assistant</h1>
        <p className="text-muted-foreground text-sm">
          Ask questions in plain language and get practical next steps.
        </p>
      </div>
      <ChatWindow mode="patient" />
    </main>
  );
}
