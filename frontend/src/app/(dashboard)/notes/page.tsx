"use client";

import { PageHeader } from "@/components/common/PageHeader";
import { NotesEditor } from "@/components/notes/NotesEditor";
import { ProgramScoped } from "@/components/ProgramScoped";

export default function NotesPage() {
  return (
    <div className="space-y-6">
      <PageHeader title="Notes" description="Markdown notes for the program, optionally linked to a finding." />
      <ProgramScoped render={(id) => <NotesEditor programId={id} />} />
    </div>
  );
}
