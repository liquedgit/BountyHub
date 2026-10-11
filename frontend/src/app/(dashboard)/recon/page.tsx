"use client";

import { PageHeader } from "@/components/common/PageHeader";
import { ProgramScoped } from "@/components/ProgramScoped";
import { ReconDashboard } from "@/components/recon/ReconDashboard";

export default function ReconPage() {
  return (
    <div className="space-y-6">
      <PageHeader title="Recon" description="Launch scans, follow their progress and triage what they find." />
      <ProgramScoped render={(id) => <ReconDashboard programId={id} />} />
    </div>
  );
}
