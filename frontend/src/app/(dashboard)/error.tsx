"use client";

import { ErrorState } from "@/components/common/ErrorState";

export default function DashboardError({ error, reset }: { error: Error; reset: () => void }) {
  return <ErrorState error={error} title="This page could not be displayed" onRetry={reset} />;
}
