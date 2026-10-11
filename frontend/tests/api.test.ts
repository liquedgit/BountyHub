import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api, ApiError, errorMessage } from "@/lib/api";

function respond(status: number, body?: unknown) {
  return vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    statusText: "Status",
    json: async () => {
      if (body === undefined) throw new Error("no body");
      return body;
    },
  });
}

const assign = vi.fn();

beforeEach(() => {
  assign.mockClear();
  Object.defineProperty(window, "location", {
    value: { pathname: "/findings", search: "?program=2", assign },
    writable: true,
  });
});
afterEach(() => vi.unstubAllGlobals());

describe("api client", () => {
  it("uses a string detail as the message", async () => {
    vi.stubGlobal("fetch", respond(404, { detail: "Program not found" }));
    const err = await api.programs.get(1).catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(404);
    expect(err.message).toBe("Program not found");
    expect(err.body).toEqual({ detail: "Program not found" });
    expect(errorMessage(err)).toBe("Program not found");
  });

  it("joins a validation-list detail", async () => {
    vi.stubGlobal(
      "fetch",
      respond(422, {
        detail: [
          { loc: ["body", "name"], msg: "Field required", type: "missing" },
          { loc: ["body", "url"], msg: "Invalid URL", type: "value_error" },
        ],
      }),
    );
    const err = await api.programs.create({ name: "" }).catch((e) => e);
    expect(err.message).toBe("name: Field required; url: Invalid URL");
  });

  it("redirects to /login?next= on 401", async () => {
    vi.stubGlobal("fetch", respond(401, { detail: "Not authenticated" }));
    await expect(api.programs.list()).rejects.toBeInstanceOf(ApiError);
    expect(assign).toHaveBeenCalledWith("/login?next=%2Ffindings%3Fprogram%3D2");
  });

  it("does not redirect for the login call", async () => {
    vi.stubGlobal("fetch", respond(401, { detail: "Bad credentials" }));
    const { request } = await import("@/lib/api");
    await expect(request("/auth/login", { method: "POST" })).rejects.toThrow("Bad credentials");
    expect(assign).not.toHaveBeenCalled();
  });

  it("returns undefined for 204", async () => {
    vi.stubGlobal("fetch", respond(204));
    await expect(api.programs.remove(1)).resolves.toBeUndefined();
  });

  it("builds the recon list query", async () => {
    const f = respond(200, []);
    vi.stubGlobal("fetch", f);
    await api.recon.list(3);
    expect(f.mock.calls[0][0]).toBe("/api/backend/recon/scans?program_id=3");
  });
});
