"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { ListSkeleton } from "@/components/common/ListSkeleton";
import { Markdown } from "@/components/common/Markdown";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { api, errorMessage } from "@/lib/api";
import { formatRelative } from "@/lib/format";
import type { Note } from "@/lib/types";

interface Draft {
  title: string;
  body: string;
  findingId: number | null;
}

const toDraft = (n: Note): Draft => ({ title: n.title, body: n.body_md, findingId: n.finding_id });

export function NotesEditor({ programId }: { programId: number }) {
  const qc = useQueryClient();
  const svc = api.notes(programId);
  const key = ["notes", programId];
  const { data: notes = [], isLoading, error, refetch } = useQuery({ queryKey: key, queryFn: svc.list });
  const { data: findings = [] } = useQuery({
    queryKey: ["findings", programId],
    queryFn: api.findings(programId).list,
  });

  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [draft, setDraft] = useState<Draft>({ title: "", body: "", findingId: null });
  const [search, setSearch] = useState("");
  const [tab, setTab] = useState<"edit" | "preview">("edit");
  const [pendingSwitch, setPendingSwitch] = useState<{ id: number | "new" } | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const selected = notes.find((n) => n.id === selectedId) ?? null;
  const dirty =
    selected != null &&
    (draft.title !== selected.title ||
      draft.body !== selected.body_md ||
      draft.findingId !== selected.finding_id);

  const open = useCallback((n: Note) => {
    setSelectedId(n.id);
    setDraft(toDraft(n));
    setTab("edit");
  }, []);

  const invalidate = () => qc.invalidateQueries({ queryKey: key });
  const create = useMutation({
    mutationFn: () => svc.create({ title: "Untitled note", body_md: "" }),
    onSuccess: (n) => {
      toast.success("Note created");
      if (n && typeof n.id === "number") open({ ...n, body_md: n.body_md ?? "" });
      invalidate();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const save = useMutation({
    mutationFn: () => {
      const patch: { title: string; body_md: string; finding_id?: number | null } = {
        title: draft.title,
        body_md: draft.body,
      };
      if (selected && draft.findingId !== selected.finding_id) patch.finding_id = draft.findingId;
      return svc.update(selectedId!, patch);
    },
    onSuccess: (updated) => {
      toast.success("Note saved");
      if (updated && typeof updated.id === "number") {
        qc.setQueryData<Note[]>(key, (old) => old?.map((n) => (n.id === updated.id ? updated : n)));
      }
      invalidate();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const remove = useMutation({
    mutationFn: () => svc.remove(selectedId!),
    onSuccess: () => {
      toast.success("Note deleted");
      setConfirmDelete(false);
      setSelectedId(null);
      invalidate();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  const canSave = dirty && draft.title.trim() !== "" && !save.isPending;
  const { mutate: doSave } = save;
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") {
        e.preventDefault();
        if (canSave) doSave();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [canSave, doSave]);

  useEffect(() => {
    if (!dirty) return;
    const onUnload = (e: BeforeUnloadEvent) => e.preventDefault();
    window.addEventListener("beforeunload", onUnload);
    return () => window.removeEventListener("beforeunload", onUnload);
  }, [dirty]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return notes;
    return notes.filter((n) => n.title.toLowerCase().includes(q) || n.body_md.toLowerCase().includes(q));
  }, [notes, search]);

  const go = (target: { id: number | "new" }) => {
    if (dirty) {
      setPendingSwitch(target);
      return;
    }
    perform(target);
  };
  const perform = (target: { id: number | "new" }) => {
    if (target.id === "new") create.mutate();
    else {
      const n = notes.find((x) => x.id === target.id);
      if (n) open(n);
    }
  };

  if (isLoading) return <ListSkeleton rows={5} />;
  if (error) return <ErrorState error={error} title="Could not load notes" onRetry={() => refetch()} />;

  if (notes.length === 0 && selected == null) {
    return (
      <EmptyState
        title="No notes yet"
        description="Keep markdown notes for this program, optionally linked to a finding."
        action={{ label: create.isPending ? "Creating…" : "New note", onClick: () => create.mutate() }}
      />
    );
  }

  return (
    <div className="grid gap-4 md:grid-cols-[16rem_1fr]">
      <aside className="space-y-2">
        <Button className="w-full" onClick={() => go({ id: "new" })} disabled={create.isPending}>
          <Plus className="mr-1 h-4 w-4" aria-hidden /> {create.isPending ? "Creating…" : "New note"}
        </Button>
        <Input
          aria-label="Search notes"
          placeholder="Search notes"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        {filtered.length === 0 ? (
          <p className="p-2 text-sm text-muted-foreground">No notes match “{search}”.</p>
        ) : (
          <ul className="divide-y rounded-md border">
            {filtered.map((n) => (
              <li key={n.id}>
                <button
                  type="button"
                  aria-current={n.id === selectedId ? "true" : undefined}
                  className={`w-full p-2 text-left text-sm hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
                    n.id === selectedId ? "bg-muted font-semibold" : ""
                  }`}
                  onClick={() => n.id !== selectedId && go({ id: n.id })}
                >
                  <span className="block truncate">{n.title}</span>
                  <span className="block text-xs font-normal text-muted-foreground">
                    {formatRelative(n.updated_at)}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </aside>

      {selected ? (
        <section className="min-w-0 space-y-3">
          <div className="flex flex-wrap items-end gap-3">
            <div className="min-w-48 flex-1 space-y-1.5">
              <Label htmlFor="note-title">Title</Label>
              <Input
                id="note-title"
                aria-label="Note title"
                value={draft.title}
                onChange={(e) => setDraft({ ...draft, title: e.target.value })}
              />
            </div>
            <div className="w-full space-y-1.5 sm:w-56">
              <Label htmlFor="note-finding">Linked finding</Label>
              <Select
                id="note-finding"
                value={draft.findingId ?? ""}
                onChange={(e) =>
                  setDraft({ ...draft, findingId: e.target.value ? Number(e.target.value) : null })
                }
              >
                <option value="">No finding</option>
                {findings.map((f) => (
                  <option key={f.id} value={f.id}>{f.title}</option>
                ))}
              </Select>
            </div>
          </div>

          <Tabs value={tab} onValueChange={(v) => setTab(v as "edit" | "preview")} className="lg:hidden">
            <TabsList>
              <TabsTrigger value="edit">Edit</TabsTrigger>
              <TabsTrigger value="preview">Preview</TabsTrigger>
            </TabsList>
          </Tabs>

          <div className="grid gap-3 lg:grid-cols-2">
            <div className={tab === "edit" ? "" : "hidden lg:block"}>
              <Textarea
                aria-label="Markdown"
                className="min-h-72 font-mono"
                value={draft.body}
                onChange={(e) => setDraft({ ...draft, body: e.target.value })}
              />
            </div>
            <div
              aria-label="Preview"
              className={`min-h-72 rounded-md border p-3 ${tab === "preview" ? "" : "hidden lg:block"}`}
            >
              {draft.body.trim() ? (
                <Markdown>{draft.body}</Markdown>
              ) : (
                <p className="text-sm text-muted-foreground">Nothing to preview yet.</p>
              )}
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Button onClick={() => save.mutate()} disabled={!canSave}>
              {save.isPending ? "Saving…" : "Save"}
            </Button>
            <Button variant="destructive" onClick={() => setConfirmDelete(true)}>
              Delete
            </Button>
            <span className="text-sm text-muted-foreground" aria-live="polite">
              {dirty ? "Unsaved changes" : "All changes saved"}
            </span>
            {save.error ? (
              <span role="alert" className="text-sm text-destructive">{errorMessage(save.error)}</span>
            ) : null}
          </div>
        </section>
      ) : (
        <p className="text-sm text-muted-foreground">Select or create a note.</p>
      )}

      <ConfirmDialog
        open={pendingSwitch != null}
        onOpenChange={(o) => !o && setPendingSwitch(null)}
        title="Discard unsaved changes?"
        description="This note has changes that have not been saved. Switching away will lose them."
        confirmLabel="Discard changes"
        destructive
        onConfirm={() => {
          const t = pendingSwitch;
          setPendingSwitch(null);
          if (t) perform(t);
        }}
      />
      <ConfirmDialog
        open={confirmDelete}
        onOpenChange={setConfirmDelete}
        title="Delete note?"
        description={selected ? `“${selected.title}” will be permanently deleted.` : undefined}
        confirmLabel="Delete note"
        destructive
        pending={remove.isPending}
        onConfirm={() => remove.mutate()}
      />
    </div>
  );
}
