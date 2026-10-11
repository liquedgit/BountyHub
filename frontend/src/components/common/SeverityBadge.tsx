import { Badge, type BadgeProps } from "@/components/ui/badge";
import type { Severity } from "@/lib/types";

const VARIANT: Record<Severity, BadgeProps["variant"]> = {
  info: "info",
  low: "secondary",
  medium: "warning",
  high: "destructive",
  critical: "default",
};

export function SeverityBadge({ severity }: { severity: Severity }) {
  const critical = severity === "critical";
  return (
    <Badge variant={VARIANT[severity] ?? "secondary"} className={critical ? "bg-destructive text-destructive-foreground" : undefined}>
      {severity}
    </Badge>
  );
}
