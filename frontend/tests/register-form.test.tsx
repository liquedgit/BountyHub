import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { RegisterForm } from "@/components/auth/register-form";

const replace = vi.fn();
const refresh = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace, refresh }) }));

function renderForm() {
  const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <RegisterForm />
    </QueryClientProvider>,
  );
}

async function fill(password: string, confirm: string) {
  await userEvent.type(screen.getByLabelText("Email"), "me@example.com");
  await userEvent.type(screen.getByLabelText("Password"), password);
  await userEvent.type(screen.getByLabelText("Confirm password"), confirm);
  await userEvent.click(screen.getByRole("button", { name: /create account/i }));
}

describe("RegisterForm", () => {
  beforeEach(() => {
    replace.mockReset();
    refresh.mockReset();
    vi.stubGlobal("fetch", vi.fn());
  });

  it("registers, then logs in and navigates home", async () => {
    vi.mocked(fetch).mockResolvedValue(new Response("{}", { status: 200 }));
    renderForm();
    await fill("longenough", "longenough");

    await waitFor(() => expect(replace).toHaveBeenCalledWith("/"));
    const calls = vi.mocked(fetch).mock.calls;
    expect(calls.map((c) => c[0])).toEqual(["/api/backend/auth/register", "/api/auth/login"]);
    expect(JSON.parse((calls[0][1] as RequestInit).body as string)).toEqual({
      email: "me@example.com",
      password: "longenough",
    });
  });

  it("shows a mismatch error without calling the backend", async () => {
    renderForm();
    await fill("longenough", "different1");
    expect(await screen.findByRole("alert")).toHaveTextContent("Passwords do not match");
    expect(fetch).not.toHaveBeenCalled();
  });

  it("shows the closed-registration message with a sign-in link on 403", async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(JSON.stringify({ detail: "Registration is closed" }), { status: 403 }),
    );
    renderForm();
    await fill("longenough", "longenough");

    expect(await screen.findByRole("alert")).toHaveTextContent("An account already exists");
    expect(screen.getByRole("link", { name: /sign in/i })).toHaveAttribute("href", "/login");
    expect(replace).not.toHaveBeenCalled();
  });

  it("shows the validation message on 422", async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(JSON.stringify({ detail: [{ msg: "String should have at least 8 characters" }] }), {
        status: 422,
      }),
    );
    renderForm();
    await fill("longenough", "longenough");
    expect(await screen.findByRole("alert")).toHaveTextContent("at least 8 characters");
  });
});
