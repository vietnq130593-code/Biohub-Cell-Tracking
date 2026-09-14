"use client";

import * as React from "react";
import Image from "next/image";
import { motion } from "framer-motion";
import {
  ArrowDown,
  ExternalLink,
  FileText,
  Globe2,
  Hourglass,
  Timer,
  Trophy,
  Users,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  competition,
  COMPETITION_URL,
  KAGGLE_RESULTS,
  LB_CONTEXT,
} from "@/lib/competition-data";

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
  const fmt = new Intl.NumberFormat("vi-VN");
  const ver7 = KAGGLE_RESULTS.find((v) => v.id === "ver7");
  const runMinutes = Math.round((ver7?.runSeconds ?? 7020) / 60);

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
            <Hourglass className="mr-1 h-3 w-3" aria-hidden />
            Ver 7 · port 0.947 — đang chấm public LB
            <span
              className="relative ml-1.5 flex size-2"
              aria-hidden
            >
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-amber-300 opacity-75" />
              <span className="relative inline-flex size-2 rounded-full bg-amber-300" />
            </span>
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

        {/* Thành tích pipeline trên Kaggle */}
        <div className="mt-10 w-full max-w-3xl">
          <p className="mb-3 text-xs font-medium uppercase tracking-[0.2em] text-white/50">
            Thành tích pipeline của team trên Kaggle
          </p>
          <div className="grid w-full grid-cols-2 gap-2.5 sm:grid-cols-4 sm:gap-3">
            <StatItem
              icon={Trophy}
              value={LB_CONTEXT.ourScore.toFixed(3)}
              label="Public LB · ver-6 deterministic"
              delay={0.4}
            />
            <StatItem
              icon={FileText}
              value={fmt.format(ver7?.submissionRows ?? 241356)}
              label="dòng submission ver-7"
              delay={0.46}
            />
            <StatItem
              icon={Timer}
              value={`${runMinutes} phút`}
              label="run T4×2 · COMPLETE"
              delay={0.52}
            />
            <StatItem
              icon={Users}
              value={`${fmt.format(LB_CONTEXT.wallTeams)} đội`}
              label={`bức tường ${LB_CONTEXT.wallScore.toFixed(3)} trên LB`}
              delay={0.58}
            />
          </div>
        </div>

        {/* Tags */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.7, duration: 0.5 }}
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
