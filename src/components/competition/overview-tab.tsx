"use client";

import * as React from "react";
import { motion } from "framer-motion";
import {
  CircleDot,
  GitBranch,
  Network,
  Antenna,
  ScanEye,
  Shuffle,
  CalendarDays,
  CheckCircle2,
  CircleDashed,
  Hourglass,
  Lock,
  Coins,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
  competition,
  timeline,
  prizes,
  codeRequirements,
} from "@/lib/competition-data";

const fadeUp = {
  initial: { opacity: 0, y: 24 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true, margin: "-60px" },
};

const TASKS = [
  {
    icon: CircleDot,
    title: "1 · Phát hiện tế bào (Detection)",
    detail:
      "Với mỗi mốc thời gian t, tìm tọa độ trọng tâm (z, y, x) của từng tế bào trong khối ảnh 3D — chính là các node trong đồ thị tracking.",
    accent: "text-emerald-600 dark:text-emerald-400",
    ring: "ring-emerald-500/20 bg-emerald-500/10",
  },
  {
    icon: Network,
    title: "2 · Liên kết qua thời gian (Tracking)",
    detail:
      "Ghép mỗi tế bào ở frame t với chính nó ở frame t+1, tạo thành các cạnh (edge) — dù tế bào di chuyển, biến dạng và dày đặc.",
    accent: "text-teal-600 dark:text-teal-400",
    ring: "ring-teal-500/20 bg-teal-500/10",
  },
  {
    icon: GitBranch,
    title: "3 · Phân bào & phả hệ (Division & Lineage)",
    detail:
      "Nhận diện lúc một tế bào mẹ tách thành hai con — node có ≥ 2 cạnh đi ra. Ghép tất cả lại để tái dựng cây phả hệ hoàn chỉnh.",
    accent: "text-amber-600 dark:text-amber-400",
    ring: "ring-amber-500/20 bg-amber-500/10",
  },
];

const CHALLENGES = [
  {
    icon: ScanEye,
    title: "Mật độ dày đặc",
    detail:
      "Hàng nghìn tế bào gần như giống hệt nhau chen chúc trong cùng trường nhìn.",
  },
  {
    icon: Antenna,
    title: "Nhiễu ảnh thực tế",
    detail:
      "Ảnh huỳnh quang 3D có nhiễu sensor, suy giảm tín hiệu theo độ sâu và quang sai.",
  },
  {
    icon: Shuffle,
    title: "Chuyển động & biến dạng",
    detail:
      "Tế bào di chuyển phi tuyến, thay đổi hình dạng và phân chia liên tục.",
  },
  {
    icon: Lock,
    title: "Gắn nhãn thưa (sparse GT)",
    detail:
      "Ground-truth chỉ chú thích một phần tế bào — bài toán khó hơn 'đếm đủ mọi thứ'.",
  },
];

const REQUIREMENT_ICON_MAP: Record<
  string,
  React.ComponentType<{ className?: string }>
> = {
  cpu: Hourglass,
  gpu: Hourglass,
  "wifi-off": Lock,
  database: CircleDot,
  file: CheckCircle2,
  notebook: CalendarDays,
};

export function OverviewTab() {
  const fmt = new Intl.NumberFormat("vi-VN");

  return (
    <div className="space-y-14">
      {/* Bài toán là gì */}
      <section aria-labelledby="task-heading">
        <div className="mb-5">
          <h3
            id="task-heading"
            className="text-xl font-bold tracking-tight sm:text-2xl"
          >
            🧬 Bài toán của bạn là gì?
          </h3>
          <p className="mt-1.5 max-w-3xl text-sm leading-relaxed text-muted-foreground">
            {competition.description}
          </p>
        </div>
        <div className="grid gap-4 sm:grid-cols-3">
          {TASKS.map((task, i) => (
            <motion.div
              key={task.title}
              {...fadeUp}
              transition={{ delay: i * 0.08, duration: 0.45 }}
            >
              <Card className="h-full transition-shadow hover:shadow-md">
                <CardHeader className="pb-2">
                  <div
                    className={`mb-2 flex h-11 w-11 items-center justify-center rounded-xl ring-1 ${task.ring}`}
                  >
                    <task.icon className={`h-5.5 w-5.5 ${task.accent}`} aria-hidden />
                  </div>
                  <CardTitle className="text-[15px] leading-snug">
                    {task.title}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm leading-relaxed text-muted-foreground">
                    {task.detail}
                  </p>
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </div>
        <motion.p
          {...fadeUp}
          transition={{ duration: 0.45 }}
          className="mt-4 rounded-xl border border-emerald-500/25 bg-emerald-500/[0.07] p-4 text-sm leading-relaxed"
        >
          <strong>Tại sao quan trọng?</strong> {competition.impact} Hiện nay,
          các nhà nghiên cứu mất vô số giờ theo dõi tế bào thủ công — đặc biệt
          ở những bộ dữ liệu có hàng nghìn tế bào tương tự nhau di chuyển, biến
          dạng và phân chia.
        </motion.p>
      </section>

      {/* Tại sao khó */}
      <section aria-labelledby="challenge-heading">
        <h3
          id="challenge-heading"
          className="mb-5 text-xl font-bold tracking-tight sm:text-2xl"
        >
          ⚡ Vì sao các công cụ tự động sẵn có hay thất bại?
        </h3>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {CHALLENGES.map((c, i) => (
            <motion.div
              key={c.title}
              {...fadeUp}
              transition={{ delay: i * 0.07, duration: 0.4 }}
              className="rounded-xl border bg-card p-4"
            >
              <c.icon
                className="mb-2 h-5 w-5 text-rose-500"
                aria-hidden
              />
              <p className="text-sm font-semibold">{c.title}</p>
              <p className="mt-1 text-[13px] leading-relaxed text-muted-foreground">
                {c.detail}
              </p>
            </motion.div>
          ))}
        </div>
      </section>

      {/* Timeline */}
      <section aria-labelledby="timeline-heading">
        <h3
          id="timeline-heading"
          className="mb-5 text-xl font-bold tracking-tight sm:text-2xl"
        >
          🗓️ Mốc thời gian quan trọng
        </h3>
        <ol className="relative ml-3 space-y-6 border-l-2 border-dashed border-emerald-500/30 pl-6">
          {timeline.map((item, i) => {
            const date = new Date(item.date);
            const isPassed = date.getTime() < Date.now();
            return (
              <motion.li
                key={item.label}
                {...fadeUp}
                transition={{ delay: i * 0.1, duration: 0.45 }}
                className="relative"
              >
                <span
                  className={`absolute -left-[35px] flex h-5 w-5 items-center justify-center rounded-full ring-4 ring-background ${
                    isPassed
                      ? "bg-emerald-500 text-white"
                      : "bg-amber-400 text-amber-950"
                  }`}
                  aria-hidden
                >
                  {isPassed ? (
                    <CheckCircle2 className="h-3.5 w-3.5" />
                  ) : (
                    <Hourglass className="h-3.5 w-3.5" />
                  )}
                </span>
                <div className="flex flex-wrap items-center gap-2">
                  <time className="font-mono text-sm font-bold text-emerald-700 dark:text-emerald-400">
                    {new Intl.DateTimeFormat("vi-VN", {
                      day: "2-digit",
                      month: "2-digit",
                      year: "numeric",
                      timeZone: "UTC",
                    }).format(date)}
                  </time>
                  <Badge
                    variant={isPassed ? "secondary" : "default"}
                    className="text-[11px]"
                  >
                    {isPassed ? "Đã diễn ra" : "Sắp tới"}
                  </Badge>
                </div>
                <p className="mt-0.5 text-sm font-semibold">{item.label}</p>
                <p className="mt-0.5 max-w-2xl text-[13px] leading-relaxed text-muted-foreground">
                  {item.detail}
                </p>
              </motion.li>
            );
          })}
        </ol>
        <p className="mt-4 text-xs text-muted-foreground">
          * Mọi deadline lúc 23:59 UTC ngày tương ứng. BTC có quyền điều chỉnh
          lịch trình nếu cần.
        </p>
      </section>

      {/* Prizes */}
      <section aria-labelledby="prize-heading">
        <div className="mb-5 flex flex-wrap items-end justify-between gap-2">
          <h3
            id="prize-heading"
            className="text-xl font-bold tracking-tight sm:text-2xl"
          >
            🏆 Cơ cấu giải thưởng
          </h3>
          <p className="flex items-center gap-1.5 text-sm font-semibold text-amber-600 dark:text-amber-400">
            <Coins className="h-4 w-4" aria-hidden />
            Tổng: ${fmt.format(competition.totalPrize)}
          </p>
        </div>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-7">
          {prizes.map((prize, i) => {
            const max = prizes[0].amount;
            return (
              <motion.div
                key={prize.rank}
                {...fadeUp}
                transition={{ delay: i * 0.06, duration: 0.4 }}
                className={`rounded-xl border p-3.5 text-center ${
                  prize.rank === 1
                    ? "border-amber-400/60 bg-gradient-to-b from-amber-100/70 to-transparent dark:from-amber-500/15"
                    : "bg-card"
                }`}
              >
                <p className="text-lg" aria-hidden>
                  {prize.emoji}
                </p>
                <p className="mt-0.5 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                  Hạng {prize.rank}
                </p>
                <p className="mt-1 text-base font-bold tabular-nums text-emerald-700 dark:text-emerald-400">
                  ${fmt.format(prize.amount)}
                </p>
                <Progress
                  value={(prize.amount / max) * 100}
                  className="mt-2 h-1"
                />
              </motion.div>
            );
          })}
        </div>
      </section>

      {/* Code requirements */}
      <section aria-labelledby="code-heading">
        <h3
          id="code-heading"
          className="mb-5 text-xl font-bold tracking-tight sm:text-2xl"
        >
          ⚙️ Quy định nộp bài (Code Competition)
        </h3>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {codeRequirements.map((req, i) => {
            const Icon = REQUIREMENT_ICON_MAP[req.icon] ?? CircleDashed;
            return (
              <motion.div
                key={req.label}
                {...fadeUp}
                transition={{ delay: i * 0.06, duration: 0.4 }}
                className="flex items-start gap-3 rounded-xl border bg-card p-4"
              >
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
                  <Icon className="h-4.5 w-4.5" aria-hidden />
                </span>
                <div className="min-w-0">
                  <p className="text-sm font-semibold">{req.label}</p>
                  <p className="text-[13px] leading-snug text-muted-foreground">
                    {req.value}
                  </p>
                </div>
              </motion.div>
            );
          })}
        </div>
        <p className="mt-3 text-xs text-muted-foreground">
          Nút "Submit" chỉ được kích hoạt sau khi notebook commit thành công và
          đáp ứng đủ các điều kiện trên.
        </p>
      </section>
    </div>
  );
}
