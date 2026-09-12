"use client";

import * as React from "react";
import Image from "next/image";
import { motion } from "framer-motion";
import {
  ArrowDown,
  CalendarClock,
  DollarSign,
  ExternalLink,
  Globe2,
  Group,
  Trophy,
  Upload,
  Users,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  competition,
  PRIZE_DEADLINE,
  ENTRY_DEADLINE,
  COMPETITION_URL,
} from "@/lib/competition-data";

function useCountdown(target: string) {
  const [remaining, setRemaining] = React.useState<{
    days: number;
    hours: number;
    minutes: number;
    seconds: number;
    total: number;
  } | null>(null);

  React.useEffect(() => {
    const compute = () => {
      const diff = new Date(target).getTime() - Date.now();
      if (diff <= 0) {
        setRemaining({ days: 0, hours: 0, minutes: 0, seconds: 0, total: 0 });
        return;
      }
      setRemaining({
        days: Math.floor(diff / 86_400_000),
        hours: Math.floor((diff % 86_400_000) / 3_600_000),
        minutes: Math.floor((diff % 3_600_000) / 60_000),
        seconds: Math.floor((diff % 60_000) / 1000),
        total: diff,
      });
    };
    compute();
    const id = setInterval(compute, 1000);
    return () => clearInterval(id);
  }, [target]);

  return remaining;
}

function CountdownCell({
  value,
  label,
  delay,
}: {
  value: number;
  label: string;
  delay: number;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.45 }}
      className="flex min-w-[72px] flex-col items-center rounded-xl border border-white/15 bg-white/10 px-3 py-2.5 backdrop-blur-sm sm:min-w-[88px]"
    >
      <span
        className="font-mono text-2xl font-bold tabular-nums text-white sm:text-3xl"
        suppressHydrationWarning
      >
        {String(value).padStart(2, "0")}
      </span>
      <span className="text-[10px] font-medium uppercase tracking-wider text-white/60 sm:text-xs">
        {label}
      </span>
    </motion.div>
  );
}

function StatItem({
  icon: Icon,
  value,
  label,
  delay,
}: {
  icon: React.ComponentType<{ className?: string }>;
  value: string;
  label: string;
  delay: number;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.45 }}
      className="flex flex-col items-center gap-1 rounded-xl bg-white/[0.07] px-4 py-3 text-center ring-1 ring-white/10 backdrop-blur-sm"
    >
      <Icon className="mb-0.5 h-4 w-4 text-emerald-300" aria-hidden />
      <span className="text-lg font-bold leading-none text-white sm:text-xl">
        {value}
      </span>
      <span className="text-[11px] leading-tight text-white/60">{label}</span>
    </motion.div>
  );
}

export function Hero() {
  const finalLeft = useCountdown(PRIZE_DEADLINE);
  const entryLeft = useCountdown(ENTRY_DEADLINE);
  const fmt = new Intl.NumberFormat("vi-VN");

  return (
    <section className="relative isolate overflow-hidden bg-[#04120c] text-white">
      {/* Background microscopy image */}
      <div className="absolute inset-0 -z-10">
        <Image
          src="/images/hero-cells.png"
          alt="Ảnh kính hiển vi huỳnh quang tế bào phôi cá ngựa vằn"
          fill
          priority
          sizes="100vw"
          className="object-cover opacity-70"
        />
        <div className="absolute inset-0 bg-gradient-to-b from-[#04120c]/60 via-[#04120c]/70 to-[#04120c]" />
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,transparent_0%,rgba(4,18,12,0.55)_75%)]" />
        <div className="micro-grid absolute inset-0 opacity-40" />
      </div>

      <div className="mx-auto flex max-w-7xl flex-col items-center px-4 py-16 text-center sm:px-6 sm:py-24">
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="mb-5 flex flex-wrap items-center justify-center gap-2"
        >
          <Badge
            variant="outline"
            className="border-emerald-400/40 bg-emerald-400/10 text-emerald-200 backdrop-blur-sm"
          >
            <Globe2 className="mr-1 h-3 w-3" aria-hidden />
            BIOHUB · RESEARCH CODE COMPETITION
          </Badge>
          <Badge
            variant="outline"
            className="border-amber-400/40 bg-amber-400/10 text-amber-200 backdrop-blur-sm"
          >
            <CalendarClock className="mr-1 h-3 w-3" aria-hidden />
            {finalLeft
              ? `Còn ${finalLeft.days} ngày để nộp bài`
              : "Đang tính thời gian..."}
          </Badge>
        </motion.div>

        <motion.h1
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1, duration: 0.55 }}
          className="max-w-4xl text-3xl font-extrabold leading-tight tracking-tight sm:text-5xl"
        >
          Biohub — Cell Tracking{" "}
          <span className="bg-gradient-to-r from-emerald-300 via-teal-200 to-emerald-400 bg-clip-text text-transparent">
            During Development
          </span>
        </motion.h1>

        <motion.p
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2, duration: 0.55 }}
          className="mt-4 max-w-2xl text-balance text-sm leading-relaxed text-white/70 sm:text-lg"
        >
          Phát hiện và theo dõi tế bào phôi cá ngựa vằn qua không gian 3D và
          thời gian. Nhiệm vụ của bạn: <strong className="text-white">detect</strong> tế
          bào, <strong className="text-white">link</strong> chúng qua từng khung
          hình và nhận diện <strong className="text-white">phân bào</strong> để
          tái dựng phả hệ — giúp xóa bỏ nút thắt thủ công khổng lồ trong nghiên
          cứu sinh học.
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3, duration: 0.55 }}
          className="mt-7 flex flex-wrap items-center justify-center gap-3"
        >
          <Button
            asChild
            size="lg"
            className="gap-1.5 bg-emerald-500 text-emerald-950 hover:bg-emerald-400"
          >
            <a href={COMPETITION_URL} target="_blank" rel="noopener noreferrer">
              <Trophy className="h-4 w-4" aria-hidden />
              Tham gia cuộc thi
              <ExternalLink className="h-3.5 w-3.5 opacity-70" aria-hidden />
            </a>
          </Button>
          <Button
            asChild
            size="lg"
            variant="secondary"
            className="gap-1.5 bg-white/10 text-white hover:bg-white/20"
          >
            <a href="#demo">
              <ArrowDown className="h-4 w-4" aria-hidden />
              Khám phá đề bài
            </a>
          </Button>
        </motion.div>

        {/* Countdown */}
        <div className="mt-10 w-full max-w-3xl">
          <p className="mb-3 text-xs font-medium uppercase tracking-[0.2em] text-white/50">
            Đếm ngược hạn nộp bài cuối cùng · 23:59 UTC, 29/09/2026
          </p>
          <div className="flex items-start justify-center gap-2 sm:gap-3">
            <CountdownCell value={finalLeft?.days ?? 0} label="Ngày" delay={0.35} />
            <CountdownCell value={finalLeft?.hours ?? 0} label="Giờ" delay={0.42} />
            <CountdownCell value={finalLeft?.minutes ?? 0} label="Phút" delay={0.49} />
            <CountdownCell value={finalLeft?.seconds ?? 0} label="Giây" delay={0.56} />
          </div>
          {entryLeft && entryLeft.total > 0 && (
            <p className="mt-3 text-xs text-white/50" suppressHydrationWarning>
              ⚠️ Hạn chấp nhận quy tắc &amp; sáp nhập đội:{" "}
              <strong className="text-amber-200">
                còn {entryLeft.days} ngày {entryLeft.hours} giờ
              </strong>{" "}
              (22/09/2026) — hãy đăng ký sớm!
            </p>
          )}
        </div>

        {/* Stats */}
        <div className="mt-10 grid w-full max-w-4xl grid-cols-2 gap-2.5 sm:grid-cols-4 sm:gap-3">
          <StatItem
            icon={DollarSign}
            value={`$${fmt.format(competition.totalPrize)}`}
            label="Tổng giải thưởng"
            delay={0.6}
          />
          <StatItem
            icon={Users}
            value={fmt.format(competition.stats.entrants)}
            label="Người đăng ký"
            delay={0.66}
          />
          <StatItem
            icon={Group}
            value={fmt.format(competition.stats.teams)}
            label="Đội tham gia"
            delay={0.72}
          />
          <StatItem
            icon={Upload}
            value={fmt.format(competition.stats.submissions)}
            label="Lượt nộp bài"
            delay={0.78}
          />
        </div>

        {/* Tags */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.85, duration: 0.5 }}
          className="mt-8 flex flex-wrap items-center justify-center gap-1.5"
        >
          {competition.tags.map((tag) => (
            <Badge
              key={tag}
              variant="secondary"
              className="border-white/10 bg-white/[0.06] text-[11px] font-medium text-white/70"
            >
              {tag}
            </Badge>
          ))}
        </motion.div>
      </div>
    </section>
  );
}
