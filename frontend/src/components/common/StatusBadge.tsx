import { Badge, type BadgeProps } from "@/components/ui/badge";

const VARIANT: Record<string, BadgeProps["variant"]> = {
  // finding status
  new: "info",
  triaged: "secondary",
  submitted: "warning",
  accepted: "success",
  duplicate: "outline",
  rejected: "destructive",
  resolved: "success",
  paid: "success",
  // job status
  queued: "secondary",
  running: "info",
  completed: "success",
  failed: "destructive",
};

/** Finding status or recon job status; the text always carries the meaning. */
export function StatusBadge({ status }: { status: string }) {
  return <Badge variant={VARIANT[status] ?? "secondary"}>{status}</Badge>;
}
