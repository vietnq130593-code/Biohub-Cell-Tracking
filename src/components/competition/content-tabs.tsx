"use client";

import * as React from "react";
import { motion } from "framer-motion";
import {
  BookOpen,
  Database,
  Gauge,
  BarChart3,
} from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { OverviewTab } from "@/components/competition/overview-tab";
import { DataTab } from "@/components/competition/data-tab";
import { EvaluationTab } from "@/components/competition/evaluation-tab";
import { LeaderboardTab } from "@/components/competition/leaderboard-tab";

const TABS = [
  { value: "overview", label: "Tổng quan", icon: BookOpen },
  { value: "data", label: "Dữ liệu & Nộp bài", icon: Database },
  { value: "evaluation", label: "Đánh giá", icon: Gauge },
  { value: "leaderboard", label: "Xếp hạng", icon: BarChart3 },
];

export function ContentTabs() {
  return (
    <section
      id="noi-dung"
      className="mx-auto w-full max-w-7xl scroll-mt-24 px-4 py-14 sm:px-6 sm:py-20"
      aria-label="Nội dung đề bài"
    >
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: "-80px" }}
        transition={{ duration: 0.5 }}
        className="mb-8 text-center"
      >
        <h2 className="text-2xl font-extrabold tracking-tight sm:text-3xl">
          Tìm hiểu đề bài chi tiết
        </h2>
        <p className="mx-auto mt-2 max-w-2xl text-balance text-sm leading-relaxed text-muted-foreground sm:text-base">
          Mọi thứ bạn cần biết trước khi bắt tay vào làm: nhiệm vụ, dữ liệu,
          cách chấm điểm và mức độ cạnh tranh hiện tại.
        </p>
      </motion.div>

      <Tabs defaultValue="overview" className="w-full">
        <TabsList className="mx-auto mb-8 grid h-auto w-full max-w-2xl grid-cols-2 gap-1 rounded-xl p-1 sm:grid-cols-4">
          {TABS.map((tab) => (
            <TabsTrigger
              key={tab.value}
              value={tab.value}
              className="gap-1.5 px-3 py-2 text-xs font-medium data-[state=active]:shadow-sm sm:text-sm"
            >
              <tab.icon className="h-4 w-4" aria-hidden />
              {tab.label}
            </TabsTrigger>
          ))}
        </TabsList>
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
        >
          <TabsContent value="overview" className="mt-0">
            <OverviewTab />
          </TabsContent>
          <TabsContent value="data" className="mt-0">
            <DataTab />
          </TabsContent>
          <TabsContent value="evaluation" className="mt-0">
            <EvaluationTab />
          </TabsContent>
          <TabsContent value="leaderboard" className="mt-0">
            <LeaderboardTab />
          </TabsContent>
        </motion.div>
      </Tabs>
    </section>
  );
}
