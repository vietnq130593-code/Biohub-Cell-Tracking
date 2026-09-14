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
  title: "Biohub — Cell Tracking During Development | Môi trường mô phỏng pipeline",
  description:
    "Môi trường mô phỏng nội bộ các phiên bản pipeline cho cuộc thi Kaggle Biohub Cell Tracking: phát hiện & theo dõi tế bào phôi cá ngựa vằn 3D+time, metric adjEJ + 0.1×divJ, dữ liệu Zarr/GEFF và kết quả Kaggle thật của ver-6 / ver-7.",
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
      "Môi trường mô phỏng nội bộ các phiên bản pipeline: detect, track tế bào 3D+time và tái dựng phả hệ — số liệu Kaggle thật ver-6 0.945 · ver-7 đang chấm.",
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
