"use client";

import { useState } from "react";
import { ProgramSelect } from "@/components/programs/ProgramSelect";

/** Page body helper: pick a program, then render the feature for it. */
export function ProgramScoped({
  render,
}: {
  render: (programId: number) => React.ReactNode;
}) {
  const [programId, setProgramId] = useState<number | null>(null);
  return (
    <div className="space-y-4">
      <ProgramSelect value={programId} onChange={setProgramId} />
      {programId == null ? <p className="opacity-70">Choose a program to continue.</p> : render(programId)}
    </div>
  );
}
