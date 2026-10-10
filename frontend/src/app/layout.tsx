import "./globals.css";
import { Providers } from "@/components/providers";

export const metadata = { title: "BountyHub" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-neutral-950 text-neutral-100">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
