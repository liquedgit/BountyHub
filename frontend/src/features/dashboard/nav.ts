import { FolderKanban, LayoutDashboard, NotebookText, Radar, ShieldAlert, type LucideIcon } from "lucide-react";

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
