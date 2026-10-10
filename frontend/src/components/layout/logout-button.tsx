"use client";

import { LogOut } from "lucide-react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { logout } from "@/features/auth/api";

export function LogoutButton() {
  const router = useRouter();
  return (
    <Button
      variant="ghost"
      size="sm"
      onClick={async () => {
        await logout();
        router.replace("/login");
        router.refresh();
      }}
    >
      <LogOut className="h-4 w-4" /> Sign out
    </Button>
  );
}
