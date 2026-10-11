import { AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { errorMessage } from "@/lib/api";

export function ErrorState({
  error,
  title = "Something went wrong",
  onRetry,
}: {
  error?: unknown;
  title?: string;
  onRetry?: () => void;
}) {
  return (
    <div
      role="alert"
      className="flex flex-col items-center justify-center gap-2 rounded-lg border border-destructive/40 bg-destructive/5 p-8 text-center"
    >
      <AlertCircle className="h-6 w-6 text-destructive" aria-hidden />
      <h2 className="text-base font-medium">{title}</h2>
      {error !== undefined ? (
        <p className="max-w-md text-sm text-muted-foreground">{errorMessage(error)}</p>
      ) : null}
      {onRetry ? (
        <Button variant="outline" size="sm" onClick={onRetry}>
          Retry
        </Button>
      ) : null}
    </div>
  );
}
