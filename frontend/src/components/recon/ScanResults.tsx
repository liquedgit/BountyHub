"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { Fragment, useMemo, useState } from "react";
import { CopyButton } from "@/components/common/CopyButton";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { ListSkeleton } from "@/components/common/ListSkeleton";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { api, ApiError, errorMessage } from "@/lib/api";
import type { ReconAsset, ReconJob } from "@/lib/types";
import { isTerminal, POLL_INTERVAL_MS, scoreBand } from "./scoring";

const GROUPS = [
  { type: "subdomain", label: "Subdomains" },
  { type: "host", label: "Hosts" },
  { type: "endpoint", label: "Endpoints" },
  { type: "secret", label: "Secrets" },
];

const BAND_VARIANT = { high: "destructive", medium: "warning", low: "success" } as const;

function Score({ asset }: { asset: ReconAsset }) {
  if (asset.triage_score == null) return <span className="text-muted-foreground">unscored</span>;
  const band = scoreBand(asset.triage_score);
  return (
    <span className="inline-flex items-center gap-2">
      <span className="font-mono">{Math.round(asset.triage_score)}</span>
      <Badge variant={BAND_VARIANT[band]}>{asset.triage_label ?? band}</Badge>
    </span>
  );
}

function MetaDetails({ asset }: { asset: ReconAsset }) {
  const meta = asset.meta ?? {};
  const entries =
    asset.asset_type === "host"
      ? (["status_code", "title", "tech"] as const).map((k) => [k, meta[k]] as const)
      : Object.entries(meta);
  if (entries.length === 0) return <p className="text-sm text-muted-foreground">No details recorded.</p>;
  return (
    <dl className="grid gap-x-4 gap-y-1 text-sm sm:grid-cols-[auto_1fr]">
      {entries.map(([k, v]) => (
        <Fragment key={k}>
          <dt className="text-muted-foreground">{k === "status_code" ? "status" : k}</dt>
          <dd className="break-all">
            {Array.isArray(v) ? (v.length ? v.join(", ") : "—") : v == null || v === "" ? "—" : String(v)}
          </dd>
        </Fragment>
      ))}
    </dl>
  );
}

function AssetTable({ assets }: { assets: ReconAsset[] }) {
  const [open, setOpen] = useState<number | null>(null);
  if (assets.length === 0) return <p className="text-sm text-muted-foreground">Nothing matches.</p>;
  return (
    <div className="overflow-x-auto">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Value</TableHead>
            <TableHead>Source</TableHead>
            <TableHead>Triage</TableHead>
            <TableHead>Reason</TableHead>
            <TableHead className="w-24">Details</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {assets.map((a) => (
            <Fragment key={a.id}>
              <TableRow data-testid="asset-row">
                <TableCell>
                  <span className="inline-flex items-center gap-1">
                    <span className="break-all font-mono text-xs">{a.value}</span>
                    <CopyButton value={a.value} label={`Copy ${a.value}`} />
                  </span>
                </TableCell>
                <TableCell>{a.source ?? "—"}</TableCell>
                <TableCell>
                  <Score asset={a} />
                </TableCell>
                <TableCell className="text-sm text-muted-foreground">{a.triage_reason ?? "—"}</TableCell>
                <TableCell>
                  <Button
                    variant="ghost"
                    size="sm"
                    aria-expanded={open === a.id}
                    aria-label={`Details for ${a.value}`}
                    onClick={() => setOpen(open === a.id ? null : a.id)}
                  >
                    {open === a.id ? "Hide" : "Show"}
                  </Button>
                </TableCell>
              </TableRow>
              {open === a.id && (
                <TableRow>
                  <TableCell colSpan={5}>
                    <MetaDetails asset={a} />
                  </TableCell>
                </TableRow>
              )}
            </Fragment>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

function TriageButton({ job }: { job: ReconJob }) {
  const qc = useQueryClient();
  const run = useMutation({
    mutationFn: () => api.triage.run(job.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["recon-assets", job.id] }),
  });
  const err = run.error;
  return (
    <div className="space-y-2">
      <Button variant="outline" onClick={() => run.mutate()} disabled={run.isPending}>
        {run.isPending ? "Triaging…" : "Re-run AI triage"}
      </Button>
      {err ? (
        <p role="alert" className="text-sm text-destructive">
          {err instanceof ApiError && err.status === 409 ? (
            <>
              No AI provider configured.{" "}
              <Link href="/settings" className="underline">
                Open settings
              </Link>
            </>
          ) : (
            errorMessage(err)
          )}
        </p>
      ) : null}
    </div>
  );
}

export function ScanResults({ job }: { job: ReconJob }) {
  const [tab, setTab] = useState(GROUPS[0].type);
  const [filter, setFilter] = useState("");
  const assets = useQuery({
    queryKey: ["recon-assets", job.id, job.status],
    queryFn: () => api.recon.assets(job.id),
    refetchInterval: isTerminal(job.status) ? false : POLL_INTERVAL_MS,
  });

  const grouped = useMemo(() => {
    const q = filter.trim().toLowerCase();
    const match = (a: ReconAsset) =>
      !q ||
      [a.value, a.source, a.triage_label, a.triage_reason].some((s) => s?.toLowerCase().includes(q));
    return GROUPS.map((g) => {
      const all = (assets.data ?? []).filter((a) => a.asset_type === g.type);
      const shown = all.filter(match).sort((a, b) => (b.triage_score ?? -1) - (a.triage_score ?? -1));
      return { ...g, total: all.length, shown };
    });
  }, [assets.data, filter]);

  return (
    <section aria-label="Results" className="space-y-3">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <h2 className="text-base font-medium">Results</h2>
        {job.status === "completed" && <TriageButton job={job} />}
      </div>
      {assets.isLoading ? (
        <ListSkeleton rows={4} />
      ) : assets.error ? (
        <ErrorState error={assets.error} onRetry={() => assets.refetch()} />
      ) : (assets.data ?? []).length === 0 ? (
        <EmptyState
          title={isTerminal(job.status) ? "No assets found" : "No results yet"}
          description={isTerminal(job.status) ? "This scan did not discover any assets." : "Assets appear here as the scan progresses."}
        />
      ) : (
        <>
          <Input
            aria-label="Filter results"
            placeholder="Filter by value, source, label or reason"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          />
          <Tabs value={tab} onValueChange={setTab}>
            <TabsList className="h-auto flex-wrap">
              {grouped.map((g) => (
                <TabsTrigger key={g.type} value={g.type}>
                  {`${g.label} (${g.total})`}
                </TabsTrigger>
              ))}
            </TabsList>
            {grouped.map((g) => (
              <TabsContent key={g.type} value={g.type}>
                {g.total === 0 ? (
                  <p className="text-sm text-muted-foreground">None.</p>
                ) : (
                  <AssetTable assets={g.shown} />
                )}
              </TabsContent>
            ))}
          </Tabs>
        </>
      )}
    </section>
  );
}
