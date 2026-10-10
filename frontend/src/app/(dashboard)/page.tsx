import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export default function OverviewPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Overview</h1>
      <Card>
        <CardHeader>
          <CardTitle>Welcome to BountyHub</CardTitle>
          <CardDescription>Programs, findings, notes and recon will appear here.</CardDescription>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">
          Recon only runs against assets you have marked in-scope for a program.
        </CardContent>
      </Card>
    </div>
  );
}
