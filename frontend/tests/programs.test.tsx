import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ProgramDetail } from "@/components/programs/ProgramDetail";
import { ProgramList } from "@/components/programs/ProgramList";
import { ScopeEditor } from "@/components/programs/ScopeEditor";
import { TargetsEditor } from "@/components/programs/TargetsEditor";
import { ApiError } from "@/lib/api";
import { renderWithClient } from "./utils";

const m = vi.hoisted(() => ({
  push: vi.fn(),
  programs: {
    list: vi.fn(), create: vi.fn(), get: vi.fn(), update: vi.fn(), remove: vi.fn(), scopeCheck: vi.fn(),
  },
  scope: { list: vi.fn(), create: vi.fn(), remove: vi.fn() },
  targets: { list: vi.fn(), create: vi.fn(), update: vi.fn(), remove: vi.fn() },
}));

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: m.push }) }));

vi.mock("@/lib/api", async (orig) => {
  const actual = await orig<typeof import("@/lib/api")>();
  return {
    ...actual,
    api: {
      programs: m.programs,
      scopeRules: () => m.scope,
      targets: () => m.targets,
    },
  };
});

const program = {
  id: 1, name: "Acme", platform: "HackerOne", url: "https://hackerone.com/acme",
  reward_info: "$100-$5000", created_at: "2026-01-02T10:00:00Z", updated_at: "2026-01-02T10:00:00Z",
};

beforeEach(() => {
  vi.clearAllMocks();
  m.scope.list.mockResolvedValue([]);
  m.targets.list.mockResolvedValue([]);
});

describe("ProgramList", () => {
  it("lists programs and creates one with all four fields", async () => {
    m.programs.list.mockResolvedValue([program]);
    m.programs.create.mockResolvedValue({ id: 2 });
    renderWithClient(<ProgramList />);
    expect(await screen.findByText("Acme")).toBeInTheDocument();
    expect(screen.getByText("HackerOne")).toBeInTheDocument();
    expect(screen.getByText("$100-$5000")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /new program/i }));
    await userEvent.type(screen.getByLabelText("Program name"), "Globex");
    await userEvent.type(screen.getByLabelText("Platform"), "Bugcrowd");
    await userEvent.type(screen.getByLabelText("URL"), "https://bugcrowd.com/globex");
    await userEvent.type(screen.getByLabelText("Reward info"), "Up to $10k");
    await userEvent.click(screen.getByRole("button", { name: "Add program" }));
    await waitFor(() =>
      expect(m.programs.create).toHaveBeenCalledWith({
        name: "Globex",
        platform: "Bugcrowd",
        url: "https://bugcrowd.com/globex",
        reward_info: "Up to $10k",
      }),
    );
  });

  it("sends empty optional fields as null", async () => {
    m.programs.list.mockResolvedValue([program]);
    m.programs.create.mockResolvedValue({ id: 2 });
    renderWithClient(<ProgramList />);
    await screen.findByText("Acme");
    await userEvent.click(screen.getByRole("button", { name: /new program/i }));
    await userEvent.type(screen.getByLabelText("Program name"), "Globex");
    await userEvent.click(screen.getByRole("button", { name: "Add program" }));
    await waitFor(() =>
      expect(m.programs.create).toHaveBeenCalledWith({
        name: "Globex", platform: null, url: null, reward_info: null,
      }),
    );
  });

  it("filters by search", async () => {
    m.programs.list.mockResolvedValue([program, { ...program, id: 2, name: "Globex", platform: null }]);
    renderWithClient(<ProgramList />);
    await screen.findByText("Globex");
    await userEvent.type(screen.getByLabelText("Search programs"), "glob");
    expect(screen.queryByText("Acme")).not.toBeInTheDocument();
    expect(screen.getByText("Globex")).toBeInTheDocument();
  });

  it("shows the empty state and the error state", async () => {
    m.programs.list.mockResolvedValue([]);
    const { unmount } = renderWithClient(<ProgramList />);
    expect(await screen.findByText("No programs yet")).toBeInTheDocument();
    unmount();
    m.programs.list.mockRejectedValue(new ApiError(500, "db down"));
    renderWithClient(<ProgramList />);
    expect(await screen.findByText("db down")).toBeInTheDocument();
  });

  it("shows the server message when create fails", async () => {
    m.programs.list.mockResolvedValue([program]);
    m.programs.create.mockRejectedValue(new ApiError(422, "name: already exists"));
    renderWithClient(<ProgramList />);
    await screen.findByText("Acme");
    await userEvent.click(screen.getByRole("button", { name: /new program/i }));
    await userEvent.type(screen.getByLabelText("Program name"), "Acme");
    await userEvent.click(screen.getByRole("button", { name: "Add program" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("name: already exists");
  });
});

describe("ProgramDetail", () => {
  it("renders an https url as a safe external link", async () => {
    m.programs.get.mockResolvedValue(program);
    renderWithClient(<ProgramDetail programId={1} />);
    const link = await screen.findByRole("link", { name: "https://hackerone.com/acme" });
    expect(link).toHaveAttribute("href", "https://hackerone.com/acme");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
    expect(screen.getByRole("link", { name: "Findings" })).toHaveAttribute("href", "/findings?program=1");
    expect(screen.getByRole("link", { name: "Notes" })).toHaveAttribute("href", "/notes?program=1");
    expect(screen.getByRole("link", { name: "Recon" })).toHaveAttribute("href", "/recon?program=1");
  });

  it("does not render a javascript: url as a link", async () => {
    m.programs.get.mockResolvedValue({ ...program, url: "javascript:alert(1)" });
    renderWithClient(<ProgramDetail programId={1} />);
    expect(await screen.findByText("javascript:alert(1)")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "javascript:alert(1)" })).not.toBeInTheDocument();
    expect(document.querySelector('a[href^="javascript"]')).toBeNull();
  });

  it("edits the program", async () => {
    m.programs.get.mockResolvedValue(program);
    m.programs.update.mockResolvedValue(program);
    renderWithClient(<ProgramDetail programId={1} />);
    await userEvent.click(await screen.findByRole("button", { name: /edit/i }));
    const reward = screen.getByLabelText("Reward info");
    await userEvent.clear(reward);
    await userEvent.type(reward, "$1 - $2");
    await userEvent.click(screen.getByRole("button", { name: "Save changes" }));
    await waitFor(() =>
      expect(m.programs.update).toHaveBeenCalledWith(1, {
        name: "Acme", platform: "HackerOne", url: "https://hackerone.com/acme", reward_info: "$1 - $2",
      }),
    );
  });

  it("deletes after confirmation and goes to /programs", async () => {
    m.programs.get.mockResolvedValue(program);
    m.programs.remove.mockResolvedValue(undefined);
    renderWithClient(<ProgramDetail programId={1} />);
    await userEvent.click(await screen.findByRole("button", { name: /^delete$/i }));
    expect(m.programs.remove).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Delete program" }));
    await waitFor(() => expect(m.programs.remove).toHaveBeenCalledWith(1));
    await waitFor(() => expect(m.push).toHaveBeenCalledWith("/programs"));
  });

  it("shows the targets tab", async () => {
    m.programs.get.mockResolvedValue(program);
    m.targets.list.mockResolvedValue([
      { id: 1, program_id: 1, value: "app.acme.com", description: null, created_at: "", updated_at: "" },
    ]);
    renderWithClient(<ProgramDetail programId={1} />);
    await userEvent.click(await screen.findByRole("tab", { name: "Targets" }));
    expect(await screen.findByText("app.acme.com")).toBeInTheDocument();
  });
});

describe("ScopeEditor", () => {
  it("shows rules grouped and adds an out-of-scope rule", async () => {
    m.scope.list.mockResolvedValue([
      { id: 1, program_id: 1, action: "in", type: "wildcard", value: "*.acme.com" },
    ]);
    m.scope.create.mockResolvedValue({});
    renderWithClient(<ScopeEditor programId={1} />);
    expect(await screen.findByText("*.acme.com")).toBeInTheDocument();
    await userEvent.selectOptions(screen.getByLabelText("Action"), "out");
    await userEvent.selectOptions(screen.getByLabelText("Type"), "domain");
    expect(screen.getByText(/exact hostname/i)).toBeInTheDocument();
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

  it("removes a rule only after confirmation", async () => {
    m.scope.list.mockResolvedValue([
      { id: 7, program_id: 1, action: "out", type: "domain", value: "admin.acme.com" },
    ]);
    m.scope.remove.mockResolvedValue(undefined);
    renderWithClient(<ScopeEditor programId={1} />);
    await userEvent.click(await screen.findByRole("button", { name: "Delete admin.acme.com" }));
    expect(m.scope.remove).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Delete rule" }));
    await waitFor(() => expect(m.scope.remove).toHaveBeenCalledWith(7));
  });

  it("shows the scope-check verdict and reason", async () => {
    m.programs.scopeCheck.mockResolvedValue({
      host: "admin.acme.com", in_scope: false, reason: "matched out-of-scope rule admin.acme.com",
    });
    renderWithClient(<ScopeEditor programId={1} />);
    await userEvent.type(await screen.findByLabelText("Host to test"), "admin.acme.com");
    await userEvent.click(screen.getByRole("button", { name: "Check scope" }));
    expect(m.programs.scopeCheck).toHaveBeenCalledWith(1, "admin.acme.com");
    const status = await screen.findByRole("status");
    expect(within(status).getByText("Out of scope")).toBeInTheDocument();
    expect(within(status).getByText(/matched out-of-scope rule/)).toBeInTheDocument();
  });
});

describe("TargetsEditor", () => {
  const t = { id: 3, program_id: 1, value: "app.acme.com", description: "Web app", created_at: "", updated_at: "" };

  it("creates a target", async () => {
    m.targets.create.mockResolvedValue({});
    renderWithClient(<TargetsEditor programId={1} />);
    expect(await screen.findByText("No targets yet")).toBeInTheDocument();
    await userEvent.click(screen.getAllByRole("button", { name: "Add target" })[0]);
    await userEvent.type(screen.getByLabelText("Target value"), "api.acme.com");
    await userEvent.type(screen.getByLabelText("Description"), "API");
    await userEvent.click(screen.getByRole("button", { name: "Add" }));
    await waitFor(() =>
      expect(m.targets.create).toHaveBeenCalledWith({ value: "api.acme.com", description: "API" }),
    );
  });

  it("edits a target", async () => {
    m.targets.list.mockResolvedValue([t]);
    m.targets.update.mockResolvedValue({});
    renderWithClient(<TargetsEditor programId={1} />);
    await userEvent.click(await screen.findByRole("button", { name: "Edit target app.acme.com" }));
    const desc = screen.getByLabelText("Description");
    expect(desc).toHaveValue("Web app");
    await userEvent.clear(desc);
    await userEvent.type(desc, "Main app");
    await userEvent.click(screen.getByRole("button", { name: "Save target" }));
    await waitFor(() =>
      expect(m.targets.update).toHaveBeenCalledWith(3, { value: "app.acme.com", description: "Main app" }),
    );
  });

  it("deletes a target after confirmation", async () => {
    m.targets.list.mockResolvedValue([t]);
    m.targets.remove.mockResolvedValue(undefined);
    renderWithClient(<TargetsEditor programId={1} />);
    await userEvent.click(await screen.findByRole("button", { name: "Delete target app.acme.com" }));
    await userEvent.click(screen.getByRole("button", { name: "Delete target" }));
    await waitFor(() => expect(m.targets.remove).toHaveBeenCalledWith(3));
  });
});
