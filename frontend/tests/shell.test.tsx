import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { Header } from "@/components/layout/header";
import { Sidebar } from "@/components/layout/sidebar";
import { NAV_ITEMS, SETTINGS_ITEM, isActivePath } from "@/features/dashboard/nav";

let pathname = "/programs/12";
vi.mock("next/navigation", () => ({
  usePathname: () => pathname,
  useRouter: () => ({ replace: vi.fn(), refresh: vi.fn() }),
}));
vi.mock("next-themes", () => ({ useTheme: () => ({ resolvedTheme: "dark", setTheme: vi.fn() }) }));

function renderShell() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <Sidebar />
      <Header />
    </QueryClientProvider>,
  );
}

describe("app shell", () => {
  beforeEach(() => {
    pathname = "/programs/12";
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response(JSON.stringify({ id: 1, email: "hunter@example.com" }))),
    );
  });

  it("highlights the parent of a nested route", () => {
    renderShell();
    const nav = screen.getByRole("navigation", { name: "Main" });
    const current = within(nav).getAllByRole("link").filter((l) => l.getAttribute("aria-current") === "page");
    expect(current).toHaveLength(1);
    expect(current[0]).toHaveTextContent("Programs");
  });

  it("only matches / exactly", () => {
    expect(isActivePath("/programs", "/")).toBe(false);
    expect(isActivePath("/programsx", "/programs")).toBe(false);
    expect(isActivePath("/settings", SETTINGS_ITEM.href)).toBe(true);
  });

  it("menu button opens the nav with every item", async () => {
    renderShell();
    await userEvent.click(screen.getByRole("button", { name: "Open menu" }));
    const dialog = await screen.findByRole("dialog");
    for (const item of [...NAV_ITEMS, SETTINGS_ITEM]) {
      expect(within(dialog).getByRole("link", { name: item.label })).toHaveAttribute("href", item.href);
    }
  });

  it("shows the signed-in email", async () => {
    renderShell();
    expect(await screen.findByText("hunter@example.com")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sign out" })).toBeInTheDocument();
  });
});
