import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Providers } from "@/providers/providers";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "BountyHub", template: "%s · BountyHub" },
  description: "Bug-bounty management and authorized recon workspace",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
