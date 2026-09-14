"use client";

import * as React from "react";
import { motion } from "framer-motion";
import {
  Boxes,
  FileJson,
  FolderTree,
  Fingerprint,
  HardDrive,
  FileText,
  FileCode2,
  CheckSquare,
  FileDown,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { datasetInfo, submissionFormat } from "@/lib/competition-data";

const fadeUp = {
  initial: { opacity: 0, y: 24 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true, margin: "-60px" },
};

const FORMAT_ICONS = [Boxes, FileJson, Fingerprint, FolderTree];

export function DataTab() {
  return (
    <div className="space-y-14">
      {/* Tổng quan dataset */}
      <section aria-labelledby="dataset-heading">
        <div className="mb-5">
          <h3
            id="dataset-heading"
            className="text-xl font-bold tracking-tight sm:text-2xl"
          >
            📦 Dữ liệu cuộc thi
          </h3>
          <p className="mt-1.5 max-w-3xl text-sm leading-relaxed text-muted-foreground">
            {datasetInfo.summary}
          </p>
        </div>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <motion.div {...fadeUp} transition={{ duration: 0.4 }}>
            <div className="flex items-center gap-3 rounded-xl border bg-card p-4">
              <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
                <HardDrive className="h-5 w-5" aria-hidden />
              </span>
              <div>
                <p className="text-lg font-bold leading-tight">{datasetInfo.size}</p>
                <p className="text-xs text-muted-foreground">Dung lượng tải về</p>
              </div>
            </div>
          </motion.div>
          <motion.div {...fadeUp} transition={{ delay: 0.08, duration: 0.4 }}>
            <div className="flex items-center gap-3 rounded-xl border bg-card p-4">
              <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-teal-500/10 text-teal-600 dark:text-teal-400">
                <FileText className="h-5 w-5" aria-hidden />
              </span>
              <div>
                <p className="text-lg font-bold leading-tight">{datasetInfo.files} files</p>
                <p className="text-xs text-muted-foreground">Số lượng file</p>
              </div>
            </div>
          </motion.div>
          <motion.div {...fadeUp} transition={{ delay: 0.16, duration: 0.4 }}>
            <div className="flex items-center gap-3 rounded-xl border bg-card p-4">
              <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-amber-500/10 text-amber-600 dark:text-amber-400">
                <FileDown className="h-5 w-5" aria-hidden />
              </span>
              <div>
                <p className="text-lg font-bold leading-tight">CC0</p>
                <p className="text-xs text-muted-foreground">Public Domain</p>
              </div>
            </div>
          </motion.div>
        </div>
      </section>

      {/* Định dạng chi tiết */}
      <section aria-labelledby="format-heading">
        <h3
          id="format-heading"
          className="mb-5 text-xl font-bold tracking-tight sm:text-2xl"
        >
          🧫 Định dạng dữ liệu chi tiết
        </h3>
        <motion.div {...fadeUp} transition={{ duration: 0.45 }}>
          <Card>
            <CardContent className="pt-6">
              <Accordion type="single" collapsible className="w-full">
                {datasetInfo.format.map((fmt, i) => {
                  const Icon = FORMAT_ICONS[i] ?? Boxes;
                  return (
                    <AccordionItem key={fmt.title} value={`item-${i}`}>
                      <AccordionTrigger className="hover:no-underline">
                        <span className="flex items-center gap-2.5 text-left">
                          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
                            <Icon className="h-4 w-4" aria-hidden />
                          </span>
                          <span className="text-[15px] font-semibold">
                            {fmt.title}
                          </span>
                        </span>
                      </AccordionTrigger>
                      <AccordionContent>
                        <ul className="space-y-2.5 pl-11">
                          {fmt.points.map((point) => (
                            <li
                              key={point.slice(0, 40)}
                              className="flex gap-2 text-sm leading-relaxed text-muted-foreground"
                            >
                              <span
                                className="mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full bg-emerald-500"
                                aria-hidden
                              />
                              {point}
                            </li>
                          ))}
                        </ul>
                      </AccordionContent>
                    </AccordionItem>
                  );
                })}
              </Accordion>
            </CardContent>
          </Card>
        </motion.div>

        <motion.div {...fadeUp} transition={{ duration: 0.45 }} className="mt-4">
          <div className="rounded-xl border border-emerald-500/25 bg-emerald-500/[0.06] p-4 text-sm leading-relaxed">
            <strong>💡 Mẹo quan trọng:</strong> Tập train/test{" "}
            <em>không trùng phôi</em> (embryo-disjoint) — khi chia validation
            cục bộ, hãy chia theo phôi thay vì theo mẫu để mô phỏng điều kiện
            kiểm tra thật.
          </div>
        </motion.div>
      </section>

      {/* Định dạng submission */}
      <section aria-labelledby="submission-heading">
        <div className="mb-5">
          <h3
            id="submission-heading"
            className="text-xl font-bold tracking-tight sm:text-2xl"
          >
            📄 Định dạng file nộp (submission.csv)
          </h3>
          <p className="mt-1.5 max-w-3xl text-sm leading-relaxed text-muted-foreground">
            File nộp gồm hai loại hàng — <strong>node</strong> (vị trí tế bào) và{" "}
            <strong>edge</strong> (liên kết giữa tế bào), nhóm theo dataset.
          </p>
        </div>
        <div className="grid gap-4 lg:grid-cols-5">
          <motion.div
            {...fadeUp}
            transition={{ duration: 0.45 }}
            className="lg:col-span-3"
          >
            <Card className="h-full overflow-hidden">
              <CardHeader className="flex flex-row items-center gap-2 border-b bg-muted/50 py-3">
                <FileCode2
                  className="h-4 w-4 text-emerald-600 dark:text-emerald-400"
                  aria-hidden
                />
                <CardTitle className="font-mono text-sm font-semibold">
                  sample_submission.csv
                </CardTitle>
                <Badge variant="secondary" className="ml-auto text-[10px]">
                  CSV
                </Badge>
              </CardHeader>
              <CardContent className="p-0">
                <pre className="overflow-x-auto p-4 font-mono text-[12.5px] leading-relaxed">
                  <code>
                    {submissionFormat.csvExample.split("\n").map((line, i) => (
                      <span
                        key={i}
                        className={
                          i === 0
                            ? "block font-bold text-emerald-700 dark:text-emerald-400"
                            : line.includes("node")
                              ? "block text-teal-700 dark:text-teal-300"
                              : "block text-amber-700 dark:text-amber-300"
                        }
                      >
                        {line}
                      </span>
                    ))}
                  </code>
                </pre>
              </CardContent>
            </Card>
          </motion.div>
          <motion.div
            {...fadeUp}
            transition={{ delay: 0.1, duration: 0.45 }}
            className="lg:col-span-2"
          >
            <Card className="h-full">
              <CardHeader className="pb-3">
                <CardTitle className="text-[15px]">
                  Quy tắc bắt buộc
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="space-y-2.5">
                  {submissionFormat.rules.map((rule) => (
                    <li
                      key={rule.slice(0, 40)}
                      className="flex gap-2 text-[13px] leading-relaxed text-muted-foreground"
                    >
                      <CheckSquare
                        className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600 dark:text-emerald-400"
                        aria-hidden
                      />
                      {rule}
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          </motion.div>
        </div>
      </section>
    </div>
  );
}
