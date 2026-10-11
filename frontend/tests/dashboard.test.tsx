import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { DashboardOverview } from "@/components/dashboard/DashboardOverview";
import type { DashboardSummary } from "@/lib/types";
import { renderWithClient } from "./utils";

const m = vi.hoisted(() => ({ summary: vi.fn() }));

vi.mock("@/lib/api", async (orig) => {
  const actual = await orig<typeof import("@/lib/api")>();
  return { ...actual, api: { dashboard: { summary: m.summary } } };
});

const SUMMARY: DashboardSummary = {
  programs: 3,
  targets: 9,
  notes: 2,
  findings: {
    total: 12,
    open: 7,
    by_status: { new: 4, triaged: 3, submitted: 0, accepted: 0, duplicate: 0, rejected: 0, resolved: 0, paid: 5 },
    by_severity: { critical: 1, high: 4, medium: 3, low: 2, info: 2 },
  },
  payout_cents_paid: 123456,
  scans: { total: 8, active: 2 },
  ai_configured: true,
  recent_findings: [
    { id: 1, program_id: 4, program_name: "Acme", title: "Stored XSS", severity: "high", status: "new",
      updated_at: new Date().toISOString() },
  ],
  recent_scans: [
    { id: 9, program_id: 4, program_name: "Acme", status: "running", current_stage: "httpx", target_count: 2,
      created_at: new Date().toISOString(), finished_at: null },
  ],
};

beforeEach(() => vi.clearAllMocks());

describe("DashboardOverview", () => {
  it("renders numbers, money, bars and links from the summary", async () => {
    m.summary.mockResolvedValue(SUMMARY);
    renderWithClient(<DashboardOverview />);
    expect(await screen.findByText("$1,234.56")).toBeInTheDocument();
    expect(screen.getByText("7")).toBeInTheDocument();
    expect(screen.getByText("12 total")).toBeInTheDocument();
    expect(screen.getByTestId("bar-high")).toHaveStyle({ width: "100%" });
    expect(screen.getByTestId("bar-critical")).toHaveStyle({ width: "25%" });
    expect(screen.getByRole("link", { name: "Stored XSS" })).toHaveAttribute("href", "/findings?program=4");
    expect(screen.getByRole("link", { name: /scan #9/ })).toHaveAttribute("href", "/recon?program=4&scan=9");
    expect(screen.queryByText(/AI provider not configured/)).not.toBeInTheDocument();
    expect(screen.queryByText("Getting started")).not.toBeInTheDocument();
  });

  it("shows the getting-started checklist and AI callout on an empty summary", async () => {
    m.summary.mockResolvedValue({
      ...SUMMARY, programs: 0, ai_configured: false, recent_findings: [], recent_scans: [],
    });
    renderWithClient(<DashboardOverview />);
    expect(await screen.findByText("Getting started")).toBeInTheDocument();
    for (const label of ["Create a program", "Add scope rules", "Configure the AI provider", "Run a scan"]) {
      expect(screen.getByRole("link", { name: label })).toBeInTheDocument();
    }
    expect(screen.getByText(/AI provider not configured/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Configure it in Settings/ })).toHaveAttribute("href", "/settings");
  });

  it("shows an error state and retries", async () => {
    m.summary.mockRejectedValueOnce(new Error("boom")).mockResolvedValue(SUMMARY);
    renderWithClient(<DashboardOverview />);
    expect(await screen.findByRole("alert")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByText("$1,234.56")).toBeInTheDocument();
    expect(m.summary).toHaveBeenCalledTimes(2);
  });
});
