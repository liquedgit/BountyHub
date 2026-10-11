"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { Brand } from "@/components/layout/brand";
import { LogoutButton } from "@/components/layout/logout-button";
import { MobileNav } from "@/components/layout/mobile-nav";
import { ThemeToggle } from "@/components/layout/theme-toggle";
import { request } from "@/lib/api";

export function Header() {
  const me = useQuery({
    queryKey: ["auth", "me"],
    queryFn: () => request<{ email: string }>("/auth/me"),
    staleTime: 5 * 60_000,
  });

  return (
    <header className="sticky top-0 z-30 flex h-14 items-center gap-2 border-b bg-background/95 px-3 backdrop-blur sm:px-6">
      <MobileNav />
      <Link href="/" aria-label="BountyHub home" className="md:hidden">
        <Brand className="text-base" />
      </Link>
      <div className="ml-auto flex min-w-0 items-center gap-1 sm:gap-2">
        {me.data?.email ? (
          <span
            data-testid="user-email"
            className="hidden max-w-[16rem] truncate text-sm text-muted-foreground sm:inline"
            title={me.data.email}
          >
            {me.data.email}
          </span>
        ) : null}
        <ThemeToggle />
        <LogoutButton />
      </div>
    </header>
  );
}
