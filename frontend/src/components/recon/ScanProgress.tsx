import { Badge } from "@/components/ui/badge";
import { StatusBadge } from "@/components/common/StatusBadge";
import { formatDate, formatDuration } from "@/lib/format";
import type { ReconJob } from "@/lib/types";
import { STAGES } from "./scoring";

function stageState(job: ReconJob, index: number): "done" | "current" | "failed" | "pending" {
  if (job.status === "completed") return "done";
  const cur = STAGES.indexOf((job.current_stage ?? "") as (typeof STAGES)[number]);
  if (job.status === "queued" || cur < 0) return job.status === "failed" && index === 0 ? "failed" : "pending";
  if (index < cur) return "done";
  if (index === cur) return job.status === "failed" ? "failed" : "current";
  return "pending";
}

const STATE_TEXT = { done: "done", current: "in progress", failed: "failed", pending: "pending" };

export function ScanProgress({ job }: { job: ReconJob }) {
  return (
    <section aria-label="Scan progress" className="space-y-4 rounded-lg border p-4">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-base font-medium">Scan #{job.id}</h2>
        <span data-testid="job-status" className="sr-only">{job.status}</span>
        <StatusBadge status={job.status} />
      </div>

      <ol className="grid gap-2 sm:grid-cols-3 lg:grid-cols-6" aria-label="Stages">
        {STAGES.map((stage, i) => {
          const state = stageState(job, i);
          return (
            <li
              key={stage}
              data-stage={stage}
              data-state={state}
              aria-current={state === "current" ? "step" : undefined}
              className="rounded-md border p-2 text-sm"
            >
              <div className="font-medium">{stage}</div>
              <Badge
                variant={
                  state === "done" ? "success" : state === "current" ? "info" : state === "failed" ? "destructive" : "secondary"
                }
              >
                {STATE_TEXT[state]}
              </Badge>
            </li>
          );
        })}
      </ol>

      <dl className="grid gap-2 text-sm sm:grid-cols-3">
        <div>
          <dt className="text-muted-foreground">Started</dt>
          <dd>{formatDate(job.started_at)}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Finished</dt>
          <dd>{formatDate(job.finished_at)}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Duration</dt>
          <dd>{job.started_at ? formatDuration(job.started_at, job.finished_at) : "—"}</dd>
        </div>
      </dl>

      {job.rejected_targets.length > 0 && (
        <p className="text-sm text-warning" data-testid="rejected">
          Rejected (out of scope): {job.rejected_targets.join(", ")}
        </p>
      )}
      {job.notes.length > 0 && (
        <ul className="space-y-1 text-sm text-warning" aria-label="Warnings">
          {job.notes.map((n, i) => (
            <li key={i}>Warning: {n}</li>
          ))}
        </ul>
      )}
      {job.error && (
        <div role="alert" className="rounded-md border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive">
          <strong>Scan failed:</strong> {job.error}
        </div>
      )}
    </section>
  );
}
