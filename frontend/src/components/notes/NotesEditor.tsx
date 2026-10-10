"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import { api } from "@/lib/api";

export function NotesEditor({ programId }: { programId: number }) {
  const qc = useQueryClient();
  const svc = api.notes(programId);
  const key = ["notes", programId];
  const { data: notes = [] } = useQuery({ queryKey: key, queryFn: svc.list });
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");

  const selected = notes.find((n) => n.id === selectedId) ?? null;
  useEffect(() => {
    setTitle(selected?.title ?? "");
    setBody(selected?.body_md ?? "");
  }, [selected?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const invalidate = () => qc.invalidateQueries({ queryKey: key });
  const create = useMutation({
    mutationFn: () => svc.create({ title: "Untitled note", body_md: "" }),
    onSuccess: (n) => {
      setSelectedId(n.id);
      invalidate();
    },
  });
  const save = useMutation({
    mutationFn: () => svc.update(selectedId!, { title, body_md: body }),
    onSuccess: invalidate,
  });
  const remove = useMutation({
    mutationFn: () => svc.remove(selectedId!),
    onSuccess: () => {
      setSelectedId(null);
      invalidate();
    },
  });

  return (
    <div className="grid gap-4 md:grid-cols-[14rem_1fr]">
      <aside className="space-y-2">
        <button className="rounded bg-blue-600 px-3 py-1 text-white" onClick={() => create.mutate()}>
          New note
        </button>
        <ul className="divide-y rounded border">
          {notes.map((n) => (
            <li key={n.id}>
              <button
                className={`w-full p-2 text-left ${n.id === selectedId ? "font-semibold" : ""}`}
                onClick={() => setSelectedId(n.id)}
              >
                {n.title}
              </button>
            </li>
          ))}
        </ul>
      </aside>
      {selected ? (
        <section className="space-y-2">
          <input
            aria-label="Note title"
            className="w-full rounded border bg-transparent px-2 py-1"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
          <div className="grid gap-2 md:grid-cols-2">
            <textarea
              aria-label="Markdown"
              className="min-h-64 rounded border bg-transparent p-2 font-mono text-sm"
              value={body}
              onChange={(e) => setBody(e.target.value)}
            />
            <div aria-label="Preview" className="min-h-64 rounded border p-2">
              <ReactMarkdown>{body}</ReactMarkdown>
            </div>
          </div>
          <div className="flex gap-2">
            <button className="rounded bg-blue-600 px-3 py-1 text-white" onClick={() => save.mutate()}>
              Save
            </button>
            <button className="rounded border px-3 py-1 text-red-500" onClick={() => remove.mutate()}>
              Delete
            </button>
          </div>
        </section>
      ) : (
        <p className="opacity-70">Select or create a note.</p>
      )}
    </div>
  );
}
