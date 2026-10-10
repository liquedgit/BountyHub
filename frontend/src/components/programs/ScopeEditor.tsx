"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "@/lib/api";
import type { ScopeAction, ScopeType } from "@/lib/types";

const TYPES: ScopeType[] = ["domain", "wildcard", "ip", "url"];

export function ScopeEditor({ programId }: { programId: number }) {
  const qc = useQueryClient();
  const rules = api.scopeRules(programId);
  const key = ["scope-rules", programId];
  const { data = [], isLoading } = useQuery({ queryKey: key, queryFn: rules.list });
  const [action, setAction] = useState<ScopeAction>("in");
  const [type, setType] = useState<ScopeType>("wildcard");
  const [value, setValue] = useState("");

  const add = useMutation({
    mutationFn: () => rules.create({ action, type, value: value.trim() }),
    onSuccess: () => {
      setValue("");
      qc.invalidateQueries({ queryKey: key });
    },
  });
  const remove = useMutation({
    mutationFn: (id: number) => rules.remove(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: key }),
  });

  return (
    <section aria-label="Scope editor" className="space-y-3">
      <h2 className="text-lg font-semibold">Scope</h2>
      <form
        className="flex flex-wrap gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          if (value.trim()) add.mutate();
        }}
      >
        <select
          aria-label="Action"
          className="rounded border bg-transparent px-2 py-1"
          value={action}
          onChange={(e) => setAction(e.target.value as ScopeAction)}
        >
          <option value="in">In scope</option>
          <option value="out">Out of scope</option>
        </select>
        <select
          aria-label="Type"
          className="rounded border bg-transparent px-2 py-1"
          value={type}
          onChange={(e) => setType(e.target.value as ScopeType)}
        >
          {TYPES.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
        <input
          aria-label="Scope value"
          placeholder="*.example.com"
          className="rounded border bg-transparent px-2 py-1"
          value={value}
          onChange={(e) => setValue(e.target.value)}
        />
        <button className="rounded bg-blue-600 px-3 py-1 text-white" type="submit">
          Add rule
        </button>
      </form>
      {isLoading && <p>Loading…</p>}
      <ul className="divide-y rounded border">
        {data.map((r) => (
          <li key={r.id} className="flex items-center justify-between p-2">
            <span>
              <span
                className={r.action === "in" ? "text-green-500" : "text-red-500"}
                data-testid={`action-${r.id}`}
              >
                {r.action === "in" ? "IN" : "OUT"}
              </span>{" "}
              <span className="text-xs opacity-70">{r.type}</span> {r.value}
            </span>
            <button
              aria-label={`Delete ${r.value}`}
              className="text-sm text-red-500"
              onClick={() => remove.mutate(r.id)}
            >
              Remove
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
