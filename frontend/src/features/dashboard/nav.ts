import { LayoutDashboard, type LucideIcon } from "lucide-react";

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
}

/** Feature pages (programs, findings, notes, recon) register themselves here as they are built. */
export const NAV_ITEMS: NavItem[] = [{ href: "/", label: "Overview", icon: LayoutDashboard }];
