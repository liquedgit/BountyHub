"use client";

import { useQuery } from "@tanstack/react-query";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
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
    <div className="flex items-center gap-2">
      <Label htmlFor="program-select">Program</Label>
      <Select
        id="program-select"
        className="w-auto min-w-[12rem]"
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value ? Number(e.target.value) : null)}
      >
        <option value="">Select a program…</option>
        {programs.map((p) => (
          <option key={p.id} value={p.id}>
            {p.name}
          </option>
        ))}
      </Select>
    </div>
  );
}
