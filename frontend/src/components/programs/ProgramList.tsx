"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { api } from "@/lib/api";

export function ProgramList() {
  const qc = useQueryClient();
  const { data, isLoading, error } = useQuery({ queryKey: ["programs"], queryFn: api.programs.list });
  const [name, setName] = useState("");
  const [platform, setPlatform] = useState("");
  const create = useMutation({
    mutationFn: () => api.programs.create({ name, platform: platform || null }),
    onSuccess: () => {
      setName("");
      setPlatform("");
      qc.invalidateQueries({ queryKey: ["programs"] });
    },
  });

  return (
    <section className="space-y-4">
      <form
        className="flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          if (name.trim()) create.mutate();
        }}
      >
        <input
          aria-label="Program name"
          placeholder="Program name"
          className="rounded border bg-transparent px-2 py-1"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <input
          aria-label="Platform"
          placeholder="Platform (HackerOne…)"
          className="rounded border bg-transparent px-2 py-1"
          value={platform}
          onChange={(e) => setPlatform(e.target.value)}
        />
        <button className="rounded bg-blue-600 px-3 py-1 text-white" type="submit">
          Add program
        </button>
      </form>
      {isLoading && <p>Loading…</p>}
      {error && <p role="alert">Failed to load programs.</p>}
      {data && data.length === 0 && <p>No programs yet.</p>}
      <ul className="divide-y rounded border">
        {data?.map((p) => (
          <li key={p.id} className="flex justify-between p-3">
            <Link href={`/programs/${p.id}`} className="font-medium hover:underline">
              {p.name}
            </Link>
            <span className="text-sm opacity-70">{p.platform ?? "—"}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
