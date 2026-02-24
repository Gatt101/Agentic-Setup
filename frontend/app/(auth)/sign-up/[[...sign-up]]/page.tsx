import { SignUp } from "@clerk/nextjs";

export default function SignUpPage() {
  return (
    <main className="flex min-h-[calc(100vh-4rem)] items-center justify-center p-6">
      <SignUp
        forceRedirectUrl="/select-role"
        path="/sign-up"
        routing="path"
        signInUrl="/sign-in"
      />
    </main>
  );
}
