import { SignIn } from "@clerk/nextjs";

export default function SignInPage() {
  return (
    <main className="flex min-h-[calc(100vh-4rem)] items-center justify-center p-6">
      <SignIn
        forceRedirectUrl="/select-role"
        path="/sign-in"
        routing="path"
        signUpUrl="/sign-up"
      />
    </main>
  );
}
