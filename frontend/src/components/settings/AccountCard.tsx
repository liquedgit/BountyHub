"use client";

import { useQuery } from "@tanstack/react-query";
import { LogOut } from "lucide-react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { logout } from "@/features/auth/api";
import { errorMessage, request } from "@/lib/api";

export function AccountCard() {
  const router = useRouter();
  const { data, isLoading, error } = useQuery({
    queryKey: ["auth", "me"],
    queryFn: () => request<{ id: number; email: string }>("/auth/me"),
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle>Account</CardTitle>
        <CardDescription>The account you are signed in with.</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0 text-sm">
          {isLoading ? (
            <Skeleton className="h-5 w-48" aria-label="Loading account" />
          ) : error ? (
            <span className="text-destructive">{errorMessage(error)}</span>
          ) : (
            <>
              <span className="text-muted-foreground">Signed in as </span>
              <span className="break-all font-medium">{data?.email}</span>
            </>
          )}
        </div>
        <Button
          variant="outline"
          onClick={async () => {
            await logout();
            router.replace("/login");
            router.refresh();
          }}
        >
          <LogOut className="h-4 w-4" /> Sign out
        </Button>
      </CardContent>
    </Card>
  );
}
