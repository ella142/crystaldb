import type { Metadata } from "next";
import { SiteHeader } from "@/components/site-header";
import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "CrystalDB",
    template: "%s | CrystalDB",
  },
  description:
    "A provenance-aware crystallographic database linking experimental X-ray diffraction measurements to crystal structures.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        <SiteHeader />
        <main>{children}</main>
        <footer className="border-t border-line bg-white">
          <div className="page-frame flex flex-col gap-2 py-8 text-sm text-slate-500 sm:flex-row sm:items-center sm:justify-between">
            <span>CrystalDB · provenance-aware scientific data</span>
            <span>Read-only API release v0.1.2</span>
          </div>
        </footer>
      </body>
    </html>
  );
}
