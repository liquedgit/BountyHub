"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { NAV_ITEMS, SETTINGS_ITEM, isActivePath, type NavItem } from "@/features/dashboard/nav";
import { cn } from "@/lib/utils";

/** The primary navigation, shared by the desktop sidebar and the mobile sheet. */
export function NavLinks({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();

  function renderItem({ href, label, icon: Icon }: NavItem) {
    const active = isActivePath(pathname, href);
    return (
      <Link
        key={href}
        href={href}
        onClick={onNavigate}
        aria-current={active ? "page" : undefined}
        className={cn(
          "flex items-center gap-3 rounded-md px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
          active && "bg-accent font-medium text-accent-foreground",
        )}
      >
        <Icon className="h-4 w-4" aria-hidden />
        {label}
      </Link>
    );
  }

  return (
    <nav aria-label="Main" className="flex h-full flex-col">
      <div className="space-y-1">{NAV_ITEMS.map(renderItem)}</div>
      <div className="mt-auto space-y-1 border-t pt-3">{renderItem(SETTINGS_ITEM)}</div>
    </nav>
  );
}
