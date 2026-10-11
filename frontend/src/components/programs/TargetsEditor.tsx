"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { ListSkeleton } from "@/components/common/ListSkeleton";
import { Button } from "@/components/ui/button";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { api, errorMessage } from "@/lib/api";
import type { Target } from "@/lib/types";

export function TargetsEditor({ programId }: { programId: number }) {
  const qc = useQueryClient();
  const targets = api.targets(programId);
  const key = ["targets", programId];
  const { data = [], isLoading, error, refetch } = useQuery({ queryKey: key, queryFn: targets.list });
  // `null` = closed, `"new"` = create dialog, a Target = edit dialog
  const [editing, setEditing] = useState<Target | "new" | null>(null);
  const [toDelete, setToDelete] = useState<Target | null>(null);
  const [value, setValue] = useState("");
  const [description, setDescription] = useState("");

  useEffect(() => {
    if (editing === null) return;
    setValue(editing === "new" ? "" : editing.value);
    setDescription(editing === "new" ? "" : editing.description ?? "");
  }, [editing]);

  const save = useMutation({
    meta: { silent: true },
    mutationFn: () => {
      const body = { value: value.trim(), description: description.trim() || null };
      return editing && editing !== "new"
        ? targets.update(editing.id, body)
        : targets.create(body);
    },
    onSuccess: () => {
      setEditing(null);
      qc.invalidateQueries({ queryKey: key });
    },
  });
  const remove = useMutation({
    mutationFn: (id: number) => targets.remove(id),
    onSuccess: () => {
      setToDelete(null);
      qc.invalidateQueries({ queryKey: key });
    },
  });

  const openEditor = (t: Target | "new") => {
    save.reset();
    setEditing(t);
  };

  return (
    <section aria-label="Targets" className="space-y-4 pt-4">
      <div className="flex items-center justify-between gap-2">
        <p className="text-sm text-muted-foreground">Concrete assets you plan to test.</p>
        <Button onClick={() => openEditor("new")}>
          <Plus className="h-4 w-4" aria-hidden /> Add target
        </Button>
      </div>

      {isLoading ? (
        <ListSkeleton rows={3} />
      ) : error ? (
        <ErrorState error={error} title="Failed to load targets" onRetry={() => refetch()} />
      ) : data.length === 0 ? (
        <EmptyState
          title="No targets yet"
          description="Add the hosts, apps or endpoints you want to test."
          action={{ label: "Add target", onClick: () => openEditor("new") }}
        />
      ) : (
        <div className="overflow-x-auto rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Value</TableHead>
                <TableHead>Description</TableHead>
                <TableHead className="w-24 text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.map((t) => (
                <TableRow key={t.id}>
                  <TableCell className="break-all font-medium">{t.value}</TableCell>
                  <TableCell className="text-muted-foreground">{t.description ?? "—"}</TableCell>
                  <TableCell className="text-right">
                    <Button
                      variant="ghost"
                      size="icon"
                      aria-label={`Edit target ${t.value}`}
                      onClick={() => openEditor(t)}
                    >
                      <Pencil className="h-4 w-4" aria-hidden />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      aria-label={`Delete target ${t.value}`}
                      onClick={() => setToDelete(t)}
                    >
                      <Trash2 className="h-4 w-4" aria-hidden />
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      <Dialog open={editing !== null} onOpenChange={(o) => !o && setEditing(null)}>
        <DialogContent>
          <form
            className="grid gap-4"
            onSubmit={(e) => {
              e.preventDefault();
              if (value.trim()) save.mutate();
            }}
          >
            <DialogHeader>
              <DialogTitle>{editing === "new" ? "Add target" : "Edit target"}</DialogTitle>
              <DialogDescription>A host, URL or other asset to test.</DialogDescription>
            </DialogHeader>
            <div className="grid gap-2">
              <Label htmlFor="target-value">Target value</Label>
              <Input
                id="target-value"
                value={value}
                onChange={(e) => setValue(e.target.value)}
                placeholder="app.example.com"
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="target-description">Description</Label>
              <Input
                id="target-description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Main web app"
              />
            </div>
            {save.error ? (
              <p role="alert" className="text-sm text-destructive">
                {errorMessage(save.error)}
              </p>
            ) : null}
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setEditing(null)} disabled={save.isPending}>
                Cancel
              </Button>
              <Button type="submit" disabled={save.isPending || !value.trim()}>
                {save.isPending ? "Saving…" : editing === "new" ? "Add" : "Save target"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={!!toDelete}
        onOpenChange={(o) => !o && setToDelete(null)}
        title="Delete target?"
        description={toDelete ? `“${toDelete.value}” will be removed.` : undefined}
        confirmLabel={remove.isPending ? "Deleting…" : "Delete target"}
        destructive
        pending={remove.isPending}
        onConfirm={() => toDelete && remove.mutate(toDelete.id)}
      />
    </section>
  );
}
