import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { FindingsBoard } from "@/components/findings/FindingsBoard";
import { NotesEditor } from "@/components/notes/NotesEditor";
import { ProgramList } from "@/components/programs/ProgramList";
import { ScopeEditor } from "@/components/programs/ScopeEditor";
import { ReconDashboard } from "@/components/recon/ReconDashboard";
import { ApiError } from "@/lib/api";
import { renderWithClient } from "./utils";

const m = vi.hoisted(() => ({
  programs: { list: vi.fn(), create: vi.fn(), get: vi.fn() },
  scope: { list: vi.fn(), create: vi.fn(), remove: vi.fn() },
  findings: { list: vi.fn(), create: vi.fn(), update: vi.fn() },
  notes: { list: vi.fn(), create: vi.fn(), update: vi.fn(), remove: vi.fn() },
  recon: { start: vi.fn(), job: vi.fn(), assets: vi.fn() },
}));

vi.mock("@/lib/api", async (orig) => {
  const actual = await orig<typeof import("@/lib/api")>();
  return {
    ...actual,
    api: {
      programs: m.programs,
      scopeRules: () => m.scope,
      findings: () => m.findings,
      notes: () => m.notes,
      recon: m.recon,
    },
  };
});

beforeEach(() => vi.clearAllMocks());

describe("ProgramList", () => {
  it("lists programs and creates one", async () => {
    m.programs.list.mockResolvedValue([
      { id: 1, name: "Acme", platform: "HackerOne", url: null, reward_info: null, created_at: "" },
    ]);
    m.programs.create.mockResolvedValue({ id: 2 });
    renderWithClient(<ProgramList />);
    expect(await screen.findByText("Acme")).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("Program name"), "Globex");
    await userEvent.click(screen.getByText("Add program"));
    await waitFor(() =>
      expect(m.programs.create).toHaveBeenCalledWith({ name: "Globex", platform: null }),
    );
  });
});

describe("ScopeEditor", () => {
  it("shows rules and adds an out-of-scope rule", async () => {
    m.scope.list.mockResolvedValue([
      { id: 1, program_id: 1, action: "in", type: "wildcard", value: "*.acme.com" },
    ]);
    m.scope.create.mockResolvedValue({});
    renderWithClient(<ScopeEditor programId={1} />);
    expect(await screen.findByText("*.acme.com")).toBeInTheDocument();
    await userEvent.selectOptions(screen.getByLabelText("Action"), "out");
    await userEvent.selectOptions(screen.getByLabelText("Type"), "domain");
    await userEvent.type(screen.getByLabelText("Scope value"), "admin.acme.com");
    await userEvent.click(screen.getByText("Add rule"));
    await waitFor(() =>
      expect(m.scope.create).toHaveBeenCalledWith({
        action: "out",
        type: "domain",
        value: "admin.acme.com",
      }),
    );
  });
});

describe("FindingsBoard", () => {
  it("groups by status, shows payout and updates status", async () => {
    m.findings.list.mockResolvedValue([
      { id: 5, program_id: 1, title: "XSS", description: null, target_id: null,
        status: "new", severity: "high", payout_cents: 50000 },
    ]);
    m.findings.update.mockResolvedValue({});
    renderWithClient(<FindingsBoard programId={1} />);
    expect(await screen.findByText("XSS")).toBeInTheDocument();
    expect(screen.getByText("$500.00")).toBeInTheDocument();
    await userEvent.selectOptions(screen.getByLabelText("Status for XSS"), "triaged");
    await waitFor(() => expect(m.findings.update).toHaveBeenCalledWith(5, { status: "triaged" }));
  });
});

describe("NotesEditor", () => {
  it("edits a note, renders markdown preview and saves", async () => {
    m.notes.list.mockResolvedValue([
      { id: 3, program_id: 1, title: "Recon notes", body_md: "# Hello", finding_id: null },
    ]);
    m.notes.update.mockResolvedValue({});
    renderWithClient(<NotesEditor programId={1} />);
    await userEvent.click(await screen.findByText("Recon notes"));
    expect(await screen.findByRole("heading", { name: "Hello" })).toBeInTheDocument();
    const area = screen.getByLabelText("Markdown");
    await userEvent.clear(area);
    await userEvent.type(area, "plain");
    await userEvent.click(screen.getByText("Save"));
    await waitFor(() =>
      expect(m.notes.update).toHaveBeenCalledWith(3, { title: "Recon notes", body_md: "plain" }),
    );
  });
});

describe("ReconDashboard", () => {
  it("launches a scan, polls status and shows scored assets by type", async () => {
    const base = {
      id: 9, program_id: 1, current_stage: "httpx", targets: ["a.acme.com"],
      rejected_targets: ["evil.com"], error: null, created_at: "", started_at: null, finished_at: null,
    };
    m.recon.start.mockResolvedValue({ ...base, status: "queued" });
    m.recon.job.mockResolvedValue({ ...base, status: "completed" });
    m.recon.assets.mockResolvedValue([
      { id: 1, asset_type: "subdomain", value: "a.acme.com", source: "subfinder", meta: {}, triage_score: 0.9 },
      { id: 2, asset_type: "secret", value: "AKIA…", source: "scanner", meta: {}, triage_score: 0.3 },
    ]);
    renderWithClient(<ReconDashboard programId={1} />);
    await userEvent.type(screen.getByLabelText("Targets"), "a.acme.com{enter}evil.com");
    await userEvent.click(screen.getByText("Launch scan"));
    expect(m.recon.start).toHaveBeenCalledWith(1, ["a.acme.com", "evil.com"]);
    await waitFor(() => expect(screen.getByTestId("job-status")).toHaveTextContent("completed"));
    expect(screen.getByTestId("rejected")).toHaveTextContent("evil.com");
    expect(await screen.findByText("0.90")).toBeInTheDocument();
    expect(screen.getByText("Secrets (1)")).toBeInTheDocument();
    expect(screen.getByText("Subdomains (1)")).toBeInTheDocument();
  });

  it("shows an error when every target is out of scope", async () => {
    m.recon.start.mockRejectedValue(
      new ApiError(422, "fail", { detail: { rejected_targets: ["evil.com"] } }),
    );
    renderWithClient(<ReconDashboard programId={1} />);
    await userEvent.type(screen.getByLabelText("Targets"), "evil.com");
    await userEvent.click(screen.getByText("Launch scan"));
    expect(await screen.findByRole("alert")).toHaveTextContent("in scope");
    expect(screen.getByTestId("rejected")).toHaveTextContent("evil.com");
  });
});
