import {
  FolderKanban,
  LayoutDashboard,
  NotebookText,
  Radar,
  Settings,
  ShieldAlert,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
}

export const NAV_ITEMS: NavItem[] = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/programs", label: "Programs", icon: FolderKanban },
  { href: "/findings", label: "Findings", icon: ShieldAlert },
  { href: "/notes", label: "Notes", icon: NotebookText },
  { href: "/recon", label: "Recon", icon: Radar },
];

/** Pinned at the bottom of the navigation. */
export const SETTINGS_ITEM: NavItem = { href: "/settings", label: "Settings", icon: Settings };

/** A nested route (`/programs/12`) belongs to its parent item; `/` only matches itself. */
export function isActivePath(pathname: string | null, href: string): boolean {
  if (!pathname) return false;
  if (href === "/") return pathname === "/";
  return pathname === href || pathname.startsWith(`${href}/`);
}
