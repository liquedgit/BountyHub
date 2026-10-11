import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ReconDashboard } from "@/components/recon/ReconDashboard";
import { ApiError } from "@/lib/api";
import { renderWithClient } from "./utils";

const m = vi.hoisted(() => ({
  recon: { start: vi.fn(), job: vi.fn(), assets: vi.fn() },
}));

vi.mock("@/lib/api", async (orig) => {
  const actual = await orig<typeof import("@/lib/api")>();
  return {
    ...actual,
    api: {
      recon: m.recon,
    },
  };
});

beforeEach(() => vi.clearAllMocks());

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
