import { screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ProgramScoped } from "@/components/ProgramScoped";
import { renderWithClient } from "./utils";

const nav = vi.hoisted(() => ({
  params: new URLSearchParams(),
  replace: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useSearchParams: () => nav.params,
  usePathname: () => "/findings",
  useRouter: () => ({ replace: nav.replace }),
}));

const m = vi.hoisted(() => ({ list: vi.fn() }));
vi.mock("@/lib/api", async (orig) => {
  const actual = await orig<typeof import("@/lib/api")>();
  return { ...actual, api: { programs: { list: m.list } } };
});

const prog = (id: number, name: string) => ({
  id, name, platform: null, url: null, reward_info: null, created_at: "", updated_at: "",
});

beforeEach(() => {
  vi.clearAllMocks();
  nav.params = new URLSearchParams();
  window.localStorage.clear();
});

describe("ProgramScoped", () => {
  it("renders the program from ?program", async () => {
    nav.params = new URLSearchParams("program=2");
    m.list.mockResolvedValue([prog(1, "Acme"), prog(2, "Globex")]);
    renderWithClient(<ProgramScoped render={(id) => <p>scoped {id}</p>} />);
    expect(await screen.findByText("scoped 2")).toBeInTheDocument();
    await waitFor(() => expect(window.localStorage.getItem("bountyhub:program")).toBe("2"));
  });

  it("auto-selects a single program", async () => {
    m.list.mockResolvedValue([prog(7, "Only")]);
    renderWithClient(<ProgramScoped render={(id) => <p>scoped {id}</p>} />);
    await waitFor(() => expect(nav.replace).toHaveBeenCalledWith("/findings?program=7"));
  });

  it("falls back to the remembered program", async () => {
    window.localStorage.setItem("bountyhub:program", "2");
    m.list.mockResolvedValue([prog(1, "Acme"), prog(2, "Globex")]);
    renderWithClient(<ProgramScoped render={(id) => <p>scoped {id}</p>} />);
    await waitFor(() => expect(nav.replace).toHaveBeenCalledWith("/findings?program=2"));
  });

  it("shows an empty state linking to /programs when there are none", async () => {
    m.list.mockResolvedValue([]);
    renderWithClient(<ProgramScoped render={() => <p>never</p>} />);
    const link = await screen.findByRole("link", { name: "Go to programs" });
    expect(link).toHaveAttribute("href", "/programs");
  });
});
