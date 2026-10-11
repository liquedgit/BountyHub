export type ScoreBand = "high" | "medium" | "low";

/** Triage scores are 0-100: 70+ high, 40-69 medium, below that low. */
export function scoreBand(score: number): ScoreBand {
  if (score >= 70) return "high";
  if (score >= 40) return "medium";
  return "low";
}

export const STAGES = ["scope", "subfinder", "httpx", "js_crawler", "secret_scanner", "triage"] as const;

export const POLL_INTERVAL_MS = 3000;

export function isTerminal(status: string) {
  return status === "completed" || status === "failed";
}
