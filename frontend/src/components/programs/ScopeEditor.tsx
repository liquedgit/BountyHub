"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Trash2 } from "lucide-react";
import { useState } from "react";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { ListSkeleton } from "@/components/common/ListSkeleton";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { api, errorMessage } from "@/lib/api";
import type { ScopeAction, ScopeRule, ScopeType } from "@/lib/types";

const TYPES: ScopeType[] = ["domain", "wildcard", "ip", "url"];

const TYPE_HELP: Record<ScopeType, string> = {
  domain: "Exact hostname, e.g. app.example.com. Subdomains are not covered.",
  wildcard: "*.example.com covers every subdomain but not the apex example.com.",
  ip: "A single IP address or a CIDR range, e.g. 203.0.113.0/24.",
  url: "A URL path prefix, e.g. https://example.com/api/.",
};

export function ScopeEditor({ programId }: { programId: number }) {
  const qc = useQueryClient();
  const rules = api.scopeRules(programId);
  const key = ["scope-rules", programId];
  const { data = [], isLoading, error, refetch } = useQuery({ queryKey: key, queryFn: rules.list });
  const [action, setAction] = useState<ScopeAction>("in");
  const [type, setType] = useState<ScopeType>("wildcard");
  const [value, setValue] = useState("");
  const [toDelete, setToDelete] = useState<ScopeRule | null>(null);
  const [host, setHost] = useState("");

  const add = useMutation({
    meta: { silent: true },
    mutationFn: () => rules.create({ action, type, value: value.trim() }),
    onSuccess: () => {
      setValue("");
      qc.invalidateQueries({ queryKey: key });
    },
  });
  const remove = useMutation({
    mutationFn: (id: number) => rules.remove(id),
    onSuccess: () => {
      setToDelete(null);
      qc.invalidateQueries({ queryKey: key });
    },
  });
  const check = useMutation({
    meta: { silent: true },
    mutationFn: () => api.programs.scopeCheck(programId, host.trim()),
  });

  const groups: { action: ScopeAction; title: string }[] = [
    { action: "in", title: "In scope" },
    { action: "out", title: "Out of scope" },
  ];

  return (
    <section aria-label="Scope editor" className="space-y-6 pt-4">
      <form
        className="grid gap-3 sm:grid-cols-[10rem_10rem_1fr_auto] sm:items-end"
        onSubmit={(e) => {
          e.preventDefault();
          if (value.trim()) add.mutate();
        }}
      >
        <div className="grid gap-2">
          <Label htmlFor="scope-action">Action</Label>
          <Select
            id="scope-action"
            value={action}
            onChange={(e) => setAction(e.target.value as ScopeAction)}
          >
            <option value="in">In scope</option>
            <option value="out">Out of scope</option>
          </Select>
        </div>
        <div className="grid gap-2">
          <Label htmlFor="scope-type">Type</Label>
          <Select id="scope-type" value={type} onChange={(e) => setType(e.target.value as ScopeType)}>
            {TYPES.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </Select>
        </div>
        <div className="grid gap-2">
          <Label htmlFor="scope-value">Scope value</Label>
          <Input
            id="scope-value"
            placeholder="*.example.com"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            aria-describedby="scope-type-help"
          />
        </div>
        <Button type="submit" disabled={add.isPending || !value.trim()}>
          {add.isPending ? "Adding…" : "Add rule"}
        </Button>
        <p id="scope-type-help" className="text-xs text-muted-foreground sm:col-span-4">
          {TYPE_HELP[type]}
        </p>
        {add.error ? (
          <p role="alert" className="text-sm text-destructive sm:col-span-4">
            {errorMessage(add.error)}
          </p>
        ) : null}
      </form>

      {isLoading ? (
        <ListSkeleton rows={3} />
      ) : error ? (
        <ErrorState error={error} title="Failed to load scope rules" onRetry={() => refetch()} />
      ) : data.length === 0 ? (
        <EmptyState
          title="No scope rules yet"
          description="Add in-scope and out-of-scope rules so recon only touches what the program allows."
        />
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {groups.map((g) => {
            const items = data.filter((r) => r.action === g.action);
            return (
              <div key={g.action} className="space-y-2">
                <h3 className="text-sm font-medium">
                  {g.title} <span className="text-muted-foreground">({items.length})</span>
                </h3>
                {items.length === 0 ? (
                  <p className="text-sm text-muted-foreground">None.</p>
                ) : (
                  <ul className="divide-y rounded-md border">
                    {items.map((r) => (
                      <li key={r.id} className="flex items-center justify-between gap-2 p-2">
                        <span className="flex min-w-0 items-center gap-2">
                          <Badge variant={r.action === "in" ? "success" : "destructive"}>{r.type}</Badge>
                          <span className="break-all text-sm">{r.value}</span>
                        </span>
                        <Button
                          variant="ghost"
                          size="icon"
                          aria-label={`Delete ${r.value}`}
                          onClick={() => setToDelete(r)}
                        >
                          <Trash2 className="h-4 w-4" aria-hidden />
                        </Button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            );
          })}
        </div>
      )}

      <form
        className="space-y-2 rounded-md border p-4"
        aria-label="Test a host"
        onSubmit={(e) => {
          e.preventDefault();
          if (host.trim()) check.mutate();
        }}
      >
        <h3 className="text-sm font-medium">Test a host</h3>
        <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
          <div className="grid flex-1 gap-2">
            <Label htmlFor="scope-check-host">Host to test</Label>
            <Input
              id="scope-check-host"
              placeholder="app.example.com"
              value={host}
              onChange={(e) => setHost(e.target.value)}
            />
          </div>
          <Button type="submit" variant="outline" disabled={check.isPending || !host.trim()}>
            {check.isPending ? "Checking…" : "Check scope"}
          </Button>
        </div>
        {check.error ? (
          <p role="alert" className="text-sm text-destructive">
            {errorMessage(check.error)}
          </p>
        ) : null}
        {check.data ? (
          <p role="status" className="flex flex-wrap items-center gap-2 text-sm">
            <Badge variant={check.data.in_scope ? "success" : "destructive"}>
              {check.data.in_scope ? "In scope" : "Out of scope"}
            </Badge>
            <span className="font-medium">{check.data.host}</span>
            <span className="text-muted-foreground">{check.data.reason}</span>
          </p>
        ) : null}
      </form>

      <ConfirmDialog
        open={!!toDelete}
        onOpenChange={(o) => !o && setToDelete(null)}
        title="Delete scope rule?"
        description={toDelete ? `Remove ${toDelete.action === "in" ? "in-scope" : "out-of-scope"} rule “${toDelete.value}”.` : undefined}
        confirmLabel={remove.isPending ? "Deleting…" : "Delete rule"}
        destructive
        pending={remove.isPending}
        onConfirm={() => toDelete && remove.mutate(toDelete.id)}
      />
    </section>
  );
}
