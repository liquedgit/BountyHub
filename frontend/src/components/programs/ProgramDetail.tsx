"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { ScopeEditor } from "./ScopeEditor";

export function ProgramDetail({ programId }: { programId: number }) {
  const { data: program, isLoading, error } = useQuery({
    queryKey: ["program", programId],
    queryFn: () => api.programs.get(programId),
  });
  if (isLoading) return <p>Loading…</p>;
  if (error || !program) return <p role="alert">Program not found.</p>;
  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold">{program.name}</h1>
        <p className="text-sm opacity-70">
          {program.platform ?? "No platform"}
          {program.reward_info ? ` · ${program.reward_info}` : ""}
        </p>
        {program.url && (
          <a className="text-sm text-blue-500 underline" href={program.url}>
            {program.url}
          </a>
        )}
      </header>
      <ScopeEditor programId={programId} />
    </div>
  );
}
