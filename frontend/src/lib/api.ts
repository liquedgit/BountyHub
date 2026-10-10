import { API_BASE as BASE } from "./api-client";
import type {
  Finding, Note, Program, ReconAsset, ReconJob, ScopeRule,
} from "./types";

export class ApiError extends Error {
  constructor(public status: number, message: string, public body?: unknown) {
    super(message);
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
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
    throw new ApiError(res.status, `Request failed (${res.status})`, body);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

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
  },
  scopeRules: nested<ScopeRule, Pick<ScopeRule, "action" | "type" | "value">, Partial<ScopeRule>>("scope-rules"),
  findings: nested<Finding, Partial<Finding> & { title: string }, Partial<Finding>>("findings"),
  notes: nested<Note, Partial<Note> & { title: string }, Partial<Note>>("notes"),
  recon: {
    start: (programId: number, targets: string[]) =>
      request<ReconJob>("/recon/scans", json("POST", { program_id: programId, targets })),
    job: (id: number) => request<ReconJob>(`/recon/scans/${id}`),
    assets: (id: number) => request<ReconAsset[]>(`/recon/scans/${id}/assets`),
  },
};
