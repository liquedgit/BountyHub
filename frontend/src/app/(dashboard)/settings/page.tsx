"use client";

import { AccountCard } from "@/components/settings/AccountCard";
import { AISettingsForm } from "@/components/settings/AISettingsForm";
import { PageHeader } from "@/components/common/PageHeader";

export default function SettingsPage() {
  return (
    <div className="space-y-6">
      <PageHeader title="Settings" description="Configure the AI provider used for triage." />
      <AISettingsForm />
      <AccountCard />
    </div>
  );
}
