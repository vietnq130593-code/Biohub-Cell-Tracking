"use client";

import * as React from "react";
import { motion } from "framer-motion";
import { Info, Medal, Search, Trophy, Users2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  leaderboardTop,
  leaderboardNote,
  competition,
} from "@/lib/competition-data";

const fadeUp = {
  initial: { opacity: 0, y: 24 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true, margin: "-60px" },
};

function rankBadge(rank: number) {
  if (rank === 1) return { cls: "bg-amber-400 text-amber-950", label: "🥇 1" };
  if (rank === 2) return { cls: "bg-slate-300 text-slate-800", label: "🥈 2" };
  if (rank === 3) return { cls: "bg-orange-400/80 text-orange-950", label: "🥉 3" };
  return { cls: "bg-muted text-muted-foreground", label: String(rank) };
}

export function LeaderboardTab() {
  const [query, setQuery] = React.useState("");
  const maxScore = leaderboardTop[0].score;

  const filtered = React.useMemo(
    () =>
      leaderboardTop.filter((row) =>
        row.team.toLowerCase().includes(query.trim().toLowerCase()),
      ),
    [query],
  );

  return (
    <div className="space-y-8">
      <section aria-labelledby="lb-heading">
        <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
          <div>
            <h3
              id="lb-heading"
              className="text-xl font-bold tracking-tight sm:text-2xl"
            >
              🏅 Bảng xếp hạng công khai (Top 10)
            </h3>
            <p className="mt-1.5 max-w-2xl text-sm leading-relaxed text-muted-foreground">
              Cập nhật đến 11/09/2026. Đội dẫn đầu đang đạt{" "}
              <strong className="text-emerald-700 dark:text-emerald-400">
                {leaderboardTop[0].score.toFixed(3)}
              </strong>{" "}
              — cuộc cạnh tranh cực kỳ sát sao ở nhóm đầu.
            </p>
          </div>
          <div className="relative w-full sm:w-64">
            <Search
              className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
              aria-hidden
            />
            <Input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Tìm đội..."
              className="pl-8"
              aria-label="Tìm kiếm đội trong bảng xếp hạng"
            />
          </div>
        </div>

        <motion.div {...fadeUp} transition={{ duration: 0.45 }}>
          <Card>
            <CardContent className="p-0">
              <div className="max-h-96 overflow-y-auto">
                <Table>
                  <TableHeader className="sticky top-0 z-10 bg-background">
                    <TableRow>
                      <TableHead className="w-16 text-center">#</TableHead>
                      <TableHead>Đội</TableHead>
                      <TableHead className="text-right">Điểm</TableHead>
                      <TableHead className="hidden w-28 text-right sm:table-cell">
                        Số lần nộp
                      </TableHead>
                      <TableHead className="hidden w-36 text-right md:table-cell">
                        So với #1
                      </TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filtered.map((row) => {
                      const badge = rankBadge(row.rank);
                      return (
                        <TableRow
                          key={row.rank}
                          className={row.rank === 1 ? "bg-amber-500/[0.06]" : ""}
                        >
                          <TableCell className="text-center">
                            <span
                              className={`inline-flex h-7 min-w-7 items-center justify-center rounded-full px-1.5 text-xs font-bold ${badge.cls}`}
                            >
                              {badge.label}
                            </span>
                          </TableCell>
                          <TableCell className="max-w-[180px] truncate font-medium sm:max-w-none">
                            {row.team}
                            {row.rank === 1 && (
                              <Trophy
                                className="ml-1.5 inline h-3.5 w-3.5 text-amber-500"
                                aria-label="Đang dẫn đầu"
                              />
                            )}
                          </TableCell>
                          <TableCell className="text-right font-mono font-bold tabular-nums text-emerald-700 dark:text-emerald-400">
                            {row.score.toFixed(3)}
                          </TableCell>
                          <TableCell className="hidden text-right tabular-nums text-muted-foreground sm:table-cell">
                            {row.entries}
                          </TableCell>
                          <TableCell className="hidden md:table-cell">
                            <Progress
                              value={(row.score / maxScore) * 100}
                              className="h-1.5"
                              aria-label={`Điểm bằng ${(
                                (row.score / maxScore) *
                                100
                              ).toFixed(1)}% đội hạng 1`}
                            />
                          </TableCell>
                        </TableRow>
                      );
                    })}
                    {filtered.length === 0 && (
                      <TableRow>
                        <TableCell
                          colSpan={5}
                          className="py-8 text-center text-sm text-muted-foreground"
                        >
                          Không tìm thấy đội nào khớp “{query}”.
                        </TableCell>
                      </TableRow>
                    )}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>
        </motion.div>

        <motion.div
          {...fadeUp}
          transition={{ duration: 0.45 }}
          className="mt-4 flex gap-3 rounded-xl border border-amber-500/25 bg-amber-500/[0.06] p-4"
        >
          <Info
            className="mt-0.5 h-4.5 w-4.5 shrink-0 text-amber-600 dark:text-amber-400"
            aria-hidden
          />
          <p className="text-sm leading-relaxed">
            <strong>Public ≠ Private:</strong> {leaderboardNote} Hãy chọn 2
            submission cuối cùng dựa trên cross-validation thay vì điểm public
            để tránh overfitting 29% dữ liệu hiển thị.
          </p>
        </motion.div>
      </section>

      {/* Thống kê tham gia */}
      <section aria-labelledby="stats-heading">
        <h3
          id="stats-heading"
          className="mb-5 text-xl font-bold tracking-tight sm:text-2xl"
        >
          📊 Mức độ cạnh tranh
        </h3>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {[
            {
              icon: Users2,
              value: new Intl.NumberFormat("vi-VN").format(
                competition.stats.entrants,
              ),
              label: "Người đăng ký (Entrants)",
              hint: "Đã chấp nhận quy tắc cuộc thi",
            },
            {
              icon: Users2,
              value: new Intl.NumberFormat("vi-VN").format(
                competition.stats.participants,
              ),
              label: "Người đã nộp bài",
              hint: "Có ít nhất 1 submission hợp lệ",
            },
            {
              icon: Medal,
              value: new Intl.NumberFormat("vi-VN").format(
                competition.stats.teams,
              ),
              label: "Đội đang thi",
              hint: "Cá nhân hoặc nhóm",
            },
            {
              icon: Trophy,
              value: new Intl.NumberFormat("vi-VN").format(
                competition.stats.submissions,
              ),
              label: "Tổng lượt nộp bài",
              hint: "Trung bình ~18 lượt/đội",
            },
          ].map((stat, i) => (
            <motion.div
              key={stat.label}
              {...fadeUp}
              transition={{ delay: i * 0.07, duration: 0.4 }}
            >
              <Card className="h-full">
                <CardContent className="flex flex-col gap-1 p-4">
                  <stat.icon
                    className="mb-1 h-5 w-5 text-emerald-600 dark:text-emerald-400"
                    aria-hidden
                  />
                  <p className="text-2xl font-bold tabular-nums">{stat.value}</p>
                  <p className="text-sm font-medium">{stat.label}</p>
                  <p className="text-xs text-muted-foreground">{stat.hint}</p>
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </div>
      </section>
    </div>
  );
}
