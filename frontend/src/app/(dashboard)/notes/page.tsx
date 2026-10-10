"use client";

import { NotesEditor } from "@/components/notes/NotesEditor";
import { ProgramScoped } from "@/components/ProgramScoped";

export default function NotesPage() {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Notes</h1>
      <ProgramScoped render={(id) => <NotesEditor programId={id} />} />
    </div>
  );
}
