"use client";

import * as React from "react";
import { motion } from "framer-motion";
import { Compass, PackageCheck, Quote, Timer } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { roadmap, citation } from "@/lib/competition-data";

const fadeUp = {
  initial: { opacity: 0, y: 24 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true, margin: "-60px" },
};

export function GettingStarted() {
  return (
    <section
      id="getting-started"
      className="mx-auto w-full max-w-7xl scroll-mt-24 px-4 pb-16 pt-6 sm:px-6"
      aria-labelledby="roadmap-heading"
    >
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: "-80px" }}
        transition={{ duration: 0.5 }}
        className="mb-8 text-center"
      >
        <h2
          id="roadmap-heading"
          className="text-2xl font-extrabold tracking-tight sm:text-3xl"
        >
          🚀 Lộ trình khởi đầu gợi ý
        </h2>
        <p className="mx-auto mt-2 max-w-2xl text-balance text-sm leading-relaxed text-muted-foreground sm:text-base">
          Chưa biết bắt đầu từ đâu? Đây là hành trình 5 bước từ zero đến
          submission đầu tiên — được sắp xếp theo thứ tự ưu tiên của metric.
        </p>
      </motion.div>

      <ol className="relative ml-3 space-y-5 border-l-2 border-dashed border-emerald-500/30 pl-6 sm:pl-8">
        {roadmap.map((item, i) => (
          <motion.li
            key={item.step}
            {...fadeUp}
            transition={{ delay: i * 0.08, duration: 0.45 }}
            className="relative"
          >
            <span
              className="absolute -left-[39px] flex h-8 w-8 items-center justify-center rounded-full bg-emerald-600 font-mono text-sm font-bold text-white ring-4 ring-background sm:-left-[47px]"
              aria-hidden
            >
              {item.step}
            </span>
            <Card className="transition-shadow hover:shadow-md">
              <CardContent className="flex flex-col gap-2 p-4 sm:p-5">
                <div className="flex flex-wrap items-center gap-2">
                  <p className="text-[15px] font-bold">{item.title}</p>
                  <Badge
                    variant="outline"
                    className="gap-1 border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300"
                  >
                    <Timer className="h-3 w-3" aria-hidden />
                    {item.time}
                  </Badge>
                </div>
                <p className="text-sm leading-relaxed text-muted-foreground">
                  {item.detail}
                </p>
                <p className="flex items-center gap-1.5 text-[13px] font-medium text-emerald-700 dark:text-emerald-400">
                  <PackageCheck className="h-4 w-4 shrink-0" aria-hidden />
                  Sản phẩm: {item.deliver}
                </p>
              </CardContent>
            </Card>
          </motion.li>
        ))}
      </ol>

      {/* Citation */}
      <motion.figure
        {...fadeUp}
        transition={{ duration: 0.5 }}
        className="mt-12"
      >
        <blockquote className="rounded-2xl border bg-muted/40 p-5 sm:p-6">
          <div className="mb-2 flex items-center gap-2 text-sm font-semibold">
            <Quote className="h-4 w-4 text-emerald-600 dark:text-emerald-400" aria-hidden />
            Trích dẫn (Citation)
          </div>
          <p className="text-[13px] italic leading-relaxed text-muted-foreground">
            {citation}
          </p>
        </blockquote>
      </motion.figure>

      <motion.p
        {...fadeUp}
        transition={{ duration: 0.5 }}
        className="mt-6 flex items-center justify-center gap-2 text-center text-xs text-muted-foreground"
      >
        <Compass className="h-3.5 w-3.5" aria-hidden />
        Thông tin tổng hợp từ trang chính thức của cuộc thi trên Kaggle ·
        11/09/2026
      </motion.p>
    </section>
  );
}
