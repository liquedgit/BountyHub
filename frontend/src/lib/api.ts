import type {
  AISettings, AISettingsUpdate, DashboardSummary, Finding, Note, Program, ReconAsset,
  ReconJob, ScopeCheckResult, ScopeRule, Target,
} from "./types";

/**
 * Browser-side API client. Requests go through the Next.js `/api/backend/*`
 * rewrite (see next.config.mjs), which proxies to the FastAPI backend and keeps
 * everything same-origin so the httpOnly auth cookie is sent automatically.
 */
export const API_BASE = "/api/backend";

export class ApiError extends Error {
  constructor(public status: number, message: string, public body?: unknown) {
    super(message);
    this.name = "ApiError";
  }
}

/** Human-readable message from a FastAPI error body (`detail` string or validation list). */
function messageFromBody(body: unknown, fallback: string): string {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string" && detail) return detail;
  if (Array.isArray(detail)) {
    const msgs = detail
      .map((d) => {
        if (typeof d === "string") return d;
        const item = d as { msg?: unknown; loc?: unknown };
        if (typeof item?.msg !== "string") return null;
        const loc = Array.isArray(item.loc)
          ? item.loc.filter((p) => p !== "body" && p !== "query").join(".")
          : "";
        return loc ? `${loc}: ${item.msg}` : item.msg;
      })
      .filter((m): m is string => !!m);
    if (msgs.length) return msgs.join("; ");
  }
  return fallback;
}

export function errorMessage(err: unknown): string {
  if (err instanceof Error && err.message) return err.message;
  if (typeof err === "string" && err) return err;
  return "Something went wrong";
}

export async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", ...(init.headers ?? {}) },
  });
  if (!res.ok) {
    let body: unknown;
    try {
      body = await res.json();
    } catch {
      /* non-JSON error body */
    }
    if (
      res.status === 401 &&
      typeof window !== "undefined" &&
      !path.startsWith("/auth/login")
    ) {
      const here = window.location.pathname + window.location.search;
      window.location.assign(`/login?next=${encodeURIComponent(here)}`);
    }
    throw new ApiError(
      res.status,
      messageFromBody(body, res.statusText || `Request failed (${res.status})`),
      body,
    );
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

/** Alias kept for callers of the former `api-client.ts`. */
export const apiFetch = request;

const json = (method: string, data: unknown): RequestInit => ({
  method,
  body: JSON.stringify(data),
});

const nested = <T, C, U>(path: string) => (programId: number) => ({
  list: () => request<T[]>(`/programs/${programId}/${path}`),
  create: (data: C) => request<T>(`/programs/${programId}/${path}`, json("POST", data)),
  update: (id: number, data: U) =>
    request<T>(`/programs/${programId}/${path}/${id}`, json("PATCH", data)),
  remove: (id: number) =>
    request<void>(`/programs/${programId}/${path}/${id}`, { method: "DELETE" }),
});

export const api = {
  programs: {
    list: () => request<Program[]>("/programs"),
    get: (id: number) => request<Program>(`/programs/${id}`),
    create: (data: Partial<Program> & { name: string }) =>
      request<Program>("/programs", json("POST", data)),
    update: (id: number, data: Partial<Program>) =>
      request<Program>(`/programs/${id}`, json("PATCH", data)),
    remove: (id: number) => request<void>(`/programs/${id}`, { method: "DELETE" }),
    scopeCheck: (id: number, host: string) =>
      request<ScopeCheckResult>(`/programs/${id}/scope-check`, json("POST", { host })),
  },
  scopeRules: nested<ScopeRule, Pick<ScopeRule, "action" | "type" | "value">, Partial<ScopeRule>>("scope-rules"),
  targets: nested<
    Target,
    { value: string; description?: string | null },
    Partial<Pick<Target, "value" | "description">>
  >("targets"),
  findings: nested<Finding, Partial<Finding> & { title: string }, Partial<Finding>>("findings"),
  notes: nested<Note, Partial<Note> & { title: string }, Partial<Note>>("notes"),
  recon: {
    start: (programId: number, targets: string[]) =>
      request<ReconJob>("/recon/scans", json("POST", { program_id: programId, targets })),
    list: (programId?: number, limit?: number) => {
      const qs = new URLSearchParams();
      if (programId != null) qs.set("program_id", String(programId));
      if (limit != null) qs.set("limit", String(limit));
      const s = qs.toString();
      return request<ReconJob[]>(`/recon/scans${s ? `?${s}` : ""}`);
    },
    job: (id: number) => request<ReconJob>(`/recon/scans/${id}`),
    assets: (id: number) => request<ReconAsset[]>(`/recon/scans/${id}/assets`),
  },
  dashboard: {
    summary: () => request<DashboardSummary>("/dashboard/summary"),
  },
  settings: {
    getAI: () => request<AISettings>("/settings/ai"),
    updateAI: (data: AISettingsUpdate) =>
      request<AISettings>("/settings/ai", json("PUT", data)),
  },
  triage: {
    run: (jobId: number) => request<unknown>("/triage", json("POST", { job_id: jobId })),
  },
};
