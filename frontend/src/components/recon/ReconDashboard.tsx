"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { ListSkeleton } from "@/components/common/ListSkeleton";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { api, ApiError, errorMessage } from "@/lib/api";
import { formatRelative } from "@/lib/format";
import { cn } from "@/lib/utils";
import { ScanProgress } from "./ScanProgress";
import { ScanResults } from "./ScanResults";
import { isTerminal, POLL_INTERVAL_MS } from "./scoring";

export { isTerminal, POLL_INTERVAL_MS };

function parseTargets(text: string): string[] {
  return Array.from(new Set(text.split(/[\s,]+/).filter(Boolean)));
}

export function ReconDashboard({ programId }: { programId: number }) {
  const qc = useQueryClient();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [targetsText, setTargetsText] = useState("");
  const [rejected, setRejected] = useState<string[]>([]);
  const [launchError, setLaunchError] = useState<string | null>(null);

  const rawScan = Number(searchParams.get("scan"));
  const scanId = Number.isInteger(rawScan) && rawScan > 0 ? rawScan : null;

  function selectScan(id: number) {
    const next = new URLSearchParams(searchParams.toString());
    next.set("scan", String(id));
    router.replace(`${pathname}?${next.toString()}`);
  }

  const launch = useMutation({
    mutationFn: (targets: string[]) => api.recon.start(programId, targets),
    onSuccess: (job) => {
      setRejected([]);
      setLaunchError(null);
      qc.invalidateQueries({ queryKey: ["recon-scans", programId] });
      selectScan(job.id);
    },
    onError: (err) => {
      const body = err instanceof ApiError ? (err.body as { rejected_targets?: unknown } | undefined) : undefined;
      const rej = Array.isArray(body?.rejected_targets) ? (body!.rejected_targets as string[]) : [];
      setRejected(rej);
      setLaunchError(
        rej.length
          ? err.message || "No targets are in scope for this program."
          : errorMessage(err),
      );
    },
  });

  const scans = useQuery({
    queryKey: ["recon-scans", programId],
    queryFn: () => api.recon.list(programId),
    refetchInterval: (q) =>
      q.state.data?.some((j) => !isTerminal(j.status)) ? POLL_INTERVAL_MS : false,
  });

  const job = useQuery({
    queryKey: ["recon-job", scanId],
    queryFn: () => api.recon.job(scanId!),
    enabled: scanId != null,
    refetchInterval: (q) =>
      q.state.data && isTerminal(q.state.data.status) ? false : POLL_INTERVAL_MS,
  });

  const targets = parseTargets(targetsText);

  return (
    <div className="space-y-6">
      <form
        className="space-y-2"
        onSubmit={(e) => {
          e.preventDefault();
          if (targets.length) launch.mutate(targets);
        }}
      >
        <Label htmlFor="recon-targets">Targets</Label>
        <Textarea
          id="recon-targets"
          placeholder="One target per line, e.g. app.example.com"
          className="h-28 font-mono"
          value={targetsText}
          onChange={(e) => setTargetsText(e.target.value)}
        />
        <p className="text-xs text-muted-foreground" data-testid="target-count">
          {targets.length} {targets.length === 1 ? "target" : "targets"} parsed
        </p>
        <Button type="submit" disabled={launch.isPending || targets.length === 0}>
          {launch.isPending ? "Launching…" : "Launch scan"}
        </Button>
        <p className="text-xs text-muted-foreground">
          Only targets matching the program&apos;s in-scope rules will be scanned.
        </p>
      </form>

      {launchError && (
        <div role="alert" className="space-y-1 text-sm text-destructive">
          <p>{launchError}</p>
          {rejected.length > 0 && (
            <p className="text-warning" data-testid="rejected">
              Rejected (out of scope): {rejected.join(", ")}
            </p>
          )}
        </div>
      )}

      <section aria-label="Scan history" className="space-y-2">
        <h2 className="text-base font-medium">Scan history</h2>
        {scans.isLoading ? (
          <ListSkeleton rows={3} />
        ) : scans.error ? (
          <ErrorState error={scans.error} onRetry={() => scans.refetch()} />
        ) : (scans.data ?? []).length === 0 ? (
          <EmptyState title="No scans yet" description="Launch a scan above to see its progress and results here." />
        ) : (
          <ul className="divide-y rounded-lg border">
            {scans.data!.map((s) => (
              <li key={s.id}>
                <button
                  type="button"
                  onClick={() => selectScan(s.id)}
                  aria-current={s.id === scanId ? "true" : undefined}
                  className={cn(
                    "flex w-full flex-wrap items-center gap-3 px-3 py-2 text-left text-sm hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                    s.id === scanId && "bg-muted",
                  )}
                >
                  <span className="font-medium">Scan #{s.id}</span>
                  <StatusBadge status={s.status} />
                  <span className="text-muted-foreground">
                    {s.targets.length} {s.targets.length === 1 ? "target" : "targets"}
                  </span>
                  <span className="ml-auto text-muted-foreground">{formatRelative(s.created_at)}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      {scanId != null &&
        (job.isLoading ? (
          <ListSkeleton rows={3} />
        ) : job.error || !job.data ? (
          <ErrorState error={job.error} title="Could not load scan" onRetry={() => job.refetch()} />
        ) : (
          <div className="space-y-6">
            <ScanProgress job={job.data} />
            <ScanResults job={job.data} />
          </div>
        ))}
    </div>
  );
}
