"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { DashboardSummary, Severity } from "@/lib/types";
import { formatMoney, formatRelative } from "@/lib/format";
import { PageHeader } from "@/components/common/PageHeader";
import { StatCard } from "@/components/common/StatCard";
import { SeverityBadge } from "@/components/common/SeverityBadge";
import { StatusBadge } from "@/components/common/StatusBadge";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

const SEVERITIES: Severity[] = ["critical", "high", "medium", "low", "info"];

const BAR_COLOR: Record<Severity, string> = {
  critical: "bg-destructive",
  high: "bg-destructive/70",
  medium: "bg-warning",
  low: "bg-muted-foreground",
  info: "bg-info",
};

const CHECKLIST = [
  { label: "Create a program", href: "/programs", hint: "Track the target you are hunting on." },
  { label: "Add scope rules", href: "/programs", hint: "Recon only runs against in-scope assets." },
  { label: "Configure the AI provider", href: "/settings", hint: "Enables asset ranking and triage." },
  { label: "Run a scan", href: "/recon", hint: "Enumerate subdomains and probe hosts." },
];

export function DashboardSkeleton() {
  return (
    <div className="space-y-6" aria-busy="true" aria-label="Loading overview">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }, (_, i) => (
          <Skeleton key={i} className="h-24" />
        ))}
      </div>
      <Skeleton className="h-48" />
      <div className="grid gap-4 lg:grid-cols-2">
        <Skeleton className="h-56" />
        <Skeleton className="h-56" />
      </div>
    </div>
  );
}

function GettingStarted() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Getting started</CardTitle>
        <CardDescription>No programs yet. Work through these steps to run your first scan.</CardDescription>
      </CardHeader>
      <CardContent>
        <ol className="space-y-3">
          {CHECKLIST.map((item, i) => (
            <li key={item.label} className="flex items-start gap-3 text-sm">
              <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full border text-xs">
                {i + 1}
              </span>
              <div>
                <Link href={item.href} className="font-medium underline-offset-4 hover:underline">
                  {item.label}
                </Link>
                <p className="text-muted-foreground">{item.hint}</p>
              </div>
            </li>
          ))}
        </ol>
      </CardContent>
    </Card>
  );
}

function SeverityBars({ bySeverity }: { bySeverity: Record<Severity, number> }) {
  const max = Math.max(1, ...SEVERITIES.map((s) => bySeverity[s] ?? 0));
  return (
    <Card>
      <CardHeader>
        <CardTitle>Findings by severity</CardTitle>
      </CardHeader>
      <CardContent>
        <ul className="space-y-2">
          {SEVERITIES.map((s) => {
            const count = bySeverity[s] ?? 0;
            return (
              <li key={s} className="flex items-center gap-3 text-sm">
                <span className="w-16 capitalize text-muted-foreground">{s}</span>
                <div className="h-2 flex-1 overflow-hidden rounded-full bg-muted">
                  <div
                    data-testid={`bar-${s}`}
                    className={`h-full rounded-full ${BAR_COLOR[s]}`}
                    style={{ width: `${(count / max) * 100}%` }}
                  />
                </div>
                <span className="w-8 text-right tabular-nums">{count}</span>
              </li>
            );
          })}
        </ul>
      </CardContent>
    </Card>
  );
}

function RecentFindings({ items }: { items: DashboardSummary["recent_findings"] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Recent findings</CardTitle>
      </CardHeader>
      <CardContent>
        {items.length === 0 ? (
          <p className="text-sm text-muted-foreground">No findings yet.</p>
        ) : (
          <ul className="divide-y">
            {items.map((f) => (
              <li key={f.id} className="flex items-center justify-between gap-3 py-2 text-sm">
                <div className="min-w-0">
                  <Link
                    href={`/findings?program=${f.program_id}`}
                    className="block truncate font-medium hover:underline"
                  >
                    {f.title}
                  </Link>
                  <span className="text-xs text-muted-foreground">
                    {f.program_name ?? "Deleted program"} · {formatRelative(f.updated_at)}
                  </span>
                </div>
                <div className="flex shrink-0 gap-1">
                  <SeverityBadge severity={f.severity} />
                  <StatusBadge status={f.status} />
                </div>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

function RecentScans({ items }: { items: DashboardSummary["recent_scans"] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Recent scans</CardTitle>
      </CardHeader>
      <CardContent>
        {items.length === 0 ? (
          <p className="text-sm text-muted-foreground">No scans yet.</p>
        ) : (
          <ul className="divide-y">
            {items.map((s) => (
              <li key={s.id} className="flex items-center justify-between gap-3 py-2 text-sm">
                <div className="min-w-0">
                  <Link
                    href={`/recon?program=${s.program_id}&scan=${s.id}`}
                    className="block truncate font-medium hover:underline"
                  >
                    {s.program_name ?? "Deleted program"} · scan #{s.id}
                  </Link>
                  <span className="text-xs text-muted-foreground">
                    {s.target_count} target{s.target_count === 1 ? "" : "s"} · {formatRelative(s.created_at)}
                  </span>
                </div>
                <StatusBadge status={s.status} />
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

export function DashboardOverview() {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["dashboard", "summary"],
    queryFn: () => api.dashboard.summary(),
  });

  let body;
  if (isLoading) {
    body = <DashboardSkeleton />;
  } else if (error || !data) {
    body = <ErrorState error={error} title="Could not load the overview" onRetry={() => refetch()} />;
  } else {
    body = (
      <div className="space-y-6">
        {!data.ai_configured && (
          <div role="note" className="rounded-lg border border-warning/40 bg-warning/10 p-4 text-sm">
            <span className="font-medium">AI provider not configured.</span>{" "}
            <Link href="/settings" className="underline underline-offset-4">
              Configure it in Settings
            </Link>{" "}
            to enable asset ranking and triage.
          </div>
        )}
        {data.programs === 0 ? (
          <GettingStarted />
        ) : (
          <>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <StatCard label="Programs" value={data.programs} />
              <StatCard label="Open findings" value={data.findings.open} hint={`${data.findings.total} total`} />
              <StatCard label="Paid total" value={formatMoney(data.payout_cents_paid)} />
              <StatCard label="Active scans" value={data.scans.active} hint={`${data.scans.total} total`} />
            </div>
            <SeverityBars bySeverity={data.findings.by_severity} />
            <div className="grid gap-4 lg:grid-cols-2">
              <RecentFindings items={data.recent_findings} />
              <RecentScans items={data.recent_scans} />
            </div>
          </>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader title="Overview" description="Your programs, findings and scans at a glance." />
      {body}
    </div>
  );
}
