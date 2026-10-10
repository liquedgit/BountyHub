"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export function ProgramSelect({
  value,
  onChange,
}: {
  value: number | null;
  onChange: (id: number | null) => void;
}) {
  const { data: programs = [] } = useQuery({ queryKey: ["programs"], queryFn: api.programs.list });
  return (
    <label className="flex items-center gap-2 text-sm">
      Program
      <select
        aria-label="Program"
        className="rounded border bg-transparent px-2 py-1"
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value ? Number(e.target.value) : null)}
      >
        <option value="">Select a program…</option>
        {programs.map((p) => (
          <option key={p.id} value={p.id}>
            {p.name}
          </option>
        ))}
      </select>
    </label>
  );
}
