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
  updated_at: string;
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
  created_at: string;
  updated_at: string;
}
export interface Note {
  id: number;
  program_id: number;
  title: string;
  body_md: string;
  finding_id: number | null;
  created_at: string;
  updated_at: string;
}
export type JobStatus = "queued" | "running" | "completed" | "failed";
export interface ReconJob {
  id: number;
  program_id: number;
  status: JobStatus;
  current_stage: string | null;
  targets: string[];
  rejected_targets: string[];
  error: string | null;
  notes: string[];
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}
export interface ReconAsset {
  id: number;
  asset_type: string;
  value: string;
  source: string | null;
  meta: Record<string, unknown>;
  triage_score: number | null;
  triage_label: string | null;
  triage_reason: string | null;
}

export interface Target {
  id: number;
  program_id: number;
  value: string;
  description: string | null;
  created_at: string;
  updated_at: string;
}
export interface ScopeCheckResult {
  host: string;
  in_scope: boolean;
  reason: string;
}
export type AIProvider = "claude" | "openai_compatible";
export interface AISettings {
  provider: AIProvider | string | null;
  claude_token_set: boolean;
  claude_model: string | null;
  openai_base_url: string | null;
  openai_api_key_set: boolean;
  openai_model: string | null;
}
export interface AISettingsUpdate {
  provider?: AIProvider | null;
  claude_token?: string | null;
  claude_model?: string | null;
  openai_base_url?: string | null;
  openai_api_key?: string | null;
  openai_model?: string | null;
}
export interface DashboardSummary {
  programs: number;
  targets: number;
  notes: number;
  findings: {
    total: number;
    open: number;
    by_status: Record<FindingStatus, number>;
    by_severity: Record<Severity, number>;
  };
  payout_cents_paid: number;
  scans: { total: number; active: number };
  ai_configured: boolean;
  recent_findings: {
    id: number;
    program_id: number;
    program_name: string | null;
    title: string;
    severity: Severity;
    status: FindingStatus;
    updated_at: string;
  }[];
  recent_scans: {
    id: number;
    program_id: number;
    program_name: string | null;
    status: JobStatus;
    current_stage: string | null;
    target_count: number;
    created_at: string;
    finished_at: string | null;
  }[];
}
