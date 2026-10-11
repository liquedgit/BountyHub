import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ProgramList } from "@/components/programs/ProgramList";
import { ScopeEditor } from "@/components/programs/ScopeEditor";
import { renderWithClient } from "./utils";

const m = vi.hoisted(() => ({
  programs: { list: vi.fn(), create: vi.fn(), get: vi.fn() },
  scope: { list: vi.fn(), create: vi.fn(), remove: vi.fn() },
}));

vi.mock("@/lib/api", async (orig) => {
  const actual = await orig<typeof import("@/lib/api")>();
  return {
    ...actual,
    api: {
      programs: m.programs,
      scopeRules: () => m.scope,
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
