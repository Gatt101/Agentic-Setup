import { auth } from "@clerk/nextjs/server";

import { RoleSelectionScreen } from "@/components/auth/RoleSelectionScreen";

export default async function SelectRolePage() {
  const { userId, redirectToSignIn } = await auth();

  if (!userId) {
    return redirectToSignIn();
  }

  return <RoleSelectionScreen />;
}

