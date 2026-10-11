"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Pencil, Trash2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { ErrorState } from "@/components/common/ErrorState";
import { ListSkeleton } from "@/components/common/ListSkeleton";
import { PageHeader } from "@/components/common/PageHeader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/format";
import { ProgramFormDialog } from "./ProgramFormDialog";
import { ScopeEditor } from "./ScopeEditor";
import { TargetsEditor } from "./TargetsEditor";
import { safeHttpUrl } from "./safe-url";

export function ProgramDetail({ programId }: { programId: number }) {
  const router = useRouter();
  const qc = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const { data: program, isLoading, error, refetch } = useQuery({
    queryKey: ["program", programId],
    queryFn: () => api.programs.get(programId),
  });
  const remove = useMutation({
    mutationFn: () => api.programs.remove(programId),
    onSuccess: () => {
      qc.removeQueries({ queryKey: ["program", programId] });
      qc.invalidateQueries({ queryKey: ["programs"] });
      setConfirmDelete(false);
      router.push("/programs");
    },
  });

  const back = (
    <Button asChild variant="ghost" size="sm" className="-ml-3">
      <Link href="/programs">
        <ArrowLeft className="h-4 w-4" aria-hidden /> Programs
      </Link>
    </Button>
  );

  if (isLoading) {
    return (
      <div className="space-y-4">
        {back}
        <ListSkeleton rows={3} />
      </div>
    );
  }
  if (error || !program) {
    return (
      <div className="space-y-4">
        {back}
        <ErrorState error={error ?? undefined} title="Program not found" onRetry={() => refetch()} />
      </div>
    );
  }

  const href = safeHttpUrl(program.url);
  const q = `?program=${program.id}`;
  return (
    <div className="space-y-6">
      {back}
      <PageHeader
        title={program.name}
        description={
          <span className="flex flex-wrap items-center gap-x-3 gap-y-1">
            {program.platform ? <Badge variant="secondary">{program.platform}</Badge> : null}
            {program.reward_info ? <span>{program.reward_info}</span> : null}
            {program.url ? (
              href ? (
                <a
                  href={href}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-primary underline underline-offset-2"
                >
                  {program.url}
                </a>
              ) : (
                <span>{program.url}</span>
              )
            ) : null}
            <span>Created {formatDate(program.created_at)}</span>
          </span>
        }
        actions={
          <>
            <Button variant="outline" onClick={() => setEditing(true)}>
              <Pencil className="h-4 w-4" aria-hidden /> Edit
            </Button>
            <Button variant="destructive" onClick={() => setConfirmDelete(true)}>
              <Trash2 className="h-4 w-4" aria-hidden /> Delete
            </Button>
          </>
        }
      />
      <div className="flex flex-wrap gap-2">
        <Button asChild variant="outline" size="sm">
          <Link href={`/findings${q}`}>Findings</Link>
        </Button>
        <Button asChild variant="outline" size="sm">
          <Link href={`/notes${q}`}>Notes</Link>
        </Button>
        <Button asChild variant="outline" size="sm">
          <Link href={`/recon${q}`}>Recon</Link>
        </Button>
      </div>

      <Tabs defaultValue="scope">
        <TabsList>
          <TabsTrigger value="scope">Scope</TabsTrigger>
          <TabsTrigger value="targets">Targets</TabsTrigger>
        </TabsList>
        <TabsContent value="scope">
          <ScopeEditor programId={programId} />
        </TabsContent>
        <TabsContent value="targets">
          <TargetsEditor programId={programId} />
        </TabsContent>
      </Tabs>

      <ProgramFormDialog open={editing} onOpenChange={setEditing} program={program} />
      <ConfirmDialog
        open={confirmDelete}
        onOpenChange={setConfirmDelete}
        title="Delete program?"
        description={`“${program.name}” and its scope, targets, findings and notes will be permanently deleted.`}
        confirmLabel={remove.isPending ? "Deleting…" : "Delete program"}
        destructive
        pending={remove.isPending}
        onConfirm={() => remove.mutate()}
      />
    </div>
  );
}
