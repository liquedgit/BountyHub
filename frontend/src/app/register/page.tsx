import { redirect } from "next/navigation";
import { AuthCard } from "@/components/auth/auth-card";
import { RegisterForm } from "@/components/auth/register-form";
import { fetchRegistrationOpen } from "@/lib/registration-status";

export const dynamic = "force-dynamic";
export const metadata = { title: "Create account" };

export default async function RegisterPage() {
  if ((await fetchRegistrationOpen()) === false) redirect("/login");

  return (
    <AuthCard
      title="Welcome to BountyHub"
      description="First-time setup: create the single account for this install."
    >
      <RegisterForm />
    </AuthCard>
  );
}
