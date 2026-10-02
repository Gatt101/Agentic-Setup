import { auth } from "@clerk/nextjs/server";

export default async function SelectRolePage() {
  const { userId, redirectToSignIn } = await auth();

  if (!userId) {
    return redirectToSignIn();
  }

  return (
    <main className="mx-auto flex min-h-[70vh] max-w-xl items-center px-6">
      <div>
        <p className="text-sm font-semibold uppercase text-slate-500">Pilot access</p>
        <h1 className="mt-2 text-3xl font-semibold text-slate-900">
          Clinician access has not been provisioned
        </h1>
        <p className="mt-3 text-slate-600">
          OrthoAssist pilot accounts are assigned by the clinic administrator.
          Contact the pilot coordinator to enable the doctor workspace.
        </p>
      </div>
    </main>
  );
}

