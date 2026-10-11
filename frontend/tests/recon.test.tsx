import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ReconDashboard } from "@/components/recon/ReconDashboard";
import { scoreBand } from "@/components/recon/scoring";
import { ApiError } from "@/lib/api";
import { renderWithClient } from "./utils";

const m = vi.hoisted(() => ({
  recon: { start: vi.fn(), list: vi.fn(), job: vi.fn(), assets: vi.fn() },
  triage: { run: vi.fn() },
  replace: vi.fn(),
  search: { current: "" },
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: m.replace }),
  usePathname: () => "/recon",
  useSearchParams: () => new URLSearchParams(m.search.current),
}));

vi.mock("@/lib/api", async (orig) => {
  const actual = await orig<typeof import("@/lib/api")>();
  return { ...actual, api: { recon: m.recon, triage: m.triage } };
});

const base = {
  id: 9, program_id: 1, current_stage: "httpx", targets: ["a.acme.com"],
  rejected_targets: [] as string[], error: null, notes: [] as string[],
  created_at: new Date().toISOString(), started_at: null, finished_at: null, status: "completed",
};

beforeEach(() => {
  vi.clearAllMocks();
  m.search.current = "";
  m.recon.list.mockResolvedValue([]);
});

describe("ReconDashboard", () => {
  it("launches a scan, selects it, and shows scored assets by type", async () => {
    const job = { ...base, rejected_targets: ["evil.com"] };
    m.recon.start.mockResolvedValue({ ...job, status: "queued" });
    m.recon.job.mockResolvedValue(job);
    m.recon.assets.mockResolvedValue([
      { id: 1, asset_type: "subdomain", value: "a.acme.com", source: "subfinder", meta: {}, triage_score: 90, triage_label: "high", triage_reason: "admin panel" },
      { id: 2, asset_type: "secret", value: "AKIA…", source: "scanner", meta: {}, triage_score: 30, triage_label: "low", triage_reason: null },
    ]);
    m.search.current = "scan=9";
    renderWithClient(<ReconDashboard programId={1} />);
    await userEvent.type(screen.getByLabelText("Targets"), "a.acme.com{enter}evil.com");
    expect(screen.getByTestId("target-count")).toHaveTextContent("2 targets");
    await userEvent.click(screen.getByText("Launch scan"));
    expect(m.recon.start).toHaveBeenCalledWith(1, ["a.acme.com", "evil.com"]);
    expect(m.replace).toHaveBeenCalledWith("/recon?scan=9");
    await waitFor(() => expect(screen.getByTestId("job-status")).toHaveTextContent("completed"));
    expect(screen.getByTestId("rejected")).toHaveTextContent("evil.com");
    expect(await screen.findByText("90")).toBeInTheDocument();
    expect(screen.getByText("admin panel")).toBeInTheDocument();
    expect(screen.getByText("Secrets (1)")).toBeInTheDocument();
    expect(screen.getByText("Subdomains (1)")).toBeInTheDocument();
  });

  it("names rejected targets when every target is out of scope", async () => {
    m.recon.start.mockRejectedValue(
      new ApiError(422, "No targets are in scope for this program", {
        detail: "No targets are in scope for this program",
        rejected_targets: ["evil.com"],
      }),
    );
    renderWithClient(<ReconDashboard programId={1} />);
    await userEvent.type(screen.getByLabelText("Targets"), "evil.com");
    await userEvent.click(screen.getByText("Launch scan"));
    expect(await screen.findByRole("alert")).toHaveTextContent("in scope");
    expect(screen.getByTestId("rejected")).toHaveTextContent("evil.com");
  });

  it("lists history and loads the scan from ?scan", async () => {
    m.recon.list.mockResolvedValue([
      { ...base, id: 9, status: "running" },
      { ...base, id: 8, status: "failed", targets: ["a", "b"] },
    ]);
    m.recon.job.mockResolvedValue({ ...base, id: 8, status: "failed", error: "boom", notes: ["httpx missing"] });
    m.recon.assets.mockResolvedValue([]);
    m.search.current = "scan=8";
    renderWithClient(<ReconDashboard programId={1} />);
    expect(await screen.findByText("Scan #9")).toBeInTheDocument();
    expect(m.recon.list).toHaveBeenCalledWith(1);
    expect(screen.getByText("2 targets")).toBeInTheDocument();
    await waitFor(() => expect(m.recon.job).toHaveBeenCalledWith(8));
    expect(await screen.findByText(/boom/)).toBeInTheDocument();
    expect(screen.getByText(/httpx missing/)).toBeInTheDocument();
    await userEvent.click(screen.getByText("Scan #9"));
    expect(m.replace).toHaveBeenCalledWith("/recon?scan=9");
  });

  it("marks the current stage in the stepper", async () => {
    m.recon.job.mockResolvedValue({ ...base, status: "running", current_stage: "httpx" });
    m.recon.assets.mockResolvedValue([]);
    m.search.current = "scan=9";
    renderWithClient(<ReconDashboard programId={1} />);
    const steps = await screen.findByLabelText("Stages");
    const items = within(steps).getAllByRole("listitem");
    expect(items).toHaveLength(6);
    expect(items[1]).toHaveAttribute("data-state", "done");
    expect(items[2]).toHaveAttribute("aria-current", "step");
    expect(items[2]).toHaveTextContent("in progress");
    expect(items[3]).toHaveAttribute("data-state", "pending");
  });

  it("bands scores 70+/40-69/below", () => {
    expect(scoreBand(70)).toBe("high");
    expect(scoreBand(69)).toBe("medium");
    expect(scoreBand(40)).toBe("medium");
    expect(scoreBand(39)).toBe("low");
  });

  it("filters results and shows host meta in row detail", async () => {
    m.recon.job.mockResolvedValue(base);
    m.recon.assets.mockResolvedValue([
      { id: 1, asset_type: "host", value: "https://a.acme.com", source: "httpx", meta: { status_code: 200, title: "Welcome", tech: ["nginx"] }, triage_score: 55, triage_label: "medium", triage_reason: null },
      { id: 2, asset_type: "host", value: "https://b.acme.com", source: "httpx", meta: {}, triage_score: 80, triage_label: "high", triage_reason: null },
    ]);
    m.search.current = "scan=9";
    renderWithClient(<ReconDashboard programId={1} />);
    await userEvent.click(await screen.findByRole("tab", { name: "Hosts (2)" }));
    const rows = await screen.findAllByTestId("asset-row");
    expect(rows[0]).toHaveTextContent("b.acme.com"); // sorted by score
    await userEvent.type(screen.getByLabelText("Filter results"), "a.acme");
    expect(screen.getAllByTestId("asset-row")).toHaveLength(1);
    await userEvent.click(screen.getByLabelText("Details for https://a.acme.com"));
    expect(screen.getByText("Welcome")).toBeInTheDocument();
    expect(screen.getByText("nginx")).toBeInTheDocument();
  });

  it("explains a 409 when re-running triage with no AI provider", async () => {
    m.recon.job.mockResolvedValue(base);
    m.recon.assets.mockResolvedValue([]);
    m.triage.run.mockRejectedValue(new ApiError(409, "AI provider not configured"));
    m.search.current = "scan=9";
    renderWithClient(<ReconDashboard programId={1} />);
    await userEvent.click(await screen.findByText("Re-run AI triage"));
    expect(m.triage.run).toHaveBeenCalledWith(9);
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("No AI provider configured");
    expect(within(alert).getByRole("link")).toHaveAttribute("href", "/settings");
  });

  it("shows the provider's message on a 502", async () => {
    m.recon.job.mockResolvedValue(base);
    m.recon.assets.mockResolvedValue([]);
    m.triage.run.mockRejectedValue(new ApiError(502, "provider exploded"));
    m.search.current = "scan=9";
    renderWithClient(<ReconDashboard programId={1} />);
    await userEvent.click(await screen.findByText("Re-run AI triage"));
    expect(await screen.findByRole("alert")).toHaveTextContent("provider exploded");
  });
});
