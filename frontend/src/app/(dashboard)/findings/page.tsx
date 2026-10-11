"use client";

import { PageHeader } from "@/components/common/PageHeader";
import { FindingsBoard } from "@/components/findings/FindingsBoard";
import { ProgramScoped } from "@/components/ProgramScoped";

export default function FindingsPage() {
  return (
    <div className="space-y-6">
      <PageHeader title="Findings" description="Track vulnerabilities by status, severity and payout." />
      <ProgramScoped render={(id) => <FindingsBoard programId={id} />} />
    </div>
  );
}
