import { redirect } from "next/navigation";
import { RegisterForm } from "@/components/auth/register-form";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { fetchRegistrationOpen } from "@/lib/registration-status";

export const dynamic = "force-dynamic";

export default async function RegisterPage() {
  if ((await fetchRegistrationOpen()) === false) redirect("/login");

  return (
    <main className="flex min-h-screen items-center justify-center p-4">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>Welcome to BountyHub</CardTitle>
          <CardDescription>
            First-time setup: create the single account for this install.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <RegisterForm />
        </CardContent>
      </Card>
    </main>
  );
}
