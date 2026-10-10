"use client";

import { ProgramScoped } from "@/components/ProgramScoped";
import { ReconDashboard } from "@/components/recon/ReconDashboard";

export default function ReconPage() {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Recon</h1>
      <ProgramScoped render={(id) => <ReconDashboard programId={id} />} />
    </div>
  );
}
