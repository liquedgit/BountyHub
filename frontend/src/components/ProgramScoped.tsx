"use client";

import { useQuery } from "@tanstack/react-query";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect } from "react";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { ListSkeleton } from "@/components/common/ListSkeleton";
import { ProgramSelect } from "@/components/programs/ProgramSelect";
import { api } from "@/lib/api";

const STORAGE_KEY = "bountyhub:program";

function readStored(): number | null {
  try {
    const n = Number(window.localStorage.getItem(STORAGE_KEY));
    return Number.isInteger(n) && n > 0 ? n : null;
  } catch {
    return null;
  }
}

function Scoped({ render }: { render: (programId: number) => React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const { data: programs, isLoading, error, refetch } = useQuery({
    queryKey: ["programs"],
    queryFn: api.programs.list,
  });

  const raw = Number(searchParams.get("program"));
  const selected = programs?.some((p) => p.id === raw) ? raw : null;

  const select = useCallback(
    (id: number | null) => {
      const next = new URLSearchParams(searchParams.toString());
      if (id == null) next.delete("program");
      else next.set("program", String(id));
      const qs = next.toString();
      router.replace(qs ? `${pathname}?${qs}` : pathname);
    },
    [pathname, router, searchParams],
  );

  useEffect(() => {
    if (!programs) return;
    if (selected != null) {
      try {
        window.localStorage.setItem(STORAGE_KEY, String(selected));
      } catch {
        /* storage unavailable */
      }
      return;
    }
    const stored = readStored();
    if (stored != null && programs.some((p) => p.id === stored)) select(stored);
    else if (programs.length === 1) select(programs[0].id);
  }, [programs, selected, select]);

  if (isLoading) return <ListSkeleton rows={2} />;
  if (error) return <ErrorState error={error} onRetry={() => refetch()} />;
  if (!programs || programs.length === 0) {
    return (
      <EmptyState
        title="No programs yet"
        description="Create a program first, then come back to work on it."
        action={{ label: "Go to programs", href: "/programs" }}
      />
    );
  }
  return (
    <div className="space-y-4">
      <ProgramSelect value={selected} onChange={select} />
      {selected == null ? (
        <p className="text-sm text-muted-foreground">Choose a program to continue.</p>
      ) : (
        render(selected)
      )}
    </div>
  );
}

/** Page body helper: the program lives in `?program=<id>` (and localStorage); renders the feature for it. */
export function ProgramScoped({ render }: { render: (programId: number) => React.ReactNode }) {
  return (
    <Suspense fallback={<ListSkeleton rows={2} />}>
      <Scoped render={render} />
    </Suspense>
  );
}
