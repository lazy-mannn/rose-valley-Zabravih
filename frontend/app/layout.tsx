import type { Metadata } from "next";
import { Manrope } from "next/font/google";
import "./globals.css";

const manrope = Manrope({
  subsets: ["latin"],
  variable: "--font-manrope",
  weight: ["400", "500", "600", "700", "800"],
});

export const metadata: Metadata = {
  title: "Smart Kazan Collector",
  description: "Smart waste collection platform for Sofia municipality — 43,511 bins, 76 trucks.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="bg" className={`${manrope.variable} h-full`}>
      <body className="min-h-full flex flex-col bg-[#070D1A] text-[#F0F6FF] antialiased">
        {children}
      </body>
    </html>
  );
}
