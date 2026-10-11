import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { FindingsBoard } from "@/components/findings/FindingsBoard";
import { renderWithClient } from "./utils";

const m = vi.hoisted(() => ({
  findings: { list: vi.fn(), create: vi.fn(), update: vi.fn() },
}));

vi.mock("@/lib/api", async (orig) => {
  const actual = await orig<typeof import("@/lib/api")>();
  return {
    ...actual,
    api: {
      findings: () => m.findings,
    },
  };
});

beforeEach(() => vi.clearAllMocks());

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
