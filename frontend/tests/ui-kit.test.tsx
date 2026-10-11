import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { EmptyState } from "@/components/common/EmptyState";
import { SeverityBadge } from "@/components/common/SeverityBadge";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Badge } from "@/components/ui/badge";
import { formatMoney } from "@/lib/format";

describe("ConfirmDialog", () => {
  it("calls onConfirm when confirmed", async () => {
    const onConfirm = vi.fn();
    render(
      <ConfirmDialog open onOpenChange={() => {}} title="Delete it?" confirmLabel="Delete" onConfirm={onConfirm} />,
    );
    expect(screen.getByRole("dialog")).toHaveTextContent("Delete it?");
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });

  it("closes without confirming on cancel", async () => {
    const onConfirm = vi.fn();
    const onOpenChange = vi.fn();
    render(<ConfirmDialog open onOpenChange={onOpenChange} title="Sure?" onConfirm={onConfirm} />);
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onOpenChange).toHaveBeenCalledWith(false);
    expect(onConfirm).not.toHaveBeenCalled();
  });
});

describe("EmptyState", () => {
  it("renders an action that fires onClick", async () => {
    const onClick = vi.fn();
    render(<EmptyState title="Nothing here" description="Add one" action={{ label: "Add item", onClick }} />);
    expect(screen.getByText("Nothing here")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Add item" }));
    expect(onClick).toHaveBeenCalled();
  });

  it("renders a link action", () => {
    render(<EmptyState title="None" action={{ label: "Go", href: "/programs" }} />);
    expect(screen.getByRole("link", { name: "Go" })).toHaveAttribute("href", "/programs");
  });
});

describe("badges", () => {
  it("carry their text", () => {
    render(
      <div>
        <Badge variant="success">ok</Badge>
        <SeverityBadge severity="critical" />
        <StatusBadge status="running" />
      </div>,
    );
    expect(screen.getByText("ok")).toBeInTheDocument();
    expect(screen.getByText("critical")).toBeInTheDocument();
    expect(screen.getByText("running")).toBeInTheDocument();
  });
});

describe("format", () => {
  it("formats cents as money", () => {
    expect(formatMoney(50000)).toBe("$500.00");
  });
});
