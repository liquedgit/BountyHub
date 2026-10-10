"use client";

import { FindingsBoard } from "@/components/findings/FindingsBoard";
import { ProgramScoped } from "@/components/ProgramScoped";

export default function FindingsPage() {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Findings</h1>
      <ProgramScoped render={(id) => <FindingsBoard programId={id} />} />
    </div>
  );
}
