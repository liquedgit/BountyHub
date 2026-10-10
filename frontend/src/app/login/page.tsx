import Link from "next/link";
import { redirect } from "next/navigation";
import { LoginForm } from "@/components/auth/login-form";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { fetchRegistrationOpen } from "@/lib/registration-status";

export const dynamic = "force-dynamic";

export default async function LoginPage({ searchParams }: { searchParams: { next?: string } }) {
  const registrationOpen = await fetchRegistrationOpen();
  if (registrationOpen === true) redirect("/register");

  return (
    <main className="flex min-h-screen items-center justify-center p-4">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>BountyHub</CardTitle>
          <CardDescription>Sign in to your workspace</CardDescription>
        </CardHeader>
        <CardContent>
          <LoginForm next={searchParams.next} />
          {registrationOpen === null && (
            <p className="mt-4 text-center text-sm text-muted-foreground">
              <Link href="/register" className="underline">
                Create account
              </Link>
            </p>
          )}
        </CardContent>
      </Card>
    </main>
  );
}
