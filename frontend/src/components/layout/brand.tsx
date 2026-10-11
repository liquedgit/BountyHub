import { ShieldCheck } from "lucide-react";
import { cn } from "@/lib/utils";

export function Brand({ className }: { className?: string }) {
  return (
    <span className={cn("flex items-center gap-2 text-lg font-semibold", className)}>
      <span className="flex h-8 w-8 items-center justify-center rounded-md bg-primary text-primary-foreground">
        <ShieldCheck className="h-5 w-5" aria-hidden />
      </span>
      BountyHub
    </span>
  );
}
