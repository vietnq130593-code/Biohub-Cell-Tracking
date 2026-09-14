"use client";

import * as React from "react";
import { motion } from "framer-motion";
import {
  Sigma,
  Link2,
  GitFork,
  Scale,
  Info,
  ArrowRight,
  CircleCheck,
  CircleX,
  CircleHelp,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { evaluation } from "@/lib/competition-data";

const fadeUp = {
  initial: { opacity: 0, y: 24 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true, margin: "-60px" },
};

/** Hiển thị công thức dạng đẹp */
function Formula() {
  return (
    <div className="overflow-x-auto rounded-2xl border bg-gradient-to-br from-emerald-500/[0.08] via-transparent to-teal-500/[0.08] p-6 text-center">
      <div className="mx-auto flex min-w-max items-center justify-center gap-2 font-mono text-xl font-bold sm:gap-3 sm:text-3xl">
        <span className="text-muted-foreground">score</span>
        <span className="text-muted-foreground">=</span>
        <span className="rounded-lg bg-emerald-500/15 px-2.5 py-1 text-emerald-700 ring-1 ring-emerald-500/30 dark:text-emerald-300">
          adjusted_edge_jaccard
        </span>
        <span className="text-muted-foreground">+</span>
        <span className="rounded-lg bg-amber-500/15 px-2.5 py-1 text-amber-600 ring-1 ring-amber-500/30 dark:text-amber-300">
          0.1&nbsp;×&nbsp;division_jaccard
        </span>
      </div>
      <p className="mt-4 text-xs text-muted-foreground sm:text-sm">
        Điểm có thể <strong>vượt quá 1.0</strong> do bản chất của metric điều
        chỉnh — điểm cao hơn là tốt hơn.
      </p>
    </div>
  );
}

const OUTCOME_CARDS = [
  {
    icon: CircleCheck,
    label: "TP (True Positive)",
    detail: "Cạnh dự đoán mà cả hai đầu đều khớp GT và GT cũng nối cạnh này.",
    cls: "border-emerald-500/40 bg-emerald-500/[0.07] text-emerald-700 dark:text-emerald-300",
  },
  {
    icon: CircleX,
    label: "FP (False Positive)",
    detail: "Cạnh dự đoán nhưng GT không có (link sai hoặc thừa).",
    cls: "border-rose-500/40 bg-rose-500/[0.07] text-rose-700 dark:text-rose-300",
  },
  {
    icon: CircleHelp,
    label: "FN (False Negative)",
    detail: "Cạnh trong GT mà dự đoán bỏ sót (không link hoặc link lệch).",
    cls: "border-amber-500/40 bg-amber-500/[0.07] text-amber-700 dark:text-amber-300",
  },
];

export function EvaluationTab() {
  return (
    <div className="space-y-14">
      <section aria-labelledby="eval-heading">
        <div className="mb-5">
          <h3
            id="eval-heading"
            className="text-xl font-bold tracking-tight sm:text-2xl"
          >
            📐 Cách chấm điểm
          </h3>
          <p className="mt-1.5 max-w-3xl text-sm leading-relaxed text-muted-foreground">
            Bài nộp được đánh giá bằng metric kết hợp, đo đồng thời độ chính xác
            liên kết qua thời gian (edge) và độ chính xác phát hiện phân bào
            (division).
          </p>
        </div>

        <motion.div {...fadeUp} transition={{ duration: 0.5 }}>
          <Formula />
        </motion.div>

        {/* Edge/Division explained */}
        <div className="mt-8 grid gap-4 lg:grid-cols-2">
          <motion.div {...fadeUp} transition={{ duration: 0.45 }}>
            <Card className="h-full border-emerald-500/25">
              <CardHeader className="pb-3">
                <div className="mb-1 flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-500/10 ring-1 ring-emerald-500/20">
                  <Link2
                    className="h-5 w-5 text-emerald-600 dark:text-emerald-400"
                    aria-hidden
                  />
                </div>
                <CardTitle className="text-[15px] leading-snug">
                  {evaluation.edgeJaccard.title}
                </CardTitle>
                <Badge variant="secondary" className="w-fit text-[10px]">
                  Trọng số chính · 90%+
                </Badge>
              </CardHeader>
              <CardContent>
                <ol className="space-y-3">
                  {evaluation.edgeJaccard.steps.map((step, i) => (
                    <li key={i} className="flex gap-3 text-sm leading-relaxed text-muted-foreground">
                      <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-emerald-500/15 font-mono text-[11px] font-bold text-emerald-700 dark:text-emerald-300">
                        {i + 1}
                      </span>
                      {step}
                    </li>
                  ))}
                </ol>
                <div className="mt-4 rounded-lg bg-muted/60 p-3 font-mono text-center text-sm font-semibold">
                  Jaccard&nbsp;=&nbsp;
                  <span className="text-emerald-600 dark:text-emerald-400">TP</span>
                  &nbsp;/&nbsp;(
                  <span className="text-emerald-600 dark:text-emerald-400">TP</span>
                  &nbsp;+&nbsp;
                  <span className="text-rose-600 dark:text-rose-400">FP</span>
                  &nbsp;+&nbsp;
                  <span className="text-amber-600 dark:text-amber-400">FN</span>
                  )
                </div>
              </CardContent>
            </Card>
          </motion.div>

          <motion.div {...fadeUp} transition={{ delay: 0.1, duration: 0.45 }}>
            <Card className="h-full border-amber-500/25">
              <CardHeader className="pb-3">
                <div className="mb-1 flex h-10 w-10 items-center justify-center rounded-xl bg-amber-500/10 ring-1 ring-amber-500/20">
                  <GitFork
                    className="h-5 w-5 text-amber-600 dark:text-amber-400"
                    aria-hidden
                  />
                </div>
                <CardTitle className="text-[15px] leading-snug">
                  {evaluation.divisionJaccard.title}
                </CardTitle>
                <Badge variant="secondary" className="w-fit text-[10px]">
                  Trọng số phụ · 10%
                </Badge>
              </CardHeader>
              <CardContent>
                <ol className="space-y-3">
                  {evaluation.divisionJaccard.steps.map((step, i) => (
                    <li key={i} className="flex gap-3 text-sm leading-relaxed text-muted-foreground">
                      <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-amber-500/15 font-mono text-[11px] font-bold text-amber-700 dark:text-amber-300">
                        {i + 1}
                      </span>
                      {step}
                    </li>
                  ))}
                </ol>
                <div className="mt-4 flex items-center gap-2 rounded-lg bg-muted/60 p-3 text-center text-[13px] leading-relaxed text-muted-foreground">
                  <Scale className="h-4 w-4 shrink-0" aria-hidden />
                  {evaluation.aggregation}
                </div>
              </CardContent>
            </Card>
          </motion.div>
        </div>

        {/* TP FP FN cards */}
        <div className="mt-6 grid gap-3 sm:grid-cols-3">
          {OUTCOME_CARDS.map((card, i) => (
            <motion.div
              key={card.label}
              {...fadeUp}
              transition={{ delay: i * 0.07, duration: 0.4 }}
              className={`rounded-xl border p-4 ${card.cls}`}
            >
              <card.icon className="mb-2 h-5 w-5" aria-hidden />
              <p className="text-sm font-bold">{card.label}</p>
              <p className="mt-1 text-[13px] leading-relaxed opacity-80">
                {card.detail}
              </p>
            </motion.div>
          ))}
        </div>

        {/* Quy trình tính điểm */}
        <motion.div
          {...fadeUp}
          transition={{ duration: 0.45 }}
          className="mt-6"
        >
          <div className="rounded-xl border bg-card p-4 sm:p-5">
            <div className="mb-3 flex items-center gap-2">
              <Sigma
                className="h-4.5 w-4.5 text-emerald-600 dark:text-emerald-400"
                aria-hidden
              />
              <p className="text-sm font-semibold">
                Tóm tắt pipeline chấm điểm
              </p>
            </div>
            <div className="flex flex-col items-stretch justify-between gap-2 sm:flex-row sm:items-center">
              {[
                "Ghép node dự đoán ↔ GT theo ngưỡng 7.0 µm (bipartite tối ưu)",
                "Đánh dấu cạnh TP / FP / FN",
                "Tính Edge Jaccard + penalty số node dư",
                "Kiểm tra thành phần liên thông quanh mỗi phân bào GT",
                "Gộp điểm: edge (trọng số theo TP+FP+FN) + 0.1 × division",
              ].map((step, i, arr) => (
                <React.Fragment key={i}>
                  <div className="flex flex-1 items-center gap-2 rounded-lg bg-muted/50 px-3 py-2 text-[12px] font-medium leading-snug">
                    <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-emerald-600 font-mono text-[10px] font-bold text-white">
                      {i + 1}
                    </span>
                    {step}
                  </div>
                  {i < arr.length - 1 && (
                    <ArrowRight
                      className="hidden h-4 w-4 shrink-0 text-muted-foreground/60 sm:block"
                      aria-hidden
                    />
                  )}
                </React.Fragment>
              ))}
            </div>
          </div>
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
            <strong>Lưu ý:</strong> {evaluation.note} Tế bào được gắn nhãn thưa
            trong ground-truth — metric đã được thiết kế để xử lý công bằng
            trường hợp này.
          </p>
        </motion.div>
      </section>
    </div>
  );
}
