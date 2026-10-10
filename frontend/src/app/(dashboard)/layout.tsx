import Link from "next/link";

const NAV = [
  { href: "/programs", label: "Programs" },
  { href: "/findings", label: "Findings" },
  { href: "/notes", label: "Notes" },
  { href: "/recon", label: "Recon" },
];

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen">
      <nav className="w-48 space-y-2 border-r p-4">
        <div className="mb-4 font-bold">BountyHub</div>
        {NAV.map((n) => (
          <Link key={n.href} href={n.href} className="block hover:underline">
            {n.label}
          </Link>
        ))}
      </nav>
      <main className="flex-1 p-6">{children}</main>
    </div>
  );
}
