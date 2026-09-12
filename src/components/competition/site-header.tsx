"use client";

import * as React from "react";
import { motion } from "framer-motion";
import {
  Dna,
  FlaskConical,
  Trophy,
  Database,
  Gauge,
  Upload,
  BarChart3,
  ExternalLink,
  Moon,
  Sun,
  GraduationCap,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  NavigationMenu,
  NavigationMenuList,
  NavigationMenuItem,
  navigationMenuTriggerStyle,
} from "@/components/ui/navigation-menu";
import { useTheme } from "next-themes";
import { COMPETITION_URL } from "@/lib/competition-data";

const NAV_LINKS = [
  { href: "#demo", label: "Mô phỏng", icon: FlaskConical },
  { href: "#noi-dung", label: "Đề bài", icon: GraduationCap },
  { href: "#getting-started", label: "Lộ trình", icon: BarChart3 },
];

export function SiteHeader() {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = React.useState(false);
  const [scrolled, setScrolled] = React.useState(false);

  React.useEffect(() => {
    setMounted(true);
    const onScroll = () => setScrolled(window.scrollY > 12);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <motion.header
      initial={{ y: -64, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.5, ease: "easeOut" }}
      className={`sticky top-0 z-50 w-full border-b transition-all duration-300 ${
        scrolled
          ? "bg-background/85 backdrop-blur-md shadow-sm"
          : "bg-background/60 backdrop-blur-sm"
      }`}
    >
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-3 px-4 sm:px-6">
        <a href="#" className="flex items-center gap-2.5 min-w-0">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground shadow-sm">
            <Dna className="h-5 w-5" aria-hidden />
          </span>
          <span className="flex min-w-0 flex-col leading-tight">
            <span className="truncate text-sm font-semibold tracking-tight">
              Biohub · Cell Tracking
            </span>
            <span className="truncate text-[11px] text-muted-foreground">
              Cẩm nang thi đấu Kaggle
            </span>
          </span>
        </a>

        <div className="hidden md:flex">
          <NavigationMenu>
            <NavigationMenuList>
              {NAV_LINKS.map((link) => (
                <NavigationMenuItem key={link.href}>
                  <a
                    href={link.href}
                    className={`${navigationMenuTriggerStyle()} gap-1.5`}
                  >
                    <link.icon className="h-4 w-4" aria-hidden />
                    {link.label}
                  </a>
                </NavigationMenuItem>
              ))}
            </NavigationMenuList>
          </NavigationMenu>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="icon"
            aria-label="Chuyển đổi giao diện sáng/tối"
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          >
            {mounted && theme === "dark" ? (
              <Sun className="h-4.5 w-4.5" aria-hidden />
            ) : (
              <Moon className="h-4.5 w-4.5" aria-hidden />
            )}
          </Button>
          <Button asChild className="gap-1.5">
            <a href={COMPETITION_URL} target="_blank" rel="noopener noreferrer">
              <Trophy className="h-4 w-4" aria-hidden />
              <span className="hidden sm:inline">Tham gia cuộc thi</span>
              <span className="sm:hidden">Tham gia</span>
              <ExternalLink className="h-3.5 w-3.5 opacity-70" aria-hidden />
            </a>
          </Button>
        </div>
      </div>

      {/* Mobile nav */}
      <nav
        className="flex items-center justify-center gap-1 border-t px-2 py-1.5 md:hidden"
        aria-label="Điều hướng chính"
      >
        {NAV_LINKS.map((link) => (
          <a
            key={link.href}
            href={link.href}
            className="flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
          >
            <link.icon className="h-3.5 w-3.5" aria-hidden />
            {link.label}
          </a>
        ))}
      </nav>
    </motion.header>
  );
}

/** Các icon dùng chung cho phần code requirements */
export const REQUIREMENT_ICONS: Record<
  string,
  React.ComponentType<{ className?: string }>
> = {
  cpu: Gauge,
  gpu: FlaskConical,
  "wifi-off": Gauge,
  database: Database,
  file: Upload,
  notebook: GraduationCap,
};
