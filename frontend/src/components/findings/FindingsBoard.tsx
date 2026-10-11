"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { SeverityBadge } from "@/components/common/SeverityBadge";
import { StatCard } from "@/components/common/StatCard";
import { Button } from "@/components/ui/button";
import {
  Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { api, errorMessage } from "@/lib/api";
import { formatMoney, formatRelative } from "@/lib/format";
import {
  FINDING_STATUSES, SEVERITIES, type Finding, type FindingStatus, type Severity,
} from "@/lib/types";
import { FindingForm, type FindingValues } from "./FindingForm";

const CLOSED: FindingStatus[] = ["duplicate", "rejected", "resolved", "paid"];

export function formatPayout(cents: number | null): string {
  return formatMoney(cents);
}

export function FindingsBoard({ programId }: { programId: number }) {
  const qc = useQueryClient();
  const svc = api.findings(programId);
  const key = ["findings", programId];
  const { data = [], isLoading, error, refetch } = useQuery({ queryKey: key, queryFn: svc.list });
  const { data: targets = [] } = useQuery({
    queryKey: ["targets", programId],
    queryFn: api.targets(programId).list,
  });

  const [severityFilter, setSeverityFilter] = useState<Severity | "all">("all");
  const [creating, setCreating] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const invalidate = () => qc.invalidateQueries({ queryKey: key });
  const create = useMutation({
    mutationFn: (v: FindingValues) => svc.create(v),
    onSuccess: () => {
      setCreating(false);
      toast.success("Finding created");
      invalidate();
    },
  });
  const update = useMutation({
    mutationFn: ({ id, patch }: { id: number; patch: Partial<Finding> }) => svc.update(id, patch),
    onSuccess: () => invalidate(),
    onError: (e) => toast.error(errorMessage(e)),
  });
  const save = useMutation({
    mutationFn: ({ id, v }: { id: number; v: FindingValues }) => svc.update(id, v),
    onSuccess: () => {
      setEditingId(null);
      toast.success("Finding saved");
      invalidate();
    },
  });
  const remove = useMutation({
    mutationFn: (id: number) => svc.remove(id),
    onSuccess: () => {
      setConfirmDelete(false);
      setEditingId(null);
      toast.success("Finding deleted");
      invalidate();
    },
  });

  if (isLoading) {
    return (
      <div className="space-y-4" aria-busy="true" aria-label="Loading findings">
        <Skeleton className="h-20 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }
  if (error) return <ErrorState error={error} title="Could not load findings" onRetry={() => refetch()} />;

  const editing = data.find((f) => f.id === editingId) ?? null;
  const visible = severityFilter === "all" ? data : data.filter((f) => f.severity === severityFilter);
  const open = data.filter((f) => !CLOSED.includes(f.status)).length;
  const paidTotal = data
    .filter((f) => f.status === "paid")
    .reduce((sum, f) => sum + (f.payout_cents ?? 0), 0);

  return (
    <section className="space-y-4">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <StatCard label="Findings" value={data.length} />
        <StatCard label="Open" value={open} />
        <StatCard label="Paid total" value={formatMoney(paidTotal)} />
      </div>

      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="w-44 space-y-1.5">
          <Label htmlFor="severity-filter">Show severity</Label>
          <Select
            id="severity-filter"
            aria-label="Filter by severity"
            value={severityFilter}
            onChange={(e) => setSeverityFilter(e.target.value as Severity | "all")}
          >
            <option value="all">All severities</option>
            {SEVERITIES.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </Select>
        </div>
        {data.length > 0 ? (
          <Button onClick={() => setCreating(true)}>
            <Plus className="mr-1 h-4 w-4" aria-hidden /> New finding
          </Button>
        ) : null}
      </div>

      {data.length === 0 ? (
        <EmptyState
          title="No findings yet"
          description="Record a vulnerability you found in this program to track its status and payout."
          action={{ label: "New finding", onClick: () => setCreating(true) }}
        />
      ) : (
        <div className="flex gap-3 overflow-x-auto pb-2">
          {FINDING_STATUSES.map((status) => {
            const items = visible.filter((f) => f.status === status);
            return (
              <div
                key={status}
                aria-label={`Column ${status}`}
                className="w-64 shrink-0 rounded-lg border bg-muted/30 p-2"
              >
                <h3 className="mb-2 px-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  {status} ({items.length})
                </h3>
                <ul className="space-y-2">
                  {items.map((f) => (
                    <li key={f.id} className="rounded-md border bg-card p-3 text-sm">
                      <Button
                        type="button"
                        variant="ghost"
                        className="block h-auto w-full whitespace-normal p-0 text-left font-medium hover:bg-transparent hover:underline"
                        onClick={() => setEditingId(f.id)}
                      >
                        {f.title}
                      </Button>
                      <div className="mt-2 flex items-center justify-between gap-2">
                        <SeverityBadge severity={f.severity} />
                        <span className="tabular-nums">{formatMoney(f.payout_cents)}</span>
                      </div>
                      <div className="mt-1 text-xs text-muted-foreground">
                        Updated {formatRelative(f.updated_at)}
                      </div>
                      <Select
                        aria-label={`Status for ${f.title}`}
                        className="mt-2 h-8 text-xs"
                        value={f.status}
                        disabled={update.isPending && update.variables?.id === f.id}
                        onChange={(e) =>
                          update.mutate({ id: f.id, patch: { status: e.target.value as FindingStatus } })
                        }
                      >
                        {FINDING_STATUSES.map((s) => (
                          <option key={s} value={s}>{s}</option>
                        ))}
                      </Select>
                    </li>
                  ))}
                </ul>
              </div>
            );
          })}
        </div>
      )}

      <Dialog
        open={creating}
        onOpenChange={(o) => {
          setCreating(o);
          if (!o) create.reset();
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>New finding</DialogTitle>
            <DialogDescription>Add a finding to this program.</DialogDescription>
          </DialogHeader>
          <FindingForm
            targets={targets}
            pending={create.isPending}
            error={create.error ? errorMessage(create.error) : null}
            submitLabel="Create finding"
            onSubmit={(v) => create.mutate(v)}
          />
        </DialogContent>
      </Dialog>

      <Dialog
        open={editing != null}
        onOpenChange={(o) => {
          if (!o) {
            setEditingId(null);
            save.reset();
            remove.reset();
          }
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit finding</DialogTitle>
            <DialogDescription>Update the details, or delete this finding.</DialogDescription>
          </DialogHeader>
          {editing ? (
            <FindingForm
              key={editing.id}
              finding={editing}
              targets={targets}
              pending={save.isPending}
              error={
                save.error ? errorMessage(save.error) : remove.error ? errorMessage(remove.error) : null
              }
              submitLabel="Save changes"
              onSubmit={(v) => save.mutate({ id: editing.id, v })}
              extraActions={
                <Button type="button" variant="destructive" onClick={() => setConfirmDelete(true)}>
                  Delete
                </Button>
              }
            />
          ) : null}
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={confirmDelete && editing != null}
        onOpenChange={setConfirmDelete}
        title="Delete finding?"
        description={editing ? `“${editing.title}” will be permanently deleted.` : undefined}
        confirmLabel="Delete finding"
        destructive
        pending={remove.isPending}
        onConfirm={() => editing && remove.mutate(editing.id)}
      />
    </section>
  );
}
