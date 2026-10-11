import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { NotesEditor } from "@/components/notes/NotesEditor";
import { renderWithClient } from "./utils";

const m = vi.hoisted(() => ({
  notes: { list: vi.fn(), create: vi.fn(), update: vi.fn(), remove: vi.fn() },
}));

vi.mock("@/lib/api", async (orig) => {
  const actual = await orig<typeof import("@/lib/api")>();
  return {
    ...actual,
    api: {
      notes: () => m.notes,
    },
  };
});

beforeEach(() => vi.clearAllMocks());

describe("NotesEditor", () => {
  it("edits a note, renders markdown preview and saves", async () => {
    m.notes.list.mockResolvedValue([
      { id: 3, program_id: 1, title: "Recon notes", body_md: "# Hello", finding_id: null },
    ]);
    m.notes.update.mockResolvedValue({});
    renderWithClient(<NotesEditor programId={1} />);
    await userEvent.click(await screen.findByText("Recon notes"));
    expect(await screen.findByRole("heading", { name: "Hello" })).toBeInTheDocument();
    const area = screen.getByLabelText("Markdown");
    await userEvent.clear(area);
    await userEvent.type(area, "plain");
    await userEvent.click(screen.getByText("Save"));
    await waitFor(() =>
      expect(m.notes.update).toHaveBeenCalledWith(3, { title: "Recon notes", body_md: "plain" }),
    );
  });
});
