import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { FindingsBoard } from "@/components/findings/FindingsBoard";
import { renderWithClient } from "./utils";

const m = vi.hoisted(() => ({
  findings: { list: vi.fn(), create: vi.fn(), update: vi.fn(), remove: vi.fn() },
  targets: { list: vi.fn() },
}));

vi.mock("@/lib/api", async (orig) => {
  const actual = await orig<typeof import("@/lib/api")>();
  return {
    ...actual,
    api: {
      findings: () => m.findings,
      targets: () => m.targets,
    },
  };
});

const finding = (over: Record<string, unknown> = {}) => ({
  id: 5, program_id: 1, title: "XSS", description: "details", target_id: null,
  status: "new", severity: "high", payout_cents: 50000,
  created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-02T00:00:00Z", ...over,
});

beforeEach(() => {
  vi.clearAllMocks();
  m.targets.list.mockResolvedValue([{ id: 9, program_id: 1, value: "app.example.com" }]);
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

  it("edits a finding, sending payout in cents", async () => {
    m.findings.list.mockResolvedValue([finding()]);
    m.findings.update.mockResolvedValue({});
    renderWithClient(<FindingsBoard programId={1} />);
    await userEvent.click(await screen.findByRole("button", { name: "XSS" }));
    const title = screen.getByLabelText("Title");
    await userEvent.clear(title);
    await userEvent.type(title, "Stored XSS");
    await userEvent.selectOptions(screen.getByLabelText("Severity"), "critical");
    const payout = screen.getByLabelText("Payout (USD)");
    await userEvent.clear(payout);
    await userEvent.type(payout, "1250.5");
    await userEvent.click(screen.getByRole("button", { name: "Save changes" }));
    await waitFor(() =>
      expect(m.findings.update).toHaveBeenCalledWith(
        5,
        expect.objectContaining({
          title: "Stored XSS", severity: "critical", payout_cents: 125050, description: "details",
        }),
      ),
    );
  });

  it("rejects an invalid payout", async () => {
    m.findings.list.mockResolvedValue([finding()]);
    renderWithClient(<FindingsBoard programId={1} />);
    await userEvent.click(await screen.findByRole("button", { name: "XSS" }));
    const payout = screen.getByLabelText("Payout (USD)");
    await userEvent.clear(payout);
    await userEvent.type(payout, "12.345");
    expect(screen.getByText(/Enter a dollar amount/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Save changes" }));
    expect(m.findings.update).not.toHaveBeenCalled();
  });

  it("deletes a finding after confirmation", async () => {
    m.findings.list.mockResolvedValue([finding()]);
    m.findings.remove.mockResolvedValue(undefined);
    renderWithClient(<FindingsBoard programId={1} />);
    await userEvent.click(await screen.findByRole("button", { name: "XSS" }));
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));
    expect(m.findings.remove).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Delete finding" }));
    await waitFor(() => expect(m.findings.remove).toHaveBeenCalledWith(5));
  });

  it("filters by severity and shows totals", async () => {
    m.findings.list.mockResolvedValue([
      finding(),
      finding({ id: 6, title: "Open redirect", severity: "low", status: "paid", payout_cents: 10000 }),
    ]);
    renderWithClient(<FindingsBoard programId={1} />);
    expect(await screen.findByText("Open redirect")).toBeInTheDocument();
    expect(screen.getByText("Paid total")).toBeInTheDocument();
    expect(screen.getAllByText("$100.00").length).toBeGreaterThan(1);
    await userEvent.selectOptions(screen.getByLabelText("Filter by severity"), "low");
    expect(screen.queryByText("XSS")).not.toBeInTheDocument();
    expect(screen.getByText("Open redirect")).toBeInTheDocument();
  });

  it("creates a finding from the dialog", async () => {
    m.findings.list.mockResolvedValue([]);
    m.findings.create.mockResolvedValue({});
    renderWithClient(<FindingsBoard programId={1} />);
    await userEvent.click(await screen.findByRole("button", { name: "New finding" }));
    await userEvent.type(screen.getByLabelText("Title"), "SQLi");
    await userEvent.click(screen.getByRole("button", { name: "Create finding" }));
    await waitFor(() =>
      expect(m.findings.create).toHaveBeenCalledWith(
        expect.objectContaining({ title: "SQLi", payout_cents: null }),
      ),
    );
  });

  it("shows the server message when a save fails", async () => {
    m.findings.list.mockResolvedValue([finding()]);
    m.findings.update.mockRejectedValue(new Error("Title too long"));
    renderWithClient(<FindingsBoard programId={1} />);
    await userEvent.click(await screen.findByRole("button", { name: "XSS" }));
    await userEvent.click(screen.getByRole("button", { name: "Save changes" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Title too long");
  });
});
