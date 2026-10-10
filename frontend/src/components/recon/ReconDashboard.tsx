"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { ReconAsset } from "@/lib/types";

export const POLL_INTERVAL_MS = 3000;
const TERMINAL = ["completed", "failed"];
const GROUPS = [
  { type: "subdomain", label: "Subdomains" },
  { type: "host", label: "Hosts" },
  { type: "endpoint", label: "Endpoints" },
  { type: "secret", label: "Secrets" },
];

export function isTerminal(status: string) {
  return TERMINAL.includes(status);
}

function Score({ value }: { value: number | null }) {
  if (value == null) return <span className="opacity-50">unscored</span>;
  const tone = value >= 0.7 ? "text-red-500" : value >= 0.4 ? "text-yellow-500" : "text-green-500";
  return <span className={tone}>{value.toFixed(2)}</span>;
}

function AssetGroup({ label, assets }: { label: string; assets: ReconAsset[] }) {
  const sorted = [...assets].sort((a, b) => (b.triage_score ?? -1) - (a.triage_score ?? -1));
  return (
    <section aria-label={label} className="rounded border p-3">
      <h3 className="mb-2 font-semibold">
        {label} ({assets.length})
      </h3>
      {sorted.length === 0 ? (
        <p className="text-sm opacity-60">None.</p>
      ) : (
        <ul className="space-y-1 text-sm">
          {sorted.map((a) => (
            <li key={a.id} className="flex justify-between gap-2">
              <span className="break-all">{a.value}</span>
              <span className="whitespace-nowrap">
                <span className="mr-2 text-xs opacity-60">{a.source}</span>
                <Score value={a.triage_score} />
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export function ReconDashboard({ programId }: { programId: number }) {
  const [targetsText, setTargetsText] = useState("");
  const [jobId, setJobId] = useState<number | null>(null);
  const [rejected, setRejected] = useState<string[]>([]);
  const [launchError, setLaunchError] = useState<string | null>(null);

  const launch = useMutation({
    mutationFn: (targets: string[]) => api.recon.start(programId, targets),
    onSuccess: (job) => {
      setJobId(job.id);
      setRejected(job.rejected_targets ?? []);
      setLaunchError(null);
    },
    onError: (err) => {
      const body = err instanceof ApiError ? (err.body as any) : undefined;
      const rej: string[] = body?.detail?.rejected_targets ?? [];
      setRejected(rej);
      setLaunchError(
        rej.length ? "No targets are in scope for this program." : "Failed to start scan.",
      );
    },
  });

  const job = useQuery({
    queryKey: ["recon-job", jobId],
    queryFn: () => api.recon.job(jobId!),
    enabled: jobId != null,
    refetchInterval: (q) => (q.state.data && isTerminal(q.state.data.status) ? false : POLL_INTERVAL_MS),
  });
  const status = job.data?.status;
  const assets = useQuery({
    queryKey: ["recon-assets", jobId, status],
    queryFn: () => api.recon.assets(jobId!),
    enabled: jobId != null && status != null,
    refetchInterval: status && !isTerminal(status) ? POLL_INTERVAL_MS : false,
  });

  const targets = targetsText.split(/[\s,]+/).filter(Boolean);

  return (
    <div className="space-y-4">
      <form
        className="space-y-2"
        onSubmit={(e) => {
          e.preventDefault();
          if (targets.length) launch.mutate(targets);
        }}
      >
        <textarea
          aria-label="Targets"
          placeholder="One target per line, e.g. app.example.com"
          className="h-28 w-full rounded border bg-transparent p-2 font-mono text-sm"
          value={targetsText}
          onChange={(e) => setTargetsText(e.target.value)}
        />
        <button
          className="rounded bg-blue-600 px-3 py-1 text-white disabled:opacity-50"
          type="submit"
          disabled={launch.isPending || targets.length === 0}
        >
          Launch scan
        </button>
        <p className="text-xs opacity-60">
          Only targets matching the program&apos;s in-scope rules will be scanned.
        </p>
      </form>

      {launchError && <p role="alert" className="text-red-500">{launchError}</p>}
      {rejected.length > 0 && (
        <p className="text-sm text-yellow-500" data-testid="rejected">
          Rejected (out of scope): {rejected.join(", ")}
        </p>
      )}

      {job.data && (
        <div className="rounded border p-3" aria-label="Job status">
          <p>
            Scan #{job.data.id}: <strong data-testid="job-status">{job.data.status}</strong>
            {job.data.current_stage ? ` — ${job.data.current_stage}` : ""}
          </p>
          {job.data.error && <p className="text-red-500">{job.data.error}</p>}
        </div>
      )}

      {jobId != null && (
        <div className="grid gap-3 md:grid-cols-2">
          {GROUPS.map((g) => (
            <AssetGroup
              key={g.type}
              label={g.label}
              assets={(assets.data ?? []).filter((a) => a.asset_type === g.type)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
