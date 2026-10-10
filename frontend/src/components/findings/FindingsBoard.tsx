"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "@/lib/api";
import {
  FINDING_STATUSES, SEVERITIES, type Finding, type FindingStatus, type Severity,
} from "@/lib/types";

export function formatPayout(cents: number | null): string {
  return cents == null ? "—" : `$${(cents / 100).toFixed(2)}`;
}

export function FindingsBoard({ programId }: { programId: number }) {
  const qc = useQueryClient();
  const svc = api.findings(programId);
  const key = ["findings", programId];
  const { data = [], isLoading } = useQuery({ queryKey: key, queryFn: svc.list });
  const [title, setTitle] = useState("");
  const [severity, setSeverity] = useState<Severity>("info");

  const invalidate = () => qc.invalidateQueries({ queryKey: key });
  const create = useMutation({
    mutationFn: () => svc.create({ title: title.trim(), severity }),
    onSuccess: () => {
      setTitle("");
      invalidate();
    },
  });
  const update = useMutation({
    mutationFn: ({ id, patch }: { id: number; patch: Partial<Finding> }) => svc.update(id, patch),
    onSuccess: invalidate,
  });

  return (
    <section className="space-y-4">
      <form
        className="flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          if (title.trim()) create.mutate();
        }}
      >
        <input
          aria-label="Finding title"
          placeholder="Finding title"
          className="rounded border bg-transparent px-2 py-1"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
        />
        <select
          aria-label="New finding severity"
          className="rounded border bg-transparent px-2 py-1"
          value={severity}
          onChange={(e) => setSeverity(e.target.value as Severity)}
        >
          {SEVERITIES.map((s) => (
            <option key={s}>{s}</option>
          ))}
        </select>
        <button className="rounded bg-blue-600 px-3 py-1 text-white" type="submit">
          Add finding
        </button>
      </form>
      {isLoading && <p>Loading…</p>}
      <div className="grid gap-3 md:grid-cols-4">
        {FINDING_STATUSES.map((status) => {
          const items = data.filter((f) => f.status === status);
          return (
            <div key={status} aria-label={`Column ${status}`} className="rounded border p-2">
              <h3 className="mb-2 text-sm font-semibold uppercase">
                {status} ({items.length})
              </h3>
              <ul className="space-y-2">
                {items.map((f) => (
                  <li key={f.id} className="rounded border p-2 text-sm">
                    <div className="font-medium">{f.title}</div>
                    <div className="flex items-center justify-between opacity-80">
                      <span>{f.severity}</span>
                      <span>{formatPayout(f.payout_cents)}</span>
                    </div>
                    <select
                      aria-label={`Status for ${f.title}`}
                      className="mt-1 w-full rounded border bg-transparent px-1"
                      value={f.status}
                      onChange={(e) =>
                        update.mutate({ id: f.id, patch: { status: e.target.value as FindingStatus } })
                      }
                    >
                      {FINDING_STATUSES.map((s) => (
                        <option key={s}>{s}</option>
                      ))}
                    </select>
                    <input
                      aria-label={`Payout for ${f.title}`}
                      type="number"
                      min={0}
                      step="0.01"
                      placeholder="Payout $"
                      className="mt-1 w-full rounded border bg-transparent px-1"
                      defaultValue={f.payout_cents != null ? f.payout_cents / 100 : ""}
                      onBlur={(e) => {
                        const v = e.target.value;
                        const cents = v === "" ? null : Math.round(Number(v) * 100);
                        if (cents !== f.payout_cents)
                          update.mutate({ id: f.id, patch: { payout_cents: cents } });
                      }}
                    />
                  </li>
                ))}
              </ul>
            </div>
          );
        })}
      </div>
    </section>
  );
}
