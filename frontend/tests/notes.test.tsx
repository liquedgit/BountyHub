import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { NotesEditor } from "@/components/notes/NotesEditor";
import { renderWithClient } from "./utils";

const m = vi.hoisted(() => ({
  notes: { list: vi.fn(), create: vi.fn(), update: vi.fn(), remove: vi.fn() },
  findings: { list: vi.fn() },
}));

vi.mock("@/lib/api", async (orig) => {
  const actual = await orig<typeof import("@/lib/api")>();
  return {
    ...actual,
    api: {
      notes: () => m.notes,
      findings: () => m.findings,
    },
  };
});

beforeEach(() => {
  vi.clearAllMocks();
  m.findings.list.mockResolvedValue([{ id: 7, program_id: 1, title: "XSS in search" }]);
});

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

  const notes = [
    { id: 3, program_id: 1, title: "Recon notes", body_md: "# Hello", finding_id: null,
      created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-02T00:00:00Z" },
    { id: 4, program_id: 1, title: "Other", body_md: "x", finding_id: null,
      created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-02T00:00:00Z" },
  ];

  it("tracks dirty state and disables Save when clean", async () => {
    m.notes.list.mockResolvedValue(notes);
    renderWithClient(<NotesEditor programId={1} />);
    await userEvent.click(await screen.findByText("Recon notes"));
    expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();
    expect(screen.getByText("All changes saved")).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("Markdown"), "!");
    expect(screen.getByText("Unsaved changes")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save" })).toBeEnabled();
  });

  it("saves with Ctrl+S", async () => {
    m.notes.list.mockResolvedValue(notes);
    m.notes.update.mockResolvedValue({});
    renderWithClient(<NotesEditor programId={1} />);
    await userEvent.click(await screen.findByText("Recon notes"));
    await userEvent.type(screen.getByLabelText("Markdown"), "!");
    await userEvent.keyboard("{Control>}s{/Control}");
    await waitFor(() => expect(m.notes.update).toHaveBeenCalledWith(3, { title: "Recon notes", body_md: "# Hello!" }));
  });

  it("confirms before switching away from unsaved edits", async () => {
    m.notes.list.mockResolvedValue(notes);
    renderWithClient(<NotesEditor programId={1} />);
    await userEvent.click(await screen.findByText("Recon notes"));
    await userEvent.type(screen.getByLabelText("Markdown"), "!");
    await userEvent.click(screen.getByText("Other"));
    expect(screen.getByText("Discard unsaved changes?")).toBeInTheDocument();
    expect(screen.getByLabelText("Note title")).toHaveValue("Recon notes");
    await userEvent.click(screen.getByRole("button", { name: "Discard changes" }));
    await waitFor(() => expect(screen.getByLabelText("Note title")).toHaveValue("Other"));
  });

  it("deletes a note after confirmation", async () => {
    m.notes.list.mockResolvedValue(notes);
    m.notes.remove.mockResolvedValue(undefined);
    renderWithClient(<NotesEditor programId={1} />);
    await userEvent.click(await screen.findByText("Recon notes"));
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));
    expect(m.notes.remove).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Delete note" }));
    await waitFor(() => expect(m.notes.remove).toHaveBeenCalledWith(3));
  });

  it("saves a link to a finding", async () => {
    m.notes.list.mockResolvedValue(notes);
    m.notes.update.mockResolvedValue({});
    renderWithClient(<NotesEditor programId={1} />);
    await userEvent.click(await screen.findByText("Recon notes"));
    await userEvent.selectOptions(await screen.findByLabelText("Linked finding"), "7");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() =>
      expect(m.notes.update).toHaveBeenCalledWith(3, {
        title: "Recon notes", body_md: "# Hello", finding_id: 7,
      }),
    );
  });

  it("filters the list by search", async () => {
    m.notes.list.mockResolvedValue(notes);
    renderWithClient(<NotesEditor programId={1} />);
    await screen.findByText("Other");
    await userEvent.type(screen.getByLabelText("Search notes"), "recon");
    expect(screen.queryByText("Other")).not.toBeInTheDocument();
    expect(screen.getByText("Recon notes")).toBeInTheDocument();
  });
});
