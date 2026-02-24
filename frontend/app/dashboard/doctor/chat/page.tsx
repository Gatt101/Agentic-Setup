import { ChatWindow } from "@/components/chat/ChatWindow";

export default function DoctorChatPage() {
  return (
    <main className="space-y-4 p-6">
      <div>
        <h1 className="font-semibold text-2xl">Doctor Assistant</h1>
        <p className="text-muted-foreground text-sm">
          Review findings, triage, and report-ready outputs.
        </p>
      </div>
      <ChatWindow mode="doctor" />
    </main>
  );
}
