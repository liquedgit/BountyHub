import Link from "next/link";
import { redirect } from "next/navigation";
import { AuthCard } from "@/components/auth/auth-card";
import { LoginForm } from "@/components/auth/login-form";
import { fetchRegistrationOpen } from "@/lib/registration-status";

export const dynamic = "force-dynamic";
export const metadata = { title: "Sign in" };

export default async function LoginPage({ searchParams }: { searchParams: { next?: string } }) {
  const registrationOpen = await fetchRegistrationOpen();
  if (registrationOpen === true) redirect("/register");

  return (
    <AuthCard title="Sign in" description="Sign in to your workspace">
      <LoginForm next={searchParams.next} />
      {registrationOpen === null && (
        <p className="mt-4 text-center text-sm text-muted-foreground">
          <Link href="/register" className="underline">
            Create account
          </Link>
        </p>
      )}
    </AuthCard>
  );
}
