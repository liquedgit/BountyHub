import { ProgramDetail } from "@/components/programs/ProgramDetail";

export default function ProgramPage({ params }: { params: { id: string } }) {
  return <ProgramDetail programId={Number(params.id)} />;
}
