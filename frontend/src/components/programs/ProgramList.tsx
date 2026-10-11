"use client";

import { useQuery } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { ListSkeleton } from "@/components/common/ListSkeleton";
import { PageHeader } from "@/components/common/PageHeader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/format";
import { ProgramFormDialog } from "./ProgramFormDialog";

export function ProgramList() {
  const [creating, setCreating] = useState(false);
  const [search, setSearch] = useState("");
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["programs"],
    queryFn: api.programs.list,
  });

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q || !data) return data ?? [];
    return data.filter((p) =>
      [p.name, p.platform, p.reward_info].some((v) => v?.toLowerCase().includes(q)),
    );
  }, [data, search]);

  return (
    <section className="space-y-4">
      <PageHeader
        title="Programs"
        description="Bounty programs you are working on."
        actions={
          <Button onClick={() => setCreating(true)}>
            <Plus className="h-4 w-4" aria-hidden /> New program
          </Button>
        }
      />
      <ProgramFormDialog open={creating} onOpenChange={setCreating} />

      {isLoading ? (
        <ListSkeleton />
      ) : error ? (
        <ErrorState error={error} title="Failed to load programs" onRetry={() => refetch()} />
      ) : data && data.length === 0 ? (
        <EmptyState
          title="No programs yet"
          description="Create your first program to start defining scope and running recon."
          action={{ label: "New program", onClick: () => setCreating(true) }}
        />
      ) : (
        <>
          <Input
            aria-label="Search programs"
            placeholder="Search programs…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="max-w-sm"
          />
          {filtered.length === 0 ? (
            <EmptyState title="No matching programs" description={`Nothing matches “${search.trim()}”.`} />
          ) : (
            <div className="overflow-x-auto rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>Platform</TableHead>
                    <TableHead>Reward</TableHead>
                    <TableHead>Created</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filtered.map((p) => (
                    <TableRow key={p.id}>
                      <TableCell>
                        <Link href={`/programs/${p.id}`} className="font-medium hover:underline">
                          {p.name}
                        </Link>
                      </TableCell>
                      <TableCell>
                        {p.platform ? <Badge variant="secondary">{p.platform}</Badge> : "—"}
                      </TableCell>
                      <TableCell className="text-muted-foreground">{p.reward_info ?? "—"}</TableCell>
                      <TableCell className="whitespace-nowrap text-muted-foreground">
                        {formatDate(p.created_at)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </>
      )}
    </section>
  );
}
