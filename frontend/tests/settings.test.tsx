import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AccountCard } from "@/components/settings/AccountCard";
import { AISettingsForm } from "@/components/settings/AISettingsForm";
import { renderWithClient } from "./utils";

const m = vi.hoisted(() => ({
  getAI: vi.fn(),
  updateAI: vi.fn(),
  request: vi.fn(),
  logout: vi.fn(),
  replace: vi.fn(),
  toast: { success: vi.fn(), error: vi.fn() },
}));

vi.mock("@/lib/api", async (orig) => {
  const actual = await orig<typeof import("@/lib/api")>();
  return {
    ...actual,
    request: m.request,
    api: { settings: { getAI: m.getAI, updateAI: m.updateAI } },
  };
});
vi.mock("@/features/auth/api", () => ({ logout: m.logout }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace: m.replace, refresh: vi.fn() }) }));
vi.mock("sonner", () => ({ toast: m.toast }));

const base = {
  provider: "claude",
  claude_token_set: true,
  claude_model: "claude-x",
  openai_base_url: "https://llm.example/v1",
  openai_api_key_set: false,
  openai_model: "m1",
};

beforeEach(() => vi.clearAllMocks());

describe("AISettingsForm", () => {
  it("shows saved / not set per credential and never renders a secret", async () => {
    m.getAI.mockResolvedValue({ ...base, secret: "sk-LEAKED" });
    const { container } = renderWithClient(<AISettingsForm />);
    expect(await screen.findByText("saved")).toBeInTheDocument();
    expect(screen.getByLabelText("Claude token")).toHaveValue("");
    expect(screen.getByLabelText("Claude token")).toHaveAttribute("type", "password");
    expect(container.innerHTML).not.toContain("sk-LEAKED");

    await userEvent.selectOptions(screen.getByLabelText("Provider"), "openai_compatible");
    expect(screen.getByText("not set")).toBeInTheDocument();
    expect(screen.getByLabelText("API key")).toHaveValue("");
    expect(screen.getByLabelText("Base URL")).toHaveValue("https://llm.example/v1");
  });

  it("omits blank secrets from the PUT body and toasts success", async () => {
    m.getAI.mockResolvedValue(base);
    m.updateAI.mockResolvedValue(base);
    renderWithClient(<AISettingsForm />);
    await screen.findByText("saved");
    await waitFor(() => expect(screen.getByLabelText("Claude model")).toHaveValue("claude-x"));
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(m.updateAI).toHaveBeenCalled());
    const body = m.updateAI.mock.calls[0][0];
    expect(body).not.toHaveProperty("claude_token");
    expect(body).not.toHaveProperty("openai_api_key");
    expect(body.claude_model).toBe("claude-x");
    await waitFor(() => expect(m.toast.success).toHaveBeenCalled());
  });

  it("sends provider and a typed secret when changed", async () => {
    m.getAI.mockResolvedValue(base);
    m.updateAI.mockResolvedValue({ ...base, provider: "openai_compatible", openai_api_key_set: true });
    renderWithClient(<AISettingsForm />);
    await screen.findByText("saved");
    await userEvent.selectOptions(screen.getByLabelText("Provider"), "openai_compatible");
    await userEvent.type(screen.getByLabelText("API key"), "sk-new");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(m.updateAI).toHaveBeenCalled());
    const body = m.updateAI.mock.calls[0][0];
    expect(body.provider).toBe("openai_compatible");
    expect(body.openai_api_key).toBe("sk-new");
    expect(body).not.toHaveProperty("claude_token");
    await waitFor(() => expect(screen.getByLabelText("API key")).toHaveValue(""));
  });

  it("shows the server message on failure and an error state on load failure", async () => {
    m.getAI.mockResolvedValue(base);
    m.updateAI.mockRejectedValue(new Error("token rejected"));
    renderWithClient(<AISettingsForm />);
    await screen.findByText("saved");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(m.toast.error).toHaveBeenCalledWith("token rejected"));
  });

  it("renders an error state when loading fails", async () => {
    m.getAI.mockRejectedValue(new Error("boom"));
    renderWithClient(<AISettingsForm />);
    expect(await screen.findByRole("alert")).toHaveTextContent("boom");
  });
});

describe("AccountCard", () => {
  it("shows the email and signs out", async () => {
    m.request.mockResolvedValue({ id: 1, email: "me@example.com" });
    m.logout.mockResolvedValue(undefined);
    renderWithClient(<AccountCard />);
    expect(await screen.findByText("me@example.com")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /sign out/i }));
    await waitFor(() => expect(m.replace).toHaveBeenCalledWith("/login"));
    expect(m.logout).toHaveBeenCalled();
  });
});
