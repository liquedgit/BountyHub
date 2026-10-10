export type ScopeAction = "in" | "out";
export type ScopeType = "domain" | "wildcard" | "ip" | "url";
export const FINDING_STATUSES = [
  "new", "triaged", "submitted", "accepted", "duplicate", "rejected", "resolved", "paid",
] as const;
export type FindingStatus = (typeof FINDING_STATUSES)[number];
export const SEVERITIES = ["info", "low", "medium", "high", "critical"] as const;
export type Severity = (typeof SEVERITIES)[number];

export interface Program {
  id: number;
  name: string;
  platform: string | null;
  url: string | null;
  reward_info: string | null;
  created_at: string;
}
export interface ScopeRule {
  id: number;
  program_id: number;
  action: ScopeAction;
  type: ScopeType;
  value: string;
}
export interface Finding {
  id: number;
  program_id: number;
  title: string;
  description: string | null;
  target_id: number | null;
  status: FindingStatus;
  severity: Severity;
  payout_cents: number | null;
}
export interface Note {
  id: number;
  program_id: number;
  title: string;
  body_md: string;
  finding_id: number | null;
}
export type JobStatus = "pending" | "queued" | "running" | "completed" | "failed" | string;
export interface ReconJob {
  id: number;
  program_id: number;
  status: JobStatus;
  current_stage: string | null;
  targets: string[];
  rejected_targets: string[];
  error: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}
export interface ReconAsset {
  id: number;
  asset_type: string;
  value: string;
  source: string;
  meta: Record<string, unknown>;
  triage_score: number | null;
}
