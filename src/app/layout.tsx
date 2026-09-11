import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { Toaster } from "@/components/ui/toaster";
import { ThemeProvider } from "@/components/theme-provider";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Biohub — Cell Tracking During Development | Cẩm nang thi đấu Kaggle",
  description:
    "Tổng hợp và giải thích cuộc thi Kaggle Biohub Cell Tracking During Development: phát hiện & theo dõi tế bào phôi cá ngựa vằn trong 3D+time, $60.000 giải thưởng, metric, dữ liệu Zarr/GEFF và lộ trình khởi đầu.",
  keywords: [
    "Kaggle",
    "Biohub",
    "cell tracking",
    "zebrafish",
    "computer vision",
    "biology",
    "competition",
    "3D microscopy",
    "lineage reconstruction",
  ],
  openGraph: {
    title: "Biohub — Cell Tracking During Development",
    description:
      "Cẩm nang thi đấu Kaggle: detect, track tế bào 3D+time và tái dựng phả hệ — $60.000 giải thưởng.",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="vi" suppressHydrationWarning>
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased bg-background text-foreground`}
      >
        <ThemeProvider
          attribute="class"
          defaultTheme="light"
          enableSystem
          disableTransitionOnChange
        >
          {children}
          <Toaster />
        </ThemeProvider>
      </body>
    </html>
  );
}
