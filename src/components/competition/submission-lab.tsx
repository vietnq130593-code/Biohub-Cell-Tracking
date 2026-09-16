"use client";

import * as React from "react";
import { motion } from "framer-motion";
import {
  Activity,
  ArrowDown,
  ArrowUp,
  BarChart3,
  BookOpenCheck,
  Calculator,
  CircleAlert,
  CircleCheck,
  ClipboardPaste,
  Database,
  FileSearch,
  FlaskConical,
  Gauge,
  GitBranch,
  GitFork,
  Lightbulb,
  ListChecks,
  Loader2,
  Medal,
  OctagonAlert,
  Play,
  Ruler,
  ScanSearch,
  Target,
  TriangleAlert,
  TrendingUp,
  Unlink,
  Upload,
  Workflow,
  X,
} from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  HELDOUT_MICRO_ADJEJ,
  HELDOUT_STEMS,
} from "@/lib/competition-data";
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { Separator } from "@/components/ui/separator";
import { Slider } from "@/components/ui/slider";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";

/* =========================================================================
 * Hằng số & dữ liệu
 * ========================================================================= */

const BIG_FILE_BYTES = 60 * 1024 * 1024; // 60 MB

const SAMPLE_CSV = [
  "id,dataset,row_type,node_id,t,z,y,x,source_id,target_id",
  "1,mau_44b6,node,101,0,20,100,200,,",
  "2,mau_44b6,node,102,1,21,103,205,,",
  "3,mau_44b6,edge,,,,,,101,102",
  "4,mau_44b6,node,103,2,22,106,210,,",
  "5,mau_44b6,edge,,,,,,102,103",
  "6,mau_44b6,node,104,3,23,109,215,,",
  "7,mau_44b6,edge,,,,,,103,104",
  "8,mau_44b6,node,105,4,24,111,219,,",
  "9,mau_44b6,edge,,,,,,104,105",
  "10,mau_44b6,node,106,4,24,109,213,,",
  "11,mau_44b6,edge,,,,,,104,106",
  "12,mau_44b6,node,107,5,25,113,221,,",
  "13,mau_44b6,edge,,,,,,105,107",
  "14,mau_44b6,node,108,5,25,111,215,,",
  "15,mau_44b6,edge,,,,,,106,108",
  "16,mau_6bba,node,201,0,30,150,150,,",
  "17,mau_6bba,node,202,1,31,153,155,,",
  "18,mau_6bba,edge,,,,,,201,202",
  "19,mau_6bba,node,203,2,32,156,160,,",
  "20,mau_6bba,edge,,,,,,202,203",
  "21,mau_6bba,node,204,3,33,159,165,,",
  "22,mau_6bba,edge,,,,,,203,204",
  "23,mau_6bba,node,205,0,30,50,250,,",
  "24,mau_6bba,node,206,1,31,53,254,,",
  "25,mau_6bba,edge,,,,,,205,206",
].join("\n");

const PLACEHOLDER_CSV = [
  "id,dataset,row_type,node_id,t,z,y,x,source_id,target_id",
  "1,44b6_0113de3b,node,1,0,24,118,205,,",
  "2,44b6_0113de3b,node,2,1,26,120,211,,",
  "3,44b6_0113de3b,edge,,,,,,1,2",
].join("\n");

interface Preset {
  key: string;
  name: string;
  r: number;
  p: number;
  lambda: number;
  divJ: number;
  claim: string;
}

const PRESETS: Preset[] = [
  {
    key: "ver6",
    name: "ver-6 (hiệu chỉnh)",
    r: 98,
    p: 99,
    lambda: 99.5,
    divJ: 20,
    claim: "≈ 0.945 · khớp LB ver-6",
  },
  {
    key: "ver7",
    name: "mục tiêu ver-7",
    r: 98,
    p: 99,
    lambda: 99.6,
    divJ: 21,
    claim: "≈ 0.947 · kỳ vọng port Reyhan",
  },
  {
    key: "top",
    name: "top đầu (tham khảo)",
    r: 99,
    p: 99.5,
    lambda: 99.8,
    divJ: 6,
    claim: "≈ 0.970 · top 1",
  },
];

const LB_ROWS = [
  { label: "ver-6 — team ta (deterministic ×2)", score: 0.945, mine: true },
  { label: `bức tường — 360 đội copy notebook Reyhan`, score: 0.947, mine: false },
  { label: "top 1 · Sergio Alvarez", score: 0.97, mine: false },
] as const;

interface HealthRule {
  label: string;
  good: string;
  warn: string;
  bad: string;
}

const HEALTH_RULES: HealthRule[] = [
  { label: "cạnh/node", good: "≥ 0.80", warn: "0.65–0.80", bad: "< 0.65" },
  { label: "%node không cạnh vào", good: "< 20%", warn: "20–35%", bad: "> 35%" },
  { label: "%track 1-node", good: "< 8%", warn: "8–15%", bad: "> 15%" },
  {
    label: "độ dài track trung vị",
    good: "≥ 20 khung",
    warn: "10–20 khung",
    bad: "< 10 khung",
  },
  {
    label: "phân bào/100 khung",
    good: "2–25 khi node/khung ≥ 15",
    warn: "0–2 hoặc 25–60",
    bad: "0 khi node/khung ≥ 15 (bỏ sót) hoặc > 60 (merge-split)",
  },
];

const TRACK_BINS: { label: string; lo: number; hi: number }[] = [
  { label: "1", lo: 1, hi: 1 },
  { label: "2–3", lo: 2, hi: 3 },
  { label: "4–7", lo: 4, hi: 7 },
  { label: "8–15", lo: 8, hi: 15 },
  { label: "16–31", lo: 16, hi: 31 },
  { label: "32+", lo: 32, hi: Number.POSITIVE_INFINITY },
];

/* =========================================================================
 * Phân tích CSV (thuần client, không gọi API)
 * ========================================================================= */

type Severity = "error" | "warning";

interface Issue {
  severity: Severity;
  title: string;
  detail: string;
  rows: number[];
}

interface IssueDraft extends Issue {
  rows: number[];
}

type BadgeLevel = "good" | "warn" | "bad";

interface BadgeAssessment {
  key: string;
  label: string;
  level: BadgeLevel;
  value: string;
  hint?: string;
}

interface DatasetAnalysis {
  name: string;
  nodes: number;
  edges: number;
  divisions: number;
  frameLabel: string;
  frameSpan: number;
  nodesPerFrame: number;
  edgesPerNode: number;
  pctNoInEdge: number;
  pctSingleTrack: number;
  trackCount: number;
  medianTrackLen: number;
  divisionRate: number;
  trackLengths: number[];
  badges: BadgeAssessment[];
}

interface AnalysisResult {
  datasets: DatasetAnalysis[];
  global: DatasetAnalysis;
  issues: Issue[];
  errorCount: number;
  warningCount: number;
  totalRows: number;
  nodeRows: number;
  edgeRows: number;
  parseMs: number;
  hasHeader: boolean;
  fileName: string | null;
}

interface AnalysisOutput {
  ok: boolean;
  result: AnalysisResult | null;
  fatalIssues: Issue[];
}

interface RawNode {
  dataset: string;
  nodeId: number;
  t: number;
  z: number;
  y: number;
  x: number;
  line: number;
}

interface RawEdge {
  dataset: string;
  source: number;
  target: number;
  line: number;
}

interface ValidEdge {
  dataset: string;
  source: number;
  target: number;
  line: number;
}

const REQUIRED_COLS = [
  "dataset",
  "row_type",
  "node_id",
  "t",
  "z",
  "y",
  "x",
  "source_id",
  "target_id",
];

function parseCsvLine(line: string): string[] {
  const out: string[] = [];
  let cur = "";
  let inQuotes = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i] ?? "";
    if (inQuotes) {
      if (ch === '"') {
        if (line[i + 1] === '"') {
          cur += '"';
          i++;
        } else {
          inQuotes = false;
        }
      } else {
        cur += ch;
      }
    } else if (ch === '"') {
      inQuotes = true;
    } else if (ch === ",") {
      out.push(cur.trim());
      cur = "";
    } else {
      cur += ch;
    }
  }
  out.push(cur.trim());
  return out;
}

function toNum(s: string): number | null {
  if (s === "") return null;
  const v = Number(s);
  return Number.isFinite(v) ? v : null;
}

function median(values: number[]): number {
  if (values.length === 0) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  if (sorted.length % 2 === 1) {
    return sorted[mid] ?? 0;
  }
  const a = sorted[mid - 1] ?? 0;
  const b = sorted[mid] ?? 0;
  return (a + b) / 2;
}

function assessBadges(input: {
  edgesPerNode: number;
  pctNoInEdge: number;
  pctSingleTrack: number;
  medianTrackLen: number;
  divisionRate: number;
  nodesPerFrame: number;
}): BadgeAssessment[] {
  const out: BadgeAssessment[] = [];

  const e = input.edgesPerNode;
  out.push({
    key: "edgesPerNode",
    label: "cạnh/node",
    level: e >= 0.8 ? "good" : e >= 0.65 ? "warn" : "bad",
    value: e.toFixed(2),
  });

  const p = input.pctNoInEdge;
  out.push({
    key: "noInEdge",
    label: "%node không cạnh vào",
    level: p < 20 ? "good" : p <= 35 ? "warn" : "bad",
    value: `${p.toFixed(1)}%`,
  });

  const q = input.pctSingleTrack;
  out.push({
    key: "singleTrack",
    label: "%track 1-node",
    level: q < 8 ? "good" : q <= 15 ? "warn" : "bad",
    value: `${q.toFixed(1)}%`,
  });

  const m = input.medianTrackLen;
  out.push({
    key: "medianTrack",
    label: "trung vị track",
    level: m >= 20 ? "good" : m >= 10 ? "warn" : "bad",
    value: `${Number.isInteger(m) ? m : m.toFixed(1)} khung`,
  });

  const d = input.divisionRate;
  const dense = input.nodesPerFrame >= 15;
  let level: BadgeLevel;
  let hint: string | undefined;
  if (d > 60) {
    level = "bad";
    hint = "nhiễu merge-split";
  } else if (dense && d === 0) {
    level = "bad";
    hint = "bỏ sót phân bào";
  } else if (dense && d >= 2 && d <= 25) {
    level = "good";
  } else if (!dense) {
    level = "warn";
    hint = "mật độ node/khung < 15 — chỉ tham khảo";
  } else if (d < 2) {
    level = "warn";
    hint = "thấp hơn kỳ vọng";
  } else {
    level = "warn";
    hint = "cao — cần kiểm tra merge-split";
  }
  out.push({
    key: "divRate",
    label: "phân bào/100 khung",
    level,
    value: d.toFixed(1),
    hint,
  });

  return out;
}

function analyzeCsv(text: string, fileName: string | null): AnalysisOutput {
  const started = performance.now();
  const lines = text.split(/\r\n|\r|\n/);

  const firstLine = (lines[0] ?? "").replace(/^\uFEFF/, "");
  const firstFields = parseCsvLine(firstLine);
  const hasHeader = firstFields.some((f) => f.trim().toLowerCase() === "row_type");

  const col: Record<string, number> = {};
  if (hasHeader) {
    firstFields.forEach((f, i) => {
      const name = f.trim().toLowerCase();
      if (!(name in col)) col[name] = i;
    });
    const missing = REQUIRED_COLS.filter((c) => !(c in col));
    if (missing.length > 0) {
      return {
        ok: false,
        result: null,
        fatalIssues: [
          {
            severity: "error",
            title: "Thiếu cột bắt buộc",
            detail: `CSV thiếu các cột: ${missing.join(", ")}. Chuẩn: id, dataset, row_type, node_id, t, z, y, x, source_id, target_id (cột id có thể vắng).`,
            rows: [],
          },
        ],
      };
    }
  } else {
    const n = firstFields.length;
    if (n === 10) {
      REQUIRED_COLS.forEach((name, i) => {
        col[name] = i + 1;
      });
    } else if (n === 9) {
      REQUIRED_COLS.forEach((name, i) => {
        col[name] = i;
      });
    } else {
      return {
        ok: false,
        result: null,
        fatalIssues: [
          {
            severity: "error",
            title: "Không nhận dạng được định dạng",
            detail: `Dòng đầu tiên có ${n} cột và không chứa header (không tìm thấy cột "row_type"). Chuẩn: 10 cột (có cột id) hoặc 9 cột (không id).`,
            rows: [],
          },
        ],
      };
    }
  }

  const drafts = new Map<string, IssueDraft>();
  const pushIssue = (
    key: string,
    severity: Severity,
    title: string,
    detail: string,
    row: number
  ): void => {
    const existing = drafts.get(key);
    if (existing) {
      existing.rows.push(row);
      return;
    }
    drafts.set(key, { severity, title, detail, rows: [row] });
  };

  const idx = (name: string): number => col[name] ?? -1;
  const getField = (fields: string[], i: number): string =>
    i >= 0 && i < fields.length ? fields[i] ?? "" : "";

  const nodesByDataset = new Map<string, Map<number, RawNode>>();
  const rawEdges: RawEdge[] = [];
  let nodeRows = 0;
  let edgeRows = 0;
  let totalRows = 0;

  for (let li = hasHeader ? 1 : 0; li < lines.length; li++) {
    const raw = lines[li] ?? "";
    if (raw.trim() === "") continue;
    totalRows++;
    const lineNo = li + 1;
    const fields = parseCsvLine(raw);
    const rowType = getField(fields, idx("row_type")).trim().toLowerCase();
    const dataset = getField(fields, idx("dataset")).trim();

    if (rowType !== "node" && rowType !== "edge") {
      pushIssue(
        "row_type",
        "error",
        "row_type lạ",
        `row_type phải là "node" hoặc "edge" — gặp "${rowType === "" ? "(rỗng)" : rowType}". Hàng bị bỏ qua.`,
        lineNo
      );
      continue;
    }
    if (dataset === "") {
      pushIssue(
        "unparsable",
        "error",
        "Thiếu tên dataset",
        "Cột dataset trống — không thể gán node/cạnh vào dataset nào. Hàng bị bỏ qua.",
        lineNo
      );
      continue;
    }

    if (rowType === "node") {
      nodeRows++;
      const nodeIdRaw = getField(fields, idx("node_id")).trim();
      const nodeId = toNum(nodeIdRaw);
      if (nodeId === null || !Number.isInteger(nodeId) || nodeId <= 0) {
        pushIssue(
          "node_id",
          "error",
          "node_id không hợp lệ (≤ 0 hoặc không nguyên)",
          "node_id phải là số nguyên dương. Hàng bị bỏ qua.",
          lineNo
        );
        continue;
      }
      const t = toNum(getField(fields, idx("t")));
      const z = toNum(getField(fields, idx("z")));
      const y = toNum(getField(fields, idx("y")));
      const x = toNum(getField(fields, idx("x")));
      if (t === null || z === null || y === null || x === null) {
        pushIssue(
          "unparsable",
          "error",
          "Node thiếu tọa độ t/z/y/x",
          "Các cột t, z, y, x của node phải là số. Hàng bị bỏ qua.",
          lineNo
        );
        continue;
      }
      if (
        t < 0 ||
        z < 0 ||
        y < 0 ||
        x < 0 ||
        !Number.isInteger(t) ||
        !Number.isInteger(z) ||
        !Number.isInteger(y) ||
        !Number.isInteger(x)
      ) {
        pushIssue(
          "coords",
          "warning",
          "Node có t/z/y/x âm hoặc không nguyên",
          "Định dạng chuẩn của cuộc thi dùng chỉ số nguyên không âm (voxel). Node vẫn được tính vào thống kê.",
          lineNo
        );
      }
      let dsNodes = nodesByDataset.get(dataset);
      if (!dsNodes) {
        dsNodes = new Map();
        nodesByDataset.set(dataset, dsNodes);
      }
      if (dsNodes.has(nodeId)) {
        pushIssue(
          "dup_node",
          "error",
          "node_id trùng trong 1 dataset",
          `node_id ${nodeIdRaw} bị khai báo lần 2 trong cùng dataset — chỉ giữ node đầu tiên.`,
          lineNo
        );
        continue;
      }
      dsNodes.set(nodeId, { dataset, nodeId, t, z, y, x, line: lineNo });
    } else {
      edgeRows++;
      const source = toNum(getField(fields, idx("source_id")));
      const target = toNum(getField(fields, idx("target_id")));
      if (
        source === null ||
        target === null ||
        !Number.isInteger(source) ||
        !Number.isInteger(target)
      ) {
        pushIssue(
          "unparsable",
          "error",
          "Cạnh thiếu source_id/target_id hợp lệ",
          "source_id và target_id phải là số nguyên. Hàng bị bỏ qua.",
          lineNo
        );
        continue;
      }
      rawEdges.push({ dataset, source, target, line: lineNo });
    }
  }

  if (totalRows === 0) {
    return {
      ok: false,
      result: null,
      fatalIssues: [
        {
          severity: "error",
          title: "Không có hàng dữ liệu",
          detail: "Sau khi bỏ header và dòng trống, không còn hàng dữ liệu nào để phân tích.",
          rows: [],
        },
      ],
    };
  }

  const findOtherDataset = (nodeId: number, exclude: string): string | null => {
    for (const [name, m] of nodesByDataset) {
      if (name !== exclude && m.has(nodeId)) return name;
    }
    return null;
  };

  const validEdges: ValidEdge[] = [];
  const edgeSeen = new Set<string>();

  for (const e of rawEdges) {
    if (e.source === e.target) {
      pushIssue(
        "self_loop",
        "error",
        "Cạnh tự nối (source = target)",
        "Cạnh nối node với chính nó — vô nghĩa trong tracking. Cạnh bị loại.",
        e.line
      );
      continue;
    }
    const dsNodes = nodesByDataset.get(e.dataset);
    const srcOk = dsNodes !== undefined && dsNodes.has(e.source);
    const tgtOk = dsNodes !== undefined && dsNodes.has(e.target);
    if (!srcOk || !tgtOk) {
      const missing: string[] = [];
      if (!srcOk) {
        const other = findOtherDataset(e.source, e.dataset);
        if (other) {
          pushIssue(
            "cross_ds",
            "error",
            "Cạnh nối node khác dataset",
            `Cạnh khai báo dataset ${e.dataset} nhưng node ${e.source} thuộc dataset ${other} — cạnh bị loại.`,
            e.line
          );
        } else {
          missing.push(`source_id ${e.source}`);
        }
      }
      if (!tgtOk) {
        const other = findOtherDataset(e.target, e.dataset);
        if (other) {
          pushIssue(
            "cross_ds",
            "error",
            "Cạnh nối node khác dataset",
            `Cạnh khai báo dataset ${e.dataset} nhưng node ${e.target} thuộc dataset ${other} — cạnh bị loại.`,
            e.line
          );
        } else {
          missing.push(`target_id ${e.target}`);
        }
      }
      if (missing.length > 0) {
        pushIssue(
          "dangling",
          "error",
          "Cạnh treo lơ lửng (node không tồn tại)",
          `Không tìm thấy node: ${missing.join(", ")} trong dataset ${e.dataset} — cạnh bị loại.`,
          e.line
        );
      }
      continue;
    }
    const key = `${e.dataset}|${e.source}|${e.target}`;
    if (edgeSeen.has(key)) {
      pushIssue(
        "dup_edge",
        "warning",
        "Cạnh trùng lặp",
        "Cặp source-target xuất hiện hơn một lần — chỉ tính 1 lần.",
        e.line
      );
      continue;
    }
    edgeSeen.add(key);
    validEdges.push(e);
  }

  const datasetNames = [...nodesByDataset.keys()].sort();
  const datasets: DatasetAnalysis[] = [];
  const allTrackLengths: number[] = [];
  let globalNodes = 0;
  let globalEdges = 0;
  let globalDivisions = 0;
  let globalSpan = 0;
  let globalNoIn = 0;

  for (const name of datasetNames) {
    const dsNodes = nodesByDataset.get(name) ?? new Map<number, RawNode>();
    const nodes = [...dsNodes.values()];
    const edges = validEdges.filter((e) => e.dataset === name);

    const outLines = new Map<number, number[]>();
    const inLines = new Map<number, number[]>();
    for (const e of edges) {
      const out = outLines.get(e.source);
      if (out) out.push(e.line);
      else outLines.set(e.source, [e.line]);
      const inn = inLines.get(e.target);
      if (inn) inn.push(e.line);
      else inLines.set(e.target, [e.line]);

      const srcNode = dsNodes.get(e.source);
      const tgtNode = dsNodes.get(e.target);
      if (srcNode && tgtNode && tgtNode.t !== srcNode.t + 1) {
        pushIssue(
          "time_jump",
          "warning",
          "Cạnh nhảy thời gian (t đích ≠ t nguồn + 1)",
          "Metric chính thức BỎ hẳn cạnh t→t+k khi chấm — cạnh nhảy không phải FP nhưng cũng KHÔNG BAO GIỜ là TP; phải nội suy node giữa.",
          e.line
        );
      }
    }
    for (const linesArr of outLines.values()) {
      if (linesArr.length > 2) {
        for (const ln of linesArr) {
          pushIssue(
            "out_deg",
            "warning",
            "Node có cạnh ra > 2",
            "Metric chỉ coi tối đa 2 cạnh ra mỗi node (fork = phân bào); phần thừa bị bỏ.",
            ln
          );
        }
      }
    }
    for (const linesArr of inLines.values()) {
      if (linesArr.length > 1) {
        for (const ln of linesArr) {
          pushIssue(
            "in_deg",
            "warning",
            "Node có cạnh vào > 1",
            "Hợp nhất 2 tế bào = 1 track, sinh học vô lý.",
            ln
          );
        }
      }
    }

    // thành phần liên thông yếu (union-find)
    const parent = new Map<number, number>();
    for (const n of nodes) parent.set(n.nodeId, n.nodeId);
    const find = (x: number): number => {
      let root = x;
      for (;;) {
        const p = parent.get(root) ?? root;
        if (p === root) break;
        root = p;
      }
      let cur = x;
      while (cur !== root) {
        const p = parent.get(cur) ?? root;
        parent.set(cur, root);
        cur = p;
      }
      return root;
    };
    for (const e of edges) {
      parent.set(find(e.source), find(e.target));
    }
    const sizeByRoot = new Map<number, number>();
    for (const n of nodes) {
      const r = find(n.nodeId);
      sizeByRoot.set(r, (sizeByRoot.get(r) ?? 0) + 1);
    }
    const trackLengths = [...sizeByRoot.values()];

    const nodeCount = nodes.length;
    const edgeCount = edges.length;
    let divisions = 0;
    for (const linesArr of outLines.values()) {
      if (linesArr.length >= 2) divisions++;
    }
    let noIn = 0;
    for (const n of nodes) {
      if ((inLines.get(n.nodeId) ?? []).length === 0) noIn++;
    }
    let minT = Number.POSITIVE_INFINITY;
    let maxT = Number.NEGATIVE_INFINITY;
    for (const n of nodes) {
      if (n.t < minT) minT = n.t;
      if (n.t > maxT) maxT = n.t;
    }
    const span =
      nodes.length > 0 && Number.isFinite(minT) && Number.isFinite(maxT)
        ? maxT - minT + 1
        : 0;
    const singleTracks = trackLengths.filter((l) => l === 1).length;
    const trackCount = trackLengths.length;
    const nodesPerFrame = span > 0 ? nodeCount / span : nodeCount;
    const edgesPerNode = nodeCount > 0 ? edgeCount / nodeCount : 0;
    const pctNoInEdge = nodeCount > 0 ? (noIn / nodeCount) * 100 : 0;
    const pctSingleTrack = trackCount > 0 ? (singleTracks / trackCount) * 100 : 0;
    const medianTrackLen = median(trackLengths);
    const divisionRate = span > 0 ? (divisions / span) * 100 : 0;

    datasets.push({
      name,
      nodes: nodeCount,
      edges: edgeCount,
      divisions,
      frameLabel:
        nodes.length > 0 && span > 0 ? `${minT}–${maxT}` : "—",
      frameSpan: span,
      nodesPerFrame,
      edgesPerNode,
      pctNoInEdge,
      pctSingleTrack,
      trackCount,
      medianTrackLen,
      divisionRate,
      trackLengths,
      badges: assessBadges({
        edgesPerNode,
        pctNoInEdge,
        pctSingleTrack,
        medianTrackLen,
        divisionRate,
        nodesPerFrame,
      }),
    });

    globalNodes += nodeCount;
    globalEdges += edgeCount;
    globalDivisions += divisions;
    globalSpan += span;
    globalNoIn += noIn;
    allTrackLengths.push(...trackLengths);
  }

  const global: DatasetAnalysis = {
    name: "Σ toàn cục",
    nodes: globalNodes,
    edges: globalEdges,
    divisions: globalDivisions,
    frameLabel: `Σ ${globalSpan}`,
    frameSpan: globalSpan,
    nodesPerFrame: globalSpan > 0 ? globalNodes / globalSpan : globalNodes,
    edgesPerNode: globalNodes > 0 ? globalEdges / globalNodes : 0,
    pctNoInEdge: globalNodes > 0 ? (globalNoIn / globalNodes) * 100 : 0,
    pctSingleTrack:
      allTrackLengths.length > 0
        ? (allTrackLengths.filter((l) => l === 1).length / allTrackLengths.length) * 100
        : 0,
    trackCount: allTrackLengths.length,
    medianTrackLen: median(allTrackLengths),
    divisionRate: globalSpan > 0 ? (globalDivisions / globalSpan) * 100 : 0,
    trackLengths: allTrackLengths,
    badges: [],
  };
  global.badges = assessBadges({
    edgesPerNode: global.edgesPerNode,
    pctNoInEdge: global.pctNoInEdge,
    pctSingleTrack: global.pctSingleTrack,
    medianTrackLen: global.medianTrackLen,
    divisionRate: global.divisionRate,
    nodesPerFrame: global.nodesPerFrame,
  });

  const issues: Issue[] = [...drafts.values()].map((d) => ({
    severity: d.severity,
    title: d.title,
    detail: d.detail,
    rows: d.rows,
  }));
  const order: Record<Severity, number> = { error: 0, warning: 1 };
  issues.sort((a, b) => order[a.severity] - order[b.severity]);

  return {
    ok: true,
    result: {
      datasets,
      global,
      issues,
      errorCount: issues.filter((i) => i.severity === "error").length,
      warningCount: issues.filter((i) => i.severity === "warning").length,
      totalRows,
      nodeRows,
      edgeRows,
      parseMs: Math.max(1, Math.round(performance.now() - started)),
      hasHeader,
      fileName,
    },
    fatalIssues: [],
  };
}

/* =========================================================================
 * Mô hình what-if (Tab 2)
 * ========================================================================= */

interface ModelResult {
  M: number;
  Npred: number;
  S: number;
  TP: number;
  FN: number;
  FP: number;
  EJ: number;
  adjEJ: number;
  score: number;
}

function computeModel(r: number, p: number, lambda: number, divJ: number): ModelResult {
  const N = 1000;
  const q = 0.92;
  const M = (r / 100) * N;
  const Npred = M / (p / 100);
  const S = Npred - M;
  const Egt = q * N;
  const TP = (r / 100) * (r / 100) * (lambda / 100) * Egt;
  const FN = Egt - TP;
  const FP = q * Npred - TP;
  const denom = TP + FP + FN;
  const EJ = denom > 0 ? TP / denom : 0;
  const adjEJ = EJ * Math.max(0, 1 - (0.1 * (Npred - N)) / N);
  const score = adjEJ + 0.1 * (divJ / 100);
  return { M, Npred, S, TP, FN, FP, EJ, adjEJ, score };
}

/* =========================================================================
 * Thành phần hiển thị dùng chung
 * ========================================================================= */

type Tone = "neutral" | "good" | "warn" | "bad";

const TONE_DOT: Record<Tone, string> = {
  neutral: "bg-muted-foreground/40",
  good: "bg-emerald-500",
  warn: "bg-amber-500",
  bad: "bg-rose-500",
};

const TONE_TEXT: Record<Tone, string> = {
  neutral: "text-foreground",
  good: "text-emerald-700 dark:text-emerald-300",
  warn: "text-amber-700 dark:text-amber-300",
  bad: "text-rose-700 dark:text-rose-300",
};

function StatChip({
  label,
  value,
  tone = "neutral",
}: {
  label: string;
  value: string;
  tone?: Tone;
}) {
  return (
    <div className="rounded-lg border bg-card px-2.5 py-1.5">
      <p className="flex items-center gap-1 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
        <span className={`h-1.5 w-1.5 rounded-full ${TONE_DOT[tone]}`} aria-hidden />
        {label}
      </p>
      <p className={`font-mono text-sm font-semibold tabular-nums ${TONE_TEXT[tone]}`}>
        {value}
      </p>
    </div>
  );
}

function fmtMed(v: number): string {
  return Number.isInteger(v) ? String(v) : v.toFixed(1);
}

/* =========================================================================
 * Tab 1 — Phiên bản & điểm
 * ========================================================================= */

function VersionsTab() {
  return (
    <div className="space-y-6">
      {/* Registry phiên bản */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {/* ver 9 — FAIL runtime hidden, user gửi lại */}
        <Card className="border-rose-500/40 bg-rose-500/[0.03] md:col-span-2">
          <CardHeader>
            <CardTitle className="flex flex-wrap items-center justify-between gap-2 text-base">
              <span className="flex items-center gap-2">
                <ScanSearch className="h-4 w-4 text-rose-600 dark:text-rose-300" aria-hidden />
                ver 9 · HOCT consensus veto + RLF
              </span>
              <Badge className="gap-1 bg-rose-500 text-[10px] leading-4 text-rose-50 hover:bg-rose-500 sm:text-xs">
                <Loader2 className="h-3 w-3 animate-spin" aria-hidden />
                FAIL RUNTIME HIDDEN · gửi lại 56276434 đang chấm
              </Badge>
            </CardTitle>
            <CardDescription>
              <code className="rounded bg-muted px-1 py-0.5 font-mono text-[0.85em]">
                56261328
              </code>{" "}
              (nộp 19:07 UTC 15/9, kernel{" "}
              <code className="rounded bg-muted px-1 py-0.5 font-mono text-[0.85em]">
                biohub-ver9 v1
              </code>
              ) FAIL rerun hidden test — "exceeded the allowed runtime", không
              có điểm. User đã gửi lại 10:29 UTC 16/9 ({" "}
              <code className="rounded bg-muted px-1 py-0.5 font-mono text-[0.85em]">
                56276434
              </code>
              , cùng kernel v1 — scriptVersionId 350108883 trùng khớp bản fail →
              dự báo fail lần nữa (cùng code + cùng data + cùng limit 12h).
            </CardDescription>
          </CardHeader>
          <CardContent className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <div className="space-y-3">
              <p className="text-sm font-medium">Kiến trúc (trên nền v3-fast):</p>
              <ul className="space-y-1.5 text-sm text-muted-foreground">
                <li>
                  • <span className="font-semibold text-foreground">HOCT consensus veto mode 2</span>{" "}
                  — port nguyên văn sjlee101/biohub-lf-hoctveto-div-b: linker
                  thứ hai độc lập (royerlab general_v0, 6,25M params, arXiv
                  2607.11754) chạy trên node set FINAL mỗi video — mọi cạnh
                  (kể cả division) mà HOCT không đề xuất đều bị bỏ
                </li>
                <li>
                  • <span className="font-semibold text-foreground">Repeat-lineage filter</span>{" "}
                  (port pawanmali divfix): fork có tổ tiên cũng fork → bỏ cạnh
                  con xa hơn · GT thật 0/132 lặp lineage · guard hoàn tác nếu bỏ
                  &gt; 0,5% cạnh
                </li>
                <li>
                  • <span className="font-semibold text-foreground">Tight hardcode</span> per-prefix
                  44b6→5,5 / 6bba→6,5 µm · <span className="font-semibold text-foreground">BỎ PPSWEEP hoàn toàn</span>{" "}
                  (v1/56242181 fail hidden-test runtime vì sweep 86% runtime)
                </li>
                <li>
                  • <span className="font-semibold text-foreground">9 input</span>: 7 dataset của
                  ver-8 + sjlee101/biohub-hoct-020-wheels +
                  musculer/biohub-hoct-general-v0-official
                </li>
              </ul>
              <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 p-3 text-sm">
                <p className="font-mono font-semibold">
                  PHÂN TÍCH FAIL (56261328) — hidden ≈ 5-7× public
                </p>
                <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                  v3-fast 1,74h public PASS ≠ ver-9 2,4h public FAIL → hidden
                  test lớn hơn public ~5-7× (không phải ~2× ước tính cũ). Ba
                  nhân tố cộng dồn: (1) HOCT transformer chi phí ~bậc 2 theo
                  node/frame — hidden là embryo-3 dày nhất (124 forks/video,
                  mật độ 12× train); (2) notebook còn ~2h [ver9-gate] validator
                  replay + HOCT 8 stems — overhead thuần trên rerun; (3) budget
                  max_video_s=900 × nhiều video tích lũy. Cổng §6 rev-2 đã cảnh
                  báo (verdict FALLBACK_V3FAST) — bài học: notebook production
                  phải TỐI THIỂU, bỏ hết validator/gate replay.
                </p>
              </div>
              <div className="rounded-lg border bg-muted/40 p-3 text-sm">
                <p className="flex items-start gap-2">
                  <ListChecks className="mt-0.5 h-4 w-4 shrink-0 text-rose-600 dark:text-rose-300" aria-hidden />
                  <span>
                    <span className="font-mono font-semibold">[ver9-run]</span>{" "}
                    kernel public COMPLETE 2,4h: 240.871 dòng (veto 4 cạnh + RLF
                    bỏ 2) · topology 0 lỗi · [ver9-gate] 8 stems: adjEJ
                    +0,0017 nhưng div_tp 4→3 → verdict FALLBACK_V3FAST · HOCT
                    veto mode 2 kết luận KHÔNG đáng giá trên hidden dày — hướng
                    v10: v3-fast + RLF (chi phí ~0) + bỏ HOCT
                  </span>
                </p>
              </div>
            </div>
            <div className="space-y-2">
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Cơ sở v3-fast (nền của ver-9 — đã chạy xong)
              </p>
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="text-xs">thước đo</TableHead>
                      <TableHead className="text-xs">kết quả</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    <TableRow>
                      <TableCell className="py-1.5 text-xs">
                        runtime GPU T4×2
                      </TableCell>
                      <TableCell className="py-1.5 font-mono text-[11px] tabular-nums">
                        1,74 h ≤ 2 h — hidden ~2× vẫn an toàn
                      </TableCell>
                    </TableRow>
                    <TableRow>
                      <TableCell className="py-1.5 text-xs">adjEJ</TableCell>
                      <TableCell className="py-1.5 font-mono text-[11px] tabular-nums">
                        0,9287 (+0,0025 ≥ −0,0005)
                      </TableCell>
                    </TableRow>
                    <TableRow>
                      <TableCell className="py-1.5 text-xs">division</TableCell>
                      <TableCell className="py-1.5 font-mono text-[11px] tabular-nums">
                        4/1/8 (div_tp 4 = 4 ≥ 0 · div_fp −1 ≤ +3)
                      </TableCell>
                    </TableRow>
                    <TableRow className="bg-muted/50 font-semibold">
                      <TableCell className="py-1.5 text-xs">
                        proxy · submission
                      </TableCell>
                      <TableCell className="py-1.5 font-mono text-[11px] tabular-nums">
                        0,9594 (ppTight5565fb) · 241.355 dòng
                      </TableCell>
                    </TableRow>
                  </TableBody>
                </Table>
              </div>
              <p className="text-[11px] leading-snug text-muted-foreground">
                Kernel{" "}
                <code className="rounded bg-muted px-1 py-0.5 font-mono text-[0.85em]">
                  biohub-ver8 v3
                </code>{" "}
                (push 13:57 UTC 15/9) COMPLETE 15:35 UTC — <span className="font-semibold text-foreground">tất cả cổng PASS</span> · nộp 19:09 UTC (56261360) — CHẤM XONG: <span className="font-semibold text-emerald-700 dark:text-emerald-300">LB 0.947 · HẠNG 165/3602 · HUY CHƯƠNG BẠC</span>.
              </p>
            </div>
          </CardContent>
        </Card>

        {/* ver 8 — v3-fast LB 0.947 HẠNG 165 HUY CHƯƠNG BẠC */}
        <Card className="border-emerald-500/50 bg-emerald-500/[0.04] md:col-span-2">
          <CardHeader>
            <CardTitle className="flex flex-wrap items-center justify-between gap-2 text-base">
              <span className="flex items-center gap-2">
                <GitFork className="h-4 w-4 text-emerald-600 dark:text-emerald-300" aria-hidden />
                ver 8 · Phase D re-parenting
              </span>
              <Badge className="gap-1 bg-emerald-600 text-[10px] leading-4 text-emerald-50 hover:bg-emerald-600 sm:text-xs">
                <Medal className="h-3 w-3" aria-hidden />
                ★ LB 0.947 · HẠNG 165/3602 · HUY CHƯƠNG BẠC
              </Badge>
            </CardTitle>
            <CardDescription>
              Kernel{" "}
              <code className="rounded bg-muted px-1 py-0.5 font-mono text-[0.85em]">
                vietnguyen130593/biohub-ver8
              </code>{" "}
              — v1 (56242181) FAIL runtime; v2 chậm; v3-fast push 13:57 →
              COMPLETE 1,74h → nộp 19:09 UTC (56261360) →{" "}
              <span className="font-semibold text-emerald-700 dark:text-emerald-300">
                LB 0.947 — HẠNG 165/3602 — HUY CHƯƠNG BẠC (16/9)
              </span>
              : vị trí 22/525 đầu cụm 0.947 (ver-7 xưa ~500+ đáy cụm).
            </CardDescription>
          </CardHeader>
          <CardContent className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <div className="space-y-3">
              <p className="text-sm font-medium">Kiến trúc (trên nền ver-7):</p>
              <ul className="space-y-1.5 text-sm text-muted-foreground">
                <li>
                  • <span className="font-semibold text-foreground">DivNet rank</span>{" "}
                  RANK-ONLY W=15 µm — giữ NGUYÊN gate production tau 0.6 /
                  diverge 2.25 (khác ver-7b đã thất bại vì nới gate → div_fp
                  1→21, không nộp)
                </li>
                <li>
                  • <span className="font-semibold text-foreground">Re-parenting division recovery</span> —
                  tháo cạnh sai Y→D2, nối mẹ thật M→D2 khi DivNet + geometry +
                  DeepCenter đồng thuận
                </li>
                <li>
                  • <span className="font-semibold text-foreground">PPSWEEP 16 candidates</span>:
                  6 rp-* (re-parent tuning + rp-off escape) + 7 gốc + 3 adjEJ
                  mới — validator held-out tự chọn theo gate ±0.0005 adjEJ
                </li>
              </ul>
              <div className="rounded-lg border border-emerald-500/40 bg-emerald-500/10 p-3 text-sm">
                <p className="flex items-center gap-2 font-mono font-semibold text-emerald-800 dark:text-emerald-200">
                  <Medal className="h-4 w-4 shrink-0" aria-hidden />
                  KẾT QUẢ LB 16/9: 0.947 — HẠNG 165/3602 — HUY CHƯƠNG BẠC
                </p>
                <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                  Top 5% (cắt hạng 180, dư 15 chỗ) · cùng hiển thị 0.947 nhưng
                  full-precision ≈ 0,9475-0,9479 đầu cụm 525 đội (vị trí 22,
                  vượt 503/525) — ver-7 xưa ~500+ đáy cụm → re-parent + DivNet
                  rank + tight hardcode = +~0,0005-0,0009 full-precision THẬT
                  trên hidden test. Cụm 0.948 kế tiếp: 55 đội (hạng 89-143).
                </p>
              </div>
              <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm">
                <p className="font-mono font-semibold">
                  v1 (56242181) FAIL — rerun hidden test vượt runtime limit
                </p>
                <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                  errorDescription Kaggle: "submission notebook exceeded the allowed
                  runtime… hidden dataset can be larger/smaller/different than the
                  public dataset" · totalBytes=0 · không có điểm. Nguyên nhân: sweep
                  16-19 candidates = 86% runtime (6,87h) → kernel public 6,2h × hidden
                  ~2× ≈ 12,4h vượt hạn 12h. ver-7 (117 phút) pass vì đủ nhanh → ngân sách
                  runtime public ≤ 2h là ràng buộc CỨNG từ giờ.
                </p>
              </div>
              <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-sm">
                <p className="font-mono font-semibold">
                  v3-fast COMPLETE 1,74h — CỔNG PASS (nền &amp; fallback của ver-9)
                </p>
                <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                  Rút sweep còn 1 candidate ppTight5565fb (per-prefix
                  44b6→5.5/6bba→6.5 + fallback global 5.5 cho prefix lạ trên
                  hidden) · runtime 1,74h ≤ 2h · adjEJ +0,0025 · div 4/1/8 ·
                  proxy 0,9594 · 241.355 dòng · REPARENT_EDGE_PROB giữ 0,25
                  (v2: mở chỉ thêm FP).
                </p>
              </div>
            </div>
            <div className="space-y-2">
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Cơ sở Wave-1 (CPU — đã chạy xong)
              </p>
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="text-xs">thí nghiệm</TableHead>
                      <TableHead className="text-xs">kết quả</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    <TableRow>
                      <TableCell className="py-1.5 text-xs">
                        E1 · system view official (8 video held-out)
                      </TableCell>
                      <TableCell className="py-1.5 font-mono text-[11px] tabular-nums">
                        adjEJ 0.9280 · div 2/1/10 · proxy 0.9434
                      </TableCell>
                    </TableRow>
                    <TableRow>
                      <TableCell className="py-1.5 text-xs">
                        E0 · grid 15 combo gate
                      </TableCell>
                      <TableCell className="py-1.5 font-mono text-[11px]">
                        KHÔNG combo tăng div_tp — trần safe-div, mở gate chỉ
                        thêm FP
                      </TableCell>
                    </TableRow>
                    <TableRow className="bg-muted/50 font-semibold">
                      <TableCell className="py-1.5 text-xs">
                        Phân rã 12 sự kiện GT division
                      </TableCell>
                      <TableCell className="py-1.5 font-mono text-[11px]">
                        6/12 → re-parent · 3/12 thiếu detection
                      </TableCell>
                    </TableRow>
                    <TableRow>
                      <TableCell className="py-1.5 text-xs">
                        E2 · PPSWEEP-2 (20 config, wave1 v5)
                      </TableCell>
                      <TableCell className="py-1.5 font-mono text-[11px]">
                        pp-tight-55-65 official 0.9437 (+0.0003) · relaxed8 bị
                        gate adjEJ chặn đúng thiết kế
                      </TableCell>
                    </TableRow>
                  </TableBody>
                </Table>
              </div>
              <p className="text-[11px] leading-snug text-muted-foreground">
                Số liệu từ kernel{" "}
                <code className="rounded bg-muted px-1 py-0.5 font-mono text-[0.85em]">
                  biohub-ver8-wave1
                </code>{" "}
                (CPU, 0 GPU quota) — E1 dùng scorer official 075fc5f đúng luật
                chấm.
              </p>
            </div>
          </CardContent>
        </Card>

        {/* ver 7 — featured */}
        <Card className="border-emerald-500/40 bg-emerald-500/[0.03] md:col-span-2">
          <CardHeader>
            <CardTitle className="flex flex-wrap items-center justify-between gap-2 text-base">
              <span className="flex items-center gap-2">
                <GitBranch className="h-4 w-4 text-emerald-600 dark:text-emerald-300" aria-hidden />
                ver 7 · port notebook Reyhan 0.947
              </span>
              <Badge className="bg-emerald-600 text-[10px] leading-4 hover:bg-emerald-600 sm:text-xs">
                ĐÃ NỘP · ĐANG CHẤM PUBLIC LB (6–12 h)
              </Badge>
            </CardTitle>
            <CardDescription>
              Port nguyên văn notebook public LB 0.947 của Reyhan Ksatria — chỉ
              vá 5 dòng env path sang dataset pilkwang public, SHA256 khớp
              100%.
            </CardDescription>
          </CardHeader>
          <CardContent className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <div className="space-y-3">
              <p className="text-sm font-medium">Kiến trúc (trên nền ver-6):</p>
              <ul className="space-y-1.5 text-sm text-muted-foreground">
                <li>
                  • <span className="font-semibold text-foreground">DeepCenter veto</span> —
                  bỏ node sửa chữa có center-prior thấp (theo độ sáng/tâm),
                  không đụng cạnh đã liên kết
                </li>
                <li>
                  • <span className="font-semibold text-foreground">TTA 8-view × 3 chip</span> —
                  tái xác nhận tâm node mờ
                </li>
                <li>
                  • <span className="font-semibold text-foreground">PPSWEEP</span> tự
                  chọn config{" "}
                  <code className="rounded bg-muted px-1 py-0.5 font-mono text-[0.85em]">
                    tight55
                  </code>{" "}
                  (MOTION_RELINK_TIGHT_UM 5.5)
                </li>
                <li>• Toàn bộ dual-seed ensemble + fusion + safe-div + retention guard của ver-6</li>
              </ul>
              <p className="border-t pt-3 text-xs text-muted-foreground">
                Run T4×2 ~117 phút <span className="font-semibold text-foreground">COMPLETE</span> ·
                submission{" "}
                <span className="font-mono font-semibold text-foreground">241.356 dòng</span> ·
                sha256{" "}
                <code className="rounded bg-muted px-1 py-0.5 font-mono text-[0.85em]">
                  d34533806b3153dd…
                </code>{" "}
                · kernel{" "}
                <code className="rounded bg-muted px-1 py-0.5 font-mono text-[0.85em]">
                  vietnguyen130593/biohub-ver7 v1
                </code>
              </p>
              <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-3 text-sm">
                <p className="font-mono font-semibold">
                  PROXY held-out 0.9490 → 0.9511 (tight55)
                </p>
                <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                  Official eval 8 video held-out (scorer 075fc5f): adjEJ micro{" "}
                  <span className="font-mono font-semibold text-foreground">0.9345</span> ·
                  div 0/0/12. Kỳ vọng public LB ≈{" "}
                  <span className="font-mono font-semibold text-foreground">0.947</span> —
                  rơi vào bức tường 360 đội.
                </p>
              </div>
              <div className="rounded-lg border bg-muted/40 p-3 text-sm">
                <p className="flex items-start gap-2">
                  <Target className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600 dark:text-emerald-300" aria-hidden />
                  <span>
                    Paired A/B vs ver-6 trên 4 video chung:{" "}
                    <span className="font-mono font-semibold">
                      ΔadjEJ +0.0000 (CI95 ±0.0001)
                    </span>{" "}
                    — <strong>KHÔNG regression</strong> · guards{" "}
                    <span className="font-mono font-semibold">5/5</span>
                  </span>
                </p>
              </div>
            </div>
            <div className="space-y-2">
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Official eval — 8 video held-out
              </p>
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="text-xs">video</TableHead>
                      <TableHead className="text-xs">phôi</TableHead>
                      <TableHead className="text-right text-xs">adjEJ</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {HELDOUT_STEMS.map((v) => (
                      <TableRow key={v.stem}>
                        <TableCell className="py-1.5 font-mono text-[11px]">{v.stem}</TableCell>
                        <TableCell className="py-1.5 font-mono text-[11px] text-muted-foreground">
                          {v.embryo}
                        </TableCell>
                        <TableCell className="py-1.5 text-right font-mono text-xs tabular-nums">
                          {v.estimated ? (
                            <span title="video chưa có số riêng — dùng adjEJ micro của 8 video">
                              {HELDOUT_MICRO_ADJEJ.toFixed(4)} *
                            </span>
                          ) : (
                            <span className="font-semibold">{v.adjEJDisplay.toFixed(4)}</span>
                          )}
                        </TableCell>
                      </TableRow>
                    ))}
                    <TableRow className="bg-muted/50 font-semibold">
                      <TableCell className="py-1.5 text-xs">micro (8 video)</TableCell>
                      <TableCell className="py-1.5 text-xs text-muted-foreground">—</TableCell>
                      <TableCell className="py-1.5 text-right font-mono text-xs tabular-nums">
                        {HELDOUT_MICRO_ADJEJ.toFixed(4)}
                      </TableCell>
                    </TableRow>
                  </TableBody>
                </Table>
              </div>
              <p className="text-[11px] leading-snug text-muted-foreground">
                * 4 video chưa công bố số riêng — hiển thị adjEJ micro của cả 8
                video. Phân bào: div 0/0/12 (tp/fp/evaluable) — trọng số 0.1
                nên không đổi kết luận.
              </p>
            </div>
          </CardContent>
        </Card>

        {/* ver 6 */}
        <Card>
          <CardHeader>
            <CardTitle className="flex flex-wrap items-center justify-between gap-2 text-base">
              <span className="flex items-center gap-2">
                <Workflow className="h-4 w-4 text-emerald-600 dark:text-emerald-300" aria-hidden />
                ver 6 · dual-seed ensemble
              </span>
              <Badge
                variant="outline"
                className="border-emerald-500/40 text-[10px] text-emerald-700 dark:text-emerald-300"
              >
                0.945 ×2 — DETERMINISTIC
              </Badge>
            </CardTitle>
            <CardDescription>
              Kernel{" "}
              <code className="rounded bg-muted px-1 py-0.5 font-mono text-[0.85em]">
                vietnguyen130593/biohub-ver6
              </code>{" "}
              — 2 bản nộp đều 0.945 public LB, khớp tuyệt đối.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <ul className="space-y-1.5 text-sm text-muted-foreground">
              <li>
                • 2 lượt phát hiện độc lập — primary + seed{" "}
                <span className="font-mono">314159</span>, jitter &amp; miss-rate khác nhau
              </li>
              <li>
                • Fusion theo src: cả hai thấy → trung bình vị trí · một thấy →
                cửa sổ mờ, nhân dimFactor
              </li>
              <li>
                • Hungarian gate <span className="font-mono">7.2 µm</span> + motion EMA
              </li>
              <li>
                • Safe-div: mẹ ≤ 6.0 µm · chị em ≤ 11.5 µm · khối lượng hợp lý ·
                xác nhận động học sau 1 khung
              </li>
              <li>
                • Retention guard: gap ≤ 2 · bước ≤ 3.6 + 0.4×gap µm (node nội
                suy chỉ cạnh liền khung)
              </li>
            </ul>
            <p className="border-t pt-3 text-xs text-muted-foreground">
              T4×2: v2 2147 s · v3 2290 s · 241.761 dòng (122.975 node +
              118.786 cạnh) · submissions{" "}
              <span className="font-mono">56207468</span> /{" "}
              <span className="font-mono">56210873</span>
            </p>
          </CardContent>
        </Card>

        {/* ver 6 — validator 4 video */}
        <Card>
          <CardHeader>
            <CardTitle className="flex flex-wrap items-center justify-between gap-2 text-base">
              <span className="flex items-center gap-2">
                <Gauge className="h-4 w-4 text-primary" aria-hidden />
                ver 6 · validator nội bộ (rule cũ)
              </span>
              <Badge variant="outline" className="text-[10px]">
                adjEJ 0.9230 · divJ 0.2000
              </Badge>
            </CardTitle>
            <CardDescription>
              4 video validator · PROXY{" "}
              <span className="font-mono font-semibold">0.9430</span> → public LB{" "}
              <span className="font-mono font-semibold">0.945</span>.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="text-xs">phim</TableHead>
                    <TableHead className="text-right text-xs">phân bào GT</TableHead>
                    <TableHead className="text-right text-xs">node</TableHead>
                    <TableHead className="text-right text-xs">cạnh</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {[62, 51, 9, 78].map((div, i) => (
                    <TableRow key={i}>
                      <TableCell className="py-1.5 text-xs">video #{i + 1}</TableCell>
                      <TableCell className="py-1.5 text-right font-mono text-xs tabular-nums">
                        {div}
                      </TableCell>
                      <TableCell className="py-1.5 text-right font-mono text-xs tabular-nums text-muted-foreground">
                        —
                      </TableCell>
                      <TableCell className="py-1.5 text-right font-mono text-xs tabular-nums text-muted-foreground">
                        —
                      </TableCell>
                    </TableRow>
                  ))}
                  <TableRow className="bg-muted/50 font-semibold">
                    <TableCell className="py-1.5 text-xs">tổng</TableCell>
                    <TableCell className="py-1.5 text-right font-mono text-xs tabular-nums">
                      200
                    </TableCell>
                    <TableCell className="py-1.5 text-right font-mono text-xs tabular-nums">
                      122.975
                    </TableCell>
                    <TableCell className="py-1.5 text-right font-mono text-xs tabular-nums">
                      118.786
                    </TableCell>
                  </TableRow>
                </TableBody>
              </Table>
            </div>
            <p className="text-[11px] leading-snug text-muted-foreground">
              PROXY = adjEJ + 0.1 × divJ = 0.9230 + 0.0200 = 0.9430 — chạy
              trước submit để không đốt quota.
            </p>
          </CardContent>
        </Card>

        {/* Local scorer — giữ lại, cập nhật bối cảnh */}
        <Card className="md:col-span-2">
          <CardHeader>
            <CardTitle className="flex flex-wrap items-center justify-between gap-2 text-base">
              <span className="flex items-center gap-2">
                <Gauge className="h-4 w-4 text-teal-600 dark:text-teal-300" aria-hidden />
                Local scorer + validator held-out
              </span>
              <Badge className="bg-teal-600 text-[10px] leading-4 hover:bg-teal-600 sm:text-xs">
                port metric chính thức
              </Badge>
            </CardTitle>
            <CardDescription>
              Chấm offline bằng port metric chính thức (repo BTC royerlab) —
              validator ver-7 dùng 8 video held-out (scorer 075fc5f), paired
              A/B so ver-6 trước khi nộp.
            </CardDescription>
          </CardHeader>
          <CardContent className="grid grid-cols-1 gap-2 text-sm text-muted-foreground sm:grid-cols-3">
            <p>• adjEJ micro-averaged đúng summarise của BTC</p>
            <p>• Phân rã node recall / cạnh TP-FP-FN / division per-window</p>
            <p>• Paired A/B + CI95 — không submit khi có dấu hiệu regression</p>
          </CardContent>
        </Card>
      </div>

      {/* Điểm yếu định lượng */}
      <Card className="border-rose-500/30 bg-rose-500/[0.02]">
        <CardHeader>
          <CardTitle className="flex flex-wrap items-center justify-between gap-2 text-base">
            <span className="flex items-center gap-2">
              <Activity className="h-4 w-4 text-rose-600 dark:text-rose-300" aria-hidden />
              Điểm yếu định lượng của ver-6 / ver-7
            </span>
            <Badge
              variant="outline"
              className="border-rose-500/40 text-[10px] text-rose-700 dark:text-rose-300"
            >
              đo được trên validator — không suy đoán
            </Badge>
          </CardTitle>
          <CardDescription>
            Ba chỗ mất điểm lớn nhất — đúng thứ tự ưu tiên.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            <div className="rounded-lg border p-3">
              <p className="flex items-center gap-2 text-sm font-semibold">
                <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-rose-500/10">
                  <GitFork className="h-4 w-4 text-rose-600 dark:text-rose-400" aria-hidden />
                </span>
                Phân bào 100% FN
              </p>
              <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
                div tp=0 / fp=0 trên validator — mất trắng mảnh 10% điểm
                (0.1 × divJ). Trọng số nhỏ nhưng là khác biệt lớn ở top đầu.
              </p>
            </div>
            <div className="rounded-lg border p-3">
              <p className="flex items-center gap-2 text-sm font-semibold">
                <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-rose-500/10">
                  <Unlink className="h-4 w-4 text-rose-600 dark:text-rose-400" aria-hidden />
                </span>
                Retention worst 0.453
              </p>
              <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
                Tại{" "}
                <code className="rounded bg-muted px-1 py-0.5 font-mono text-[0.85em]">
                  44b6_0b24845f
                </code>{" "}
                — 65/400 khung rơi vào fallback, track đứt nhiều nhất cả tập.
              </p>
            </div>
            <div className="rounded-lg border p-3">
              <p className="flex items-center gap-2 text-sm font-semibold">
                <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-rose-500/10">
                  <ScanSearch className="h-4 w-4 text-rose-600 dark:text-rose-400" aria-hidden />
                </span>
                Over-prediction +17/35%
              </p>
              <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
                2 phim dự đoán thừa node 17% và 35% — bị trừ nhẹ qua hệ số
                penalty của adjEJ.
              </p>
            </div>
          </div>
          <div className="rounded-lg border border-teal-500/30 bg-teal-500/10 p-3.5 text-sm" role="note">
            <p className="flex items-start gap-2">
              <FlaskConical className="mt-0.5 h-4 w-4 shrink-0 text-teal-600 dark:text-teal-300" aria-hidden />
              <span>
                <strong>ver-7b đang chạy trên Kaggle</strong> (Phase C): divnet
                division ranker <span className="font-mono">RANK-ONLY W=15 µm</span> +
                nới gate tau 0.6→1.2 / diverge 2.25→1.0 — nhắm đúng điểm yếu
                số 1 (phân bào 100% FN). divnet AUC{" "}
                <span className="font-mono font-semibold">0.887</span> · upside
                sim ≈ <span className="font-mono font-semibold">0.9556</span>.
              </span>
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Bối cảnh leaderboard */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <TrendingUp className="h-4 w-4 text-primary" aria-hidden />
            Vị trí trên public leaderboard
          </CardTitle>
          <CardDescription>
            Điểm thật của team, bức tường notebook công khai và đỉnh bảng.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3.5">
          {LB_ROWS.map((row) => (
            <div key={row.label}>
              <div className="mb-1 flex items-baseline justify-between gap-2">
                <span className="text-sm font-medium">{row.label}</span>
                <span className="font-mono text-sm font-bold tabular-nums">
                  {row.score.toFixed(3)}
                </span>
              </div>
              <Progress
                value={row.score * 100}
                className="h-2"
                aria-label={`${row.label}: ${row.score.toFixed(3)}`}
              />
            </div>
          ))}
          <div className="flex items-start gap-2 rounded-lg border bg-muted/40 p-3 text-sm">
            <Target className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600 dark:text-emerald-300" aria-hidden />
            <p>
              Ver-7 (port nguyên văn) kỳ vọng chạm{" "}
              <span className="font-mono font-bold">0.947</span> — ngang bức
              tường 360 đội. Vượt tường phải đóng góp kiến trúc riêng: ver-7b
              nhắm phân bào, đúng mảnh điểm còn bỏ trống.
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Insight metric */}
      <Card className="border-teal-500/30 bg-teal-500/[0.04]">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Lightbulb className="h-4.5 w-4.5 text-teal-600 dark:text-teal-300" aria-hidden />
            Metric thực tế khác gì ta tưởng
          </CardTitle>
          <CardDescription>
            Hai cơ chế quan trọng đọc từ code chấm chính thức — ảnh hưởng trực tiếp đến
            chiến lược.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-1.5">
            <p className="text-sm font-semibold">
              1 · Cạnh FP chỉ bị tính khi bám vào node khớp GT
            </p>
            <p className="text-sm leading-relaxed text-muted-foreground">
              Một cạnh dự đoán chỉ là FP khi nguồn khớp một node-GT-có-cạnh-ra{" "}
              <em>hoặc</em> đích khớp một node-GT-có-cạnh-vào. Cạnh nối 2 tế bào không
              được GT chú thích bị{" "}
              <strong className="text-foreground">BỎ QUA — không phạt</strong>.
            </p>
          </div>
          <div className="space-y-1.5">
            <p className="text-sm font-semibold">
              2 · Phạt node thừa rất nhẹ — thiếu còn được thưởng nhẹ
            </p>
            <pre className="overflow-x-auto rounded-md bg-muted/70 p-2.5 font-mono text-xs">
              adjEJ = EJ × (1 − 0.1 × (N_pred − N_true) / N_true)
            </pre>
            <p className="text-sm leading-relaxed text-muted-foreground">
              Hệ số chỉ <span className="font-mono">0.1</span>: dự đoán{" "}
              <strong className="text-foreground">thiếu</strong> node làm hệ số &gt; 1
              (thưởng nhẹ), dự đoán thừa chỉ bị trừ nhẹ — vì vậy over-prediction
              +17/35% của ver-6 chưa phá điểm nhiều.
            </p>
          </div>
          <Separator className="bg-teal-500/20" />
          <p className="flex items-start gap-2 text-sm font-semibold text-teal-700 dark:text-teal-300">
            <Target className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
            Kết luận: giữ cạnh liền mạch (adjEJ ~0.92+) đã xong ở ver-6/7 — mảnh
            điểm lớn còn lại là phân bào (divJ) mà chưa ai trong bức tường
            0.947 làm được.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}

/* =========================================================================
 * Tab 2 — Máy tính điểm
 * ========================================================================= */

function CalculatorTab() {
  const [r, setR] = React.useState(98);
  const [p, setP] = React.useState(99);
  const [lambda, setLambda] = React.useState(99.5);
  const [divJ, setDivJ] = React.useState(20);

  const m = computeModel(r, p, lambda, divJ);
  const activePreset = PRESETS.find(
    (pr) => pr.r === r && pr.p === p && pr.lambda === lambda && pr.divJ === divJ
  );
  const deltaVsVer6 = m.score - 0.945;
  const lambdaLabel = Number.isInteger(lambda) ? String(lambda) : lambda.toFixed(1);
  const pLabel = Number.isInteger(p) ? String(p) : p.toFixed(1);
  const scoreColor =
    m.score >= 0.945
      ? "text-emerald-600 dark:text-emerald-400"
      : m.score >= 0.9
        ? "text-amber-600 dark:text-amber-400"
        : "text-rose-600 dark:text-rose-400";

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card className="h-fit">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Ruler className="h-4 w-4 text-primary" aria-hidden />
              Tham số mô hình
            </CardTitle>
            <CardDescription>
              Kéo 4 thanh trượt — điểm cập nhật tức thì ở bảng bên phải.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            <div>
              <div className="mb-2 flex items-baseline justify-between gap-2">
                <Label className="text-sm font-medium">
                  Node recall{" "}
                  <span className="font-mono text-muted-foreground">(r)</span> — % node
                  GT được phát hiện
                </Label>
                <span className="rounded-md bg-muted px-1.5 py-0.5 font-mono text-sm font-semibold tabular-nums">
                  {r}%
                </span>
              </div>
              <Slider
                value={[r]}
                min={0}
                max={100}
                step={1}
                onValueChange={(v) => setR(v[0] ?? r)}
                aria-label="Node recall"
              />
            </div>
            <div>
              <div className="mb-2 flex items-baseline justify-between gap-2">
                <Label className="text-sm font-medium">
                  Node precision{" "}
                  <span className="font-mono text-muted-foreground">(p)</span> — % node
                  dự đoán là thật
                </Label>
                <span className="rounded-md bg-muted px-1.5 py-0.5 font-mono text-sm font-semibold tabular-nums">
                  {pLabel}%
                </span>
              </div>
              <Slider
                value={[p]}
                min={50}
                max={100}
                step={0.5}
                onValueChange={(v) => setP(v[0] ?? p)}
                aria-label="Node precision"
              />
            </div>
            <div>
              <div className="mb-2 flex items-baseline justify-between gap-2">
                <Label className="text-sm font-medium">
                  Link correctness{" "}
                  <span className="font-mono text-muted-foreground">(λ)</span> — % cạnh
                  nối đúng
                </Label>
                <span className="rounded-md bg-muted px-1.5 py-0.5 font-mono text-sm font-semibold tabular-nums">
                  {lambdaLabel}%
                </span>
              </div>
              <Slider
                value={[lambda]}
                min={0}
                max={100}
                step={0.1}
                onValueChange={(v) => setLambda(v[0] ?? lambda)}
                aria-label="Link correctness"
              />
            </div>
            <div>
              <div className="mb-2 flex items-baseline justify-between gap-2">
                <Label className="text-sm font-medium">
                  Division jaccard{" "}
                  <span className="font-mono text-muted-foreground">(divJ)</span> — độ
                  khớp sự kiện phân bào
                </Label>
                <span className="rounded-md bg-muted px-1.5 py-0.5 font-mono text-sm font-semibold tabular-nums">
                  {divJ}%
                </span>
              </div>
              <Slider
                value={[divJ]}
                min={0}
                max={100}
                step={1}
                onValueChange={(v) => setDivJ(v[0] ?? divJ)}
                aria-label="Division jaccard"
              />
            </div>
            <Separator />
            <div>
              <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Preset
              </p>
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
                {PRESETS.map((pr) => (
                  <Button
                    key={pr.key}
                    type="button"
                    variant="outline"
                    aria-pressed={activePreset?.key === pr.key}
                    onClick={() => {
                      setR(pr.r);
                      setP(pr.p);
                      setLambda(pr.lambda);
                      setDivJ(pr.divJ);
                    }}
                    className={`h-auto flex-col items-start gap-0.5 px-3 py-2 text-left ${
                      activePreset?.key === pr.key
                        ? "border-primary/60 bg-primary/10"
                        : ""
                    }`}
                  >
                    <span className="text-xs font-semibold">{pr.name}</span>
                    <span className="font-mono text-[10px] text-muted-foreground">
                      r{pr.r} · p{pr.p} · λ{pr.lambda} · divJ{pr.divJ}
                    </span>
                    <span className="text-[11px] font-medium text-emerald-700 dark:text-emerald-300">
                      → {pr.claim}
                    </span>
                  </Button>
                ))}
              </div>
              <p className="mt-2 text-[11px] leading-relaxed text-muted-foreground">
                Preset “ver-6 (hiệu chỉnh)” cho ≈{" "}
                <span className="font-mono font-semibold">0.945</span> — khớp điểm
                public LB 0.945 của ver-6 (deterministic × 2 bản), xác nhận mô
                hình phản ánh đúng cơ chế ở vùng điểm cao.
              </p>
            </div>
          </CardContent>
        </Card>

        <Card className="h-fit">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Calculator className="h-4 w-4 text-primary" aria-hidden />
              Mô hình điểm what-if
            </CardTitle>
            <CardDescription>
              N = 1000 node (chuẩn hoá) · q = 0.92 (tỷ lệ cạnh GT). Công thức đầy đủ:
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <pre className="overflow-x-auto rounded-lg bg-muted/60 p-3 font-mono text-[11px] leading-relaxed">
{`M = r·N ;  N_pred = M/p ;  S = N_pred − M
E_gt = q·N
TP = r²·λ·E_gt        (cả 2 đầu phải được phát hiện và nối đúng)
FN = E_gt − TP
FP = q·N_pred − TP
EJ = TP/(TP+FP+FN)
adjEJ = EJ × max(0, 1 − 0.1×(N_pred−N_true)/N_true) ,  N_true = N
score = adjEJ + 0.1 × divJ`}
            </pre>
            <div className="grid grid-cols-3 gap-2">
              <StatChip label="M — node khớp" value={m.M.toFixed(1)} />
              <StatChip label="N_pred" value={m.Npred.toFixed(1)} />
              <StatChip label="S — node thừa" value={m.S.toFixed(1)} />
            </div>
            <div className="grid grid-cols-3 gap-2">
              <StatChip label="TP — cạnh đúng" value={m.TP.toFixed(1)} tone="good" />
              <StatChip label="FP — cạnh giả" value={m.FP.toFixed(1)} tone="bad" />
              <StatChip label="FN — cạnh sót" value={m.FN.toFixed(1)} tone="warn" />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <StatChip label="EJ" value={m.EJ.toFixed(3)} />
              <StatChip label="adjEJ" value={m.adjEJ.toFixed(3)} />
            </div>
            <Separator />
            <div>
              <p className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Điểm tổng — adjEJ + 0.1 × divJ
              </p>
              <div className="flex flex-wrap items-end gap-x-4 gap-y-2">
                <p className={`font-mono text-5xl font-extrabold tabular-nums tracking-tight ${scoreColor}`}>
                  {m.score.toFixed(3)}
                </p>
                <span
                  className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 font-mono text-xs font-semibold tabular-nums ${
                    deltaVsVer6 >= 0
                      ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300"
                      : "border-rose-500/30 bg-rose-500/10 text-rose-700 dark:text-rose-300"
                  }`}
                >
                  {deltaVsVer6 >= 0 ? (
                    <ArrowUp className="h-3 w-3" aria-hidden />
                  ) : (
                    <ArrowDown className="h-3 w-3" aria-hidden />
                  )}
                  {deltaVsVer6 >= 0 ? "+" : "−"}
                  {Math.abs(deltaVsVer6).toFixed(3)} so với ver-6
                </span>
              </div>
              <Progress
                className="mt-3 h-2.5"
                value={Math.min(100, Math.max(0, m.score * 100))}
                aria-label={`Điểm tổng ${m.score.toFixed(3)}`}
              />
              <div className="mt-1.5 flex justify-between font-mono text-[10px] text-muted-foreground">
                <span>0</span>
                <span>0.945 · ver-6</span>
                <span>0.970 · top 1</span>
                <span>1.0</span>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <div
        className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-3.5 text-sm"
        role="note"
      >
        <p className="flex items-start gap-2">
          <Lightbulb
            className="mt-0.5 h-4 w-4 shrink-0 text-amber-600 dark:text-amber-300"
            aria-hidden
          />
          <span>
            <strong>Mô hình xấp xỉ</strong> để hiểu cơ chế điểm — node recall xuất hiện{" "}
            <strong>bình phương</strong> trong TP (cả 2 đầu cạnh đều phải được phát
            hiện) → <strong>tăng recall là đòn bẩy mạnh nhất</strong>.
          </span>
        </p>
      </div>
    </div>
  );
}

/* =========================================================================
 * Tab 3 — Kiểm tra submission.csv
 * ========================================================================= */

function AnalyzerTab() {
  const [source, setSource] = React.useState<"file" | "text">("text");
  const [fileText, setFileText] = React.useState("");
  const [fileName, setFileName] = React.useState<string | null>(null);
  const [fileSize, setFileSize] = React.useState(0);
  const [fileError, setFileError] = React.useState<string | null>(null);
  const [pasted, setPasted] = React.useState("");
  const [result, setResult] = React.useState<AnalysisOutput | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [noData, setNoData] = React.useState(false);
  const [bigWarn, setBigWarn] = React.useState(false);
  const fileInputRef = React.useRef<HTMLInputElement | null>(null);

  const handleFile = (event: React.ChangeEvent<HTMLInputElement>): void => {
    const file = event.target.files?.[0];
    if (!file) return;
    setFileName(file.name);
    setFileSize(file.size);
    setFileError(null);
    setBigWarn(file.size > BIG_FILE_BYTES);
    setSource("file");
    const reader = new FileReader();
    reader.onload = () => {
      setFileText(typeof reader.result === "string" ? reader.result : "");
    };
    reader.onerror = () => {
      setFileError("Không đọc được file — thử dán trực tiếp vào ô văn bản.");
      setFileText("");
    };
    reader.readAsText(file);
  };

  const clearFile = (): void => {
    setFileName(null);
    setFileText("");
    setFileSize(0);
    setFileError(null);
    setBigWarn(false);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const loadSample = (): void => {
    setSource("text");
    setPasted(SAMPLE_CSV);
    setResult(null);
    setNoData(false);
    setBigWarn(false);
  };

  const analyze = (): void => {
    const text = source === "file" ? fileText : pasted;
    if (text.trim() === "") {
      setNoData(true);
      return;
    }
    setNoData(false);
    if (text.length > BIG_FILE_BYTES) setBigWarn(true);
    setLoading(true);
    window.setTimeout(() => {
      let out: AnalysisOutput;
      try {
        out = analyzeCsv(text, source === "file" ? fileName : null);
      } catch {
        out = {
          ok: false,
          result: null,
          fatalIssues: [
            {
              severity: "error",
              title: "Không phân tích được dữ liệu",
              detail: "Đã xảy ra lỗi không xác định — kiểm tra lại định dạng CSV.",
              rows: [],
            },
          ],
        };
      }
      setResult(out);
      setLoading(false);
    }, 40);
  };

  const res = result?.result ?? null;
  const fileLineCount =
    fileText === "" ? 0 : fileText.split(/\r\n|\r|\n/).filter((l) => l.trim() !== "").length;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {/* Nguồn dữ liệu */}
        <Card className="h-fit">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <FileSearch className="h-4 w-4 text-primary" aria-hidden />
              Nguồn dữ liệu
            </CardTitle>
            <CardDescription>
              Mọi xử lý chạy ngay trong trình duyệt — dữ liệu không rời máy bạn.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <ToggleGroup
              type="single"
              variant="outline"
              value={source}
              onValueChange={(v) => {
                if (v === "file" || v === "text") setSource(v);
              }}
              aria-label="Chọn nguồn dữ liệu"
            >
              <ToggleGroupItem value="file" className="gap-1.5 text-xs sm:text-sm">
                <Upload className="h-3.5 w-3.5" aria-hidden />
                Tải file CSV
              </ToggleGroupItem>
              <ToggleGroupItem value="text" className="gap-1.5 text-xs sm:text-sm">
                <ClipboardPaste className="h-3.5 w-3.5" aria-hidden />
                Dán văn bản
              </ToggleGroupItem>
            </ToggleGroup>

            {source === "file" ? (
              <div className="space-y-2">
                <Input
                  ref={fileInputRef}
                  type="file"
                  accept=".csv,text/csv,text/plain"
                  onChange={handleFile}
                  className="cursor-pointer text-xs"
                  aria-label="Chọn file CSV"
                />
                {fileName && (
                  <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
                    <p>
                      <span className="font-medium text-foreground">{fileName}</span> ·{" "}
                      {(fileSize / (1024 * 1024)).toFixed(2)} MB
                      {fileLineCount > 0 && ` · ${fileLineCount} dòng`}
                    </p>
                    <button
                      type="button"
                      onClick={clearFile}
                      className="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 hover:bg-accent hover:text-accent-foreground"
                    >
                      <X className="h-3 w-3" aria-hidden />
                      bỏ chọn file
                    </button>
                  </div>
                )}
                {fileError && (
                  <p className="text-xs font-medium text-rose-600 dark:text-rose-400">
                    {fileError}
                  </p>
                )}
              </div>
            ) : (
              <Textarea
                value={pasted}
                onChange={(e) => setPasted(e.target.value)}
                rows={10}
                className="min-h-40 font-mono text-xs"
                placeholder={PLACEHOLDER_CSV}
                aria-label="Dán nội dung submission.csv"
              />
            )}

            <div className="flex flex-wrap gap-2">
              <Button type="button" variant="outline" size="sm" onClick={loadSample}>
                <FlaskConical className="h-4 w-4" aria-hidden />
                Dán dữ liệu mẫu
              </Button>
              <Button type="button" size="sm" onClick={analyze} disabled={loading}>
                {loading ? (
                  <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
                ) : (
                  <Play className="h-4 w-4" aria-hidden />
                )}
                {loading ? "Đang phân tích…" : "Phân tích"}
              </Button>
            </div>

            {noData && (
              <p className="text-xs font-medium text-rose-600 dark:text-rose-400">
                Chưa có dữ liệu — chọn file hoặc dán văn bản trước khi phân tích (hoặc
                bấm “Dán dữ liệu mẫu”).
              </p>
            )}
            {bigWarn && (
              <p className="flex items-start gap-2 rounded-lg border border-amber-500/30 bg-amber-500/10 p-2.5 text-xs leading-relaxed text-amber-800 dark:text-amber-200">
                <TriangleAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
                Dữ liệu lớn hơn 60 MB — trình duyệt có thể chậm vài giây khi đọc/phân
                tích, nhưng vẫn sẽ thử.
              </p>
            )}
          </CardContent>
        </Card>

        {/* Hướng dẫn (trước phân tích) hoặc tổng quan (sau phân tích) */}
        {!res ? (
          <Card className="h-fit">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <BookOpenCheck className="h-4 w-4 text-primary" aria-hidden />
                Định dạng chuẩn &amp; hướng dẫn
              </CardTitle>
              <CardDescription>
                Mỗi hàng là một node hoặc một cạnh (row_type). Cột{" "}
                <code className="rounded bg-muted px-1 font-mono text-[0.85em]">id</code>{" "}
                là số thứ tự — có thể vắng mặt.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <pre className="overflow-x-auto rounded-lg bg-muted/60 p-3 font-mono text-[11px] leading-relaxed">
{`id,dataset,row_type,node_id,t,z,y,x,source_id,target_id
1,44b6_0113de3b,node,1,0,24,118,205,,
2,44b6_0113de3b,node,2,1,26,120,211,,
3,44b6_0113de3b,edge,,,,,,1,2`}
              </pre>
              <ul className="space-y-1.5 text-muted-foreground">
                <li>
                  • Hàng <strong className="text-foreground">node</strong>: điền node_id
                  + t, z, y, x; bỏ trống source_id/target_id.
                </li>
                <li>
                  • Hàng <strong className="text-foreground">edge</strong>: điền
                  source_id, target_id (cả 2 node phải tồn tại); bỏ trống phần tọa độ.
                </li>
                <li>
                  • Cạnh chuẩn: t đích = t nguồn + 1 (cạnh nhảy thời gian bị metric bỏ).
                </li>
                <li>
                  • node_id duy nhất trong từng dataset; tối đa 2 cạnh ra (fork = phân
                  bào), 1 cạnh vào mỗi node.
                </li>
              </ul>
              <p className="text-xs text-muted-foreground">
                Chưa có file? Bấm{" "}
                <strong className="text-foreground">“Dán dữ liệu mẫu”</strong> rồi{" "}
                <strong className="text-foreground">“Phân tích”</strong> để xem trình
                kiểm tra hoạt động.
              </p>
            </CardContent>
          </Card>
        ) : (
          <Card className="h-fit">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <Activity className="h-4 w-4 text-primary" aria-hidden />
                Tổng quan nhanh
              </CardTitle>
              <CardDescription>
                {res.fileName ? `file: ${res.fileName}` : "nguồn: văn bản dạn"}
                {res.hasHeader ? " · có header" : " · không header (suy đoán cột)"}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                <StatChip label="hàng dữ liệu" value={String(res.totalRows)} />
                <StatChip label="node" value={String(res.nodeRows)} />
                <StatChip label="cạnh" value={String(res.edgeRows)} />
                <StatChip label="dataset" value={String(res.datasets.length)} />
                <StatChip
                  label="lỗi"
                  value={String(res.errorCount)}
                  tone={res.errorCount > 0 ? "bad" : "good"}
                />
                <StatChip
                  label="cảnh báo"
                  value={String(res.warningCount)}
                  tone={res.warningCount > 0 ? "warn" : "good"}
                />
                <StatChip label="thời gian" value={`${res.parseMs} ms`} />
              </div>
            </CardContent>
          </Card>
        )}
      </div>

      {/* Lỗi nghiêm trọng — không phân tích được */}
      {result && !result.ok && (
        <Alert variant="destructive">
          <OctagonAlert aria-hidden />
          <AlertTitle>Không thể phân tích dữ liệu</AlertTitle>
          <AlertDescription>
            {result.fatalIssues.map((f) => (
              <p key={f.title}>
                <strong>{f.title}:</strong> {f.detail}
              </p>
            ))}
          </AlertDescription>
        </Alert>
      )}

      {res && (
        <>
          {/* Kiểm tra hợp lệ */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <ListChecks className="h-4 w-4 text-primary" aria-hidden />
                Kiểm tra hợp lệ
              </CardTitle>
              <CardDescription>
                Lỗi chặt có thể làm file bị từ chối · cảnh báo làm mất điểm.
              </CardDescription>
              <CardAction>
                {res.issues.length === 0 ? (
                  <Badge className="bg-emerald-600">sạch</Badge>
                ) : (
                  <div className="flex gap-1.5">
                    {res.errorCount > 0 && (
                      <Badge className="bg-rose-600">{res.errorCount} lỗi</Badge>
                    )}
                    {res.warningCount > 0 && (
                      <Badge className="bg-amber-500 text-amber-950">
                        {res.warningCount} cảnh báo
                      </Badge>
                    )}
                  </div>
                )}
              </CardAction>
            </CardHeader>
            <CardContent>
              {res.issues.length === 0 ? (
                <p className="flex items-center gap-2 rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-3 text-sm font-medium text-emerald-700 dark:text-emerald-300">
                  <CircleCheck className="h-4 w-4 shrink-0" aria-hidden />
                  Không phát hiện lỗi hay cảnh báo — dữ liệu tuân thủ format.
                </p>
              ) : (
                <div className="max-h-96 space-y-2 overflow-y-auto pr-1">
                  {res.issues.slice(0, 8).map((iss) => (
                    <div
                      key={iss.title}
                      className={`flex items-start gap-2.5 rounded-lg border p-3 ${
                        iss.severity === "error"
                          ? "border-rose-500/25 bg-rose-500/[0.04]"
                          : "border-amber-500/25 bg-amber-500/[0.04]"
                      }`}
                    >
                      {iss.severity === "error" ? (
                        <CircleAlert
                          className="mt-0.5 h-4 w-4 shrink-0 text-rose-500"
                          aria-hidden
                        />
                      ) : (
                        <TriangleAlert
                          className="mt-0.5 h-4 w-4 shrink-0 text-amber-500"
                          aria-hidden
                        />
                      )}
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-medium">
                          {iss.title}{" "}
                          <span className="ml-1 font-mono text-xs font-normal text-muted-foreground">
                            × {iss.rows.length}
                          </span>
                        </p>
                        <p className="mt-0.5 text-xs leading-relaxed text-muted-foreground">
                          {iss.detail}
                        </p>
                        {iss.rows.length > 0 && (
                          <p className="mt-1 font-mono text-[11px] text-muted-foreground">
                            hàng {iss.rows.slice(0, 5).join(", ")}
                            {iss.rows.length > 5 ? " …" : ""}
                          </p>
                        )}
                      </div>
                    </div>
                  ))}
                  {res.issues.length > 8 && (
                    <p className="pt-1 text-center text-xs text-muted-foreground">
                      còn {res.issues.length - 8} lỗi nữa…
                    </p>
                  )}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Thống kê từng dataset */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <Database className="h-4 w-4 text-primary" aria-hidden />
                Thống kê từng dataset
              </CardTitle>
              <CardDescription>
                track = thành phần liên thông yếu (xét cả 2 chiều cạnh) · độ dài trung vị
                = trung vị số node mỗi thành phần.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="text-xs">dataset</TableHead>
                      <TableHead className="text-right text-xs">node</TableHead>
                    <TableHead className="text-right text-xs">cạnh</TableHead>
                    <TableHead className="text-right text-xs">phân bào</TableHead>
                    <TableHead className="text-right text-xs">khung</TableHead>
                    <TableHead className="text-right text-xs">node/khung</TableHead>
                    <TableHead className="text-right text-xs">cạnh/node</TableHead>
                    <TableHead className="text-right text-xs">
                      %node không cạnh vào
                    </TableHead>
                    <TableHead className="text-right text-xs">%track 1-node</TableHead>
                    <TableHead className="text-right text-xs">số track</TableHead>
                    <TableHead className="text-right text-xs">
                      TL track trung vị
                    </TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {res.datasets.map((s) => (
                    <TableRow key={s.name}>
                      <TableCell className="font-mono text-xs">{s.name}</TableCell>
                      <TableCell className="text-right font-mono text-xs tabular-nums">
                        {s.nodes}
                      </TableCell>
                      <TableCell className="text-right font-mono text-xs tabular-nums">
                        {s.edges}
                      </TableCell>
                      <TableCell className="text-right font-mono text-xs tabular-nums">
                        {s.divisions}
                      </TableCell>
                      <TableCell className="text-right font-mono text-xs tabular-nums">
                        {s.frameLabel}
                      </TableCell>
                      <TableCell className="text-right font-mono text-xs tabular-nums">
                        {s.nodesPerFrame.toFixed(1)}
                      </TableCell>
                      <TableCell className="text-right font-mono text-xs tabular-nums">
                        {s.edgesPerNode.toFixed(2)}
                      </TableCell>
                      <TableCell className="text-right font-mono text-xs tabular-nums">
                        {s.pctNoInEdge.toFixed(1)}%
                      </TableCell>
                      <TableCell className="text-right font-mono text-xs tabular-nums">
                        {s.pctSingleTrack.toFixed(1)}%
                      </TableCell>
                      <TableCell className="text-right font-mono text-xs tabular-nums">
                        {s.trackCount}
                      </TableCell>
                      <TableCell className="text-right font-mono text-xs tabular-nums">
                        {fmtMed(s.medianTrackLen)}
                      </TableCell>
                    </TableRow>
                  ))}
                  <TableRow className="bg-muted/50 font-semibold">
                    <TableCell className="text-xs">{res.global.name}</TableCell>
                    <TableCell className="text-right font-mono text-xs tabular-nums">
                      {res.global.nodes}
                    </TableCell>
                    <TableCell className="text-right font-mono text-xs tabular-nums">
                      {res.global.edges}
                    </TableCell>
                    <TableCell className="text-right font-mono text-xs tabular-nums">
                      {res.global.divisions}
                    </TableCell>
                    <TableCell className="text-right font-mono text-xs tabular-nums">
                      {res.global.frameLabel}
                    </TableCell>
                    <TableCell className="text-right font-mono text-xs tabular-nums">
                      {res.global.nodesPerFrame.toFixed(1)}
                    </TableCell>
                    <TableCell className="text-right font-mono text-xs tabular-nums">
                      {res.global.edgesPerNode.toFixed(2)}
                    </TableCell>
                    <TableCell className="text-right font-mono text-xs tabular-nums">
                      {res.global.pctNoInEdge.toFixed(1)}%
                    </TableCell>
                    <TableCell className="text-right font-mono text-xs tabular-nums">
                      {res.global.pctSingleTrack.toFixed(1)}%
                    </TableCell>
                    <TableCell className="text-right font-mono text-xs tabular-nums">
                      {res.global.trackCount}
                    </TableCell>
                    <TableCell className="text-right font-mono text-xs tabular-nums">
                      {fmtMed(res.global.medianTrackLen)}
                    </TableCell>
                  </TableRow>
                </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>

          {/* Chuẩn sức khoẻ */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <Gauge className="h-4 w-4 text-primary" aria-hidden />
                Chuẩn sức khoẻ (quy chuẩn nội bộ)
              </CardTitle>
              <CardDescription>
                Mỗi dataset và toàn cục được chấm 5 badge theo ngưỡng quy chiếu.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {[...res.datasets, res.global].map((s) => {
                const goodCount = s.badges.filter((b) => b.level === "good").length;
                return (
                  <div key={s.name} className="rounded-lg border p-3">
                    <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                      <p className="font-mono text-xs font-semibold sm:text-sm">{s.name}</p>
                      <p className="text-[11px] text-muted-foreground">
                        {goodCount}/{s.badges.length} chuẩn đạt
                      </p>
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      {s.badges.map((b) => (
                        <span
                          key={b.key}
                          title={b.hint}
                          className="inline-flex max-w-full items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px]"
                        >
                          <span
                            className={`h-2 w-2 shrink-0 rounded-full ${
                              b.level === "good"
                                ? "bg-emerald-500"
                                : b.level === "warn"
                                  ? "bg-amber-500"
                                  : "bg-rose-500"
                            }`}
                            aria-hidden
                          />
                          <span className="text-muted-foreground">{b.label}</span>
                          <span className="font-mono font-semibold tabular-nums">
                            {b.value}
                          </span>
                          {b.hint && (
                            <span className="text-muted-foreground">({b.hint})</span>
                          )}
                        </span>
                      ))}
                    </div>
                  </div>
                );
              })}
              <Separator />
              <div className="rounded-lg bg-muted/40 p-3 text-xs text-muted-foreground">
                <p className="mb-1.5 font-medium text-foreground">Ngưỡng quy chuẩn</p>
                <ul className="space-y-1">
                  {HEALTH_RULES.map((rule) => (
                    <li key={rule.label} className="flex flex-wrap items-center gap-x-2 gap-y-1">
                      <span className="min-w-44 shrink-0">{rule.label}:</span>
                      <span className="inline-flex items-center gap-1">
                        <span className="h-2 w-2 rounded-full bg-emerald-500" aria-hidden />
                        {rule.good}
                      </span>
                      <span className="inline-flex items-center gap-1">
                        <span className="h-2 w-2 rounded-full bg-amber-500" aria-hidden />
                        {rule.warn}
                      </span>
                      <span className="inline-flex items-center gap-1">
                        <span className="h-2 w-2 rounded-full bg-rose-500" aria-hidden />
                        {rule.bad}
                      </span>
                    </li>
                  ))}
                </ul>
                <p className="mt-2 italic leading-relaxed">
                  Các ngưỡng là quy chiếu heuristic từ ver 1 + tiên nghiệm sinh học
                  (chu kỳ tế bào ~2 h, phim 100 khung ≈ 2.5 h) — không phải chuẩn chính
                  thức của BTC.
                </p>
              </div>
            </CardContent>
          </Card>

          {/* Phân bố độ dài track */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <BarChart3 className="h-4 w-4 text-primary" aria-hidden />
                Phân bố độ dài track
              </CardTitle>
              <CardDescription>
                {res.global.trackCount} track (toàn cục) · trung vị{" "}
                {fmtMed(res.global.medianTrackLen)} node ·{" "}
                {res.global.pctSingleTrack.toFixed(1)}% track 1-node
              </CardDescription>
            </CardHeader>
            <CardContent>
              {(() => {
                const counts = TRACK_BINS.map((bin) =>
                  res.global.trackLengths.filter((l) => l >= bin.lo && l <= bin.hi).length
                );
                const max = Math.max(...counts, 1);
                const ZONE = 112;
                return (
                  <div
                    className="flex items-end gap-1.5 sm:gap-3"
                    role="img"
                    aria-label={`Histogram độ dài track: ${TRACK_BINS.map(
                      (b, i) => `${b.label} là ${counts[i]}`
                    ).join(", ")}`}
                  >
                    {TRACK_BINS.map((bin, i) => {
                      const count = counts[i] ?? 0;
                      const h = count === 0 ? 0 : Math.max(6, Math.round((count / max) * ZONE));
                      return (
                        <div
                          key={bin.label}
                          className="flex flex-1 flex-col items-center justify-end gap-1.5"
                        >
                          <span className="font-mono text-xs font-semibold tabular-nums">
                            {count}
                          </span>
                          <div
                            className="w-full max-w-16 rounded-t-md bg-gradient-to-t from-primary/50 to-primary"
                            style={{ height: h }}
                            aria-hidden
                          />
                          <span className="whitespace-nowrap text-[10px] text-muted-foreground sm:text-[11px]">
                            {bin.label}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                );
              })()}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}

/* =========================================================================
 * Component chính
 * ========================================================================= */

export default function SubmissionLab() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-60px" }}
      transition={{ duration: 0.45 }}
    >
      <Tabs defaultValue="versions" className="w-full">
        <TabsList className="mx-auto mb-8 grid h-auto w-full max-w-2xl grid-cols-3 gap-1 rounded-xl p-1">
          <TabsTrigger
            value="versions"
            className="gap-1.5 px-2 py-2 text-xs font-medium data-[state=active]:shadow-sm sm:px-3 sm:text-sm"
          >
            <GitBranch className="h-4 w-4" aria-hidden />
            Phiên bản &amp; điểm
          </TabsTrigger>
          <TabsTrigger
            value="calculator"
            className="gap-1.5 px-2 py-2 text-xs font-medium data-[state=active]:shadow-sm sm:px-3 sm:text-sm"
          >
            <Calculator className="h-4 w-4" aria-hidden />
            Máy tính điểm
          </TabsTrigger>
          <TabsTrigger
            value="analyzer"
            className="gap-1.5 px-2 py-2 text-xs font-medium data-[state=active]:shadow-sm sm:px-3 sm:text-sm"
          >
            <FileSearch className="h-4 w-4" aria-hidden />
            <span className="hidden sm:inline">Kiểm tra submission.csv</span>
            <span className="sm:hidden">Kiểm tra CSV</span>
          </TabsTrigger>
        </TabsList>
        {/* forceMount giữ state 3 tab khi chuyển đổi (ẩn khi không active) */}
        <TabsContent value="versions" forceMount className="mt-0 data-[state=inactive]:hidden">
          <VersionsTab />
        </TabsContent>
        <TabsContent value="calculator" forceMount className="mt-0 data-[state=inactive]:hidden">
          <CalculatorTab />
        </TabsContent>
        <TabsContent value="analyzer" forceMount className="mt-0 data-[state=inactive]:hidden">
          <AnalyzerTab />
        </TabsContent>
      </Tabs>
    </motion.div>
  );
}
