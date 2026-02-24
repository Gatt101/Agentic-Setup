import { auth } from "@clerk/nextjs/server";
import { ChatWindow } from "@/components/chat/ChatWindow";

export default async function DoctorChatPage() {
  const { userId, redirectToSignIn } = await auth();
  if (!userId) {
    return redirectToSignIn();
  }

  return (
    <main className="mx-auto w-full max-w-[1400px] space-y-5 p-6">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight text-slate-900 dark:text-slate-100">
          Doctor Assistant
        </h1>
        <p className="mt-1 text-sm font-medium text-slate-600 dark:text-slate-300">
          Review findings, triage, and report-ready outputs.
        </p>
      </div>
      <ChatWindow actorId={userId} mode="doctor" />
    </main>
  );
}
