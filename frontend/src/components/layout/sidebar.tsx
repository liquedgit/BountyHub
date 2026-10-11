import Link from "next/link";
import { Brand } from "@/components/layout/brand";
import { NavLinks } from "@/components/layout/nav-links";

export function Sidebar() {
  return (
    <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col border-r md:flex">
      <Link href="/" aria-label="BountyHub home" className="px-5 py-4">
        <Brand />
      </Link>
      <div className="min-h-0 flex-1 px-3 pb-4">
        <NavLinks />
      </div>
    </aside>
  );
}
