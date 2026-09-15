/**
 * Dữ liệu cuộc thi Kaggle: Biohub - Cell Tracking During Development
 * Nguồn: https://www.kaggle.com/competitions/biohub-cell-tracking-during-development/overview
 * Tổng hợp ngày 11/09/2026 · cập nhật kết quả Kaggle thật của các phiên bản pipeline
 */

export const COMPETITION_URL = "https://www.kaggle.com/competitions/biohub-cell-tracking-during-development";

export const competition = {
  title: "Biohub — Cell Tracking During Development",
  subtitle: "Phát hiện và theo dõi tế bào cá ngựa vằn trong không gian 3D và thời gian",
  host: "Chan Zuckerberg Biohub",
  type: "Research Code Competition",
  description:
    "Mục tiêu của bạn là xây dựng thuật toán phát hiện (detect), theo dõi (track) và liên kết (link) các tế bào qua thời gian trong dữ liệu kính hiển vi 3D, bao gồm cả việc nhận diện chính xác các lần phân bào (cell division) và tái dựng phả hệ tế bào (lineage reconstruction). Bạn sẽ làm việc với các bộ dữ liệu kính hiển vi thật để xây dựng các phương pháp mạnh mẽ, có thể xử lý quần thể tế bào dày đặc, nhiễu ảnh và các cấu trúc sinh học phức tạp.",
  impact:
    "Công trình của bạn sẽ loại bỏ nút thắt cổ chai khổng lồ trong nghiên cứu sinh học và giúp các nhà khoa học định lượng các viên gạch nền tảng của sự sống.",
  stats: {
    entrants: 12477,
    participants: 3716,
    teams: 3386,
    submissions: 62301,
  },
  tags: ["Image", "Video", "Computer Vision", "Object Detection", "Biology", "Custom Metric"],
} as const;

export const codeRequirements = [
  { label: "CPU Notebook", value: "≤ 12 giờ runtime", icon: "cpu" },
  { label: "GPU Notebook", value: "≤ 12 giờ runtime", icon: "gpu" },
  { label: "Internet", value: "Bị vô hiệu hóa khi rerun", icon: "wifi-off" },
  { label: "Dữ liệu ngoài", value: "Được phép nếu công khai & miễn phí (kể cả model tiền huấn luyện)", icon: "database" },
  { label: "Tên file nộp", value: "phải là submission.csv", icon: "file" },
  { label: "Hình thức", value: "Chỉ nộp qua Kaggle Notebooks", icon: "notebook" },
] as const;

export const datasetInfo = {
  summary:
    "Mỗi mẫu dữ liệu là một đoạn video 3D+time ngắn của các tế bào phôi cá ngựa vằn (zebrafish) được nhuộm huỳnh quang, lưu dưới dạng Zarr v3. Nhiệm vụ của bạn là phát hiện tế bào ở mỗi mốc thời gian và liên kết chúng qua thời gian, tạo thành một đồ thị tracking gồm các node (vị trí tế bào) và các edge (liên kết giữa các tế bào qua thời gian).",
  size: "87.61 GB",
  files: "24.886",
  license: "CC0: Public Domain",
  format: [
    {
      title: "Thể tích ảnh (.zarr)",
      points: [
        "Mảng duy nhất tại path 0/ với shape (T, Z, Y, X) — điển hình (100, 64, 256, 256), kiểu uint16",
        "Mỗi chunk chứa đúng 1 mốc thời gian: (1, 64, 256, 256), nén bằng blosc/zstd",
        "Chunk của mốc thời gian t nằm tại 0/c/{t}/0/0/0; metadata mảng (shape, dtype, codecs) nằm trong 0/zarr.json",
        "Thang vật lý voxel: z = 1.625 µm/voxel, y = x = 0.40625 µm/voxel",
      ],
    },
    {
      title: "Ground-truth (.geff) — chỉ có ở tập train",
      points: [
        "nodes/ids — mảng ID của các node",
        "nodes/props/{t,z,y,x}/values — tọa độ trọng tâm nguyên (voxel) của từng node",
        "edges/ids — mảng cạnh (N, 2) gồm cặp (source_id, target_id)",
        "Chú thích thưa (sparse): không phải tế bào nào ở frame nào cũng được gắn nhãn. Trường estimated_number_of_nodes trong metadata (zarr.json) ước lượng số tế bào thật của mỗi mẫu",
      ],
    },
    {
      title: "Danh tính phôi (Embryo Identity)",
      points: [
        "Tên thư mục theo mẫu {embryo_id}_{field_of_view}, ví dụ: 44b6_0049_0438_1330_1273",
        "Đoạn đầu xác định phôi mà mẫu lấy từ đó; nhiều mẫu có thể chung một phôi",
        "Tập train và test không trùng phôi (embryo-disjoint) — không có phôi nào xuất hiện ở cả hai tập",
      ],
    },
    {
      title: "Các thư mục",
      points: [
        "train/ — mẫu huấn luyện, mỗi mẫu có cặp .zarr (ảnh) + .geff (ground-truth)",
        "test/ — mẫu test ví dụ (bản sao từ train), chỉ có ảnh .zarr, không có ground-truth. Khi notebook được rerun để chấm, một tập test ẩn mới được thay vào, kích thước xấp xỉ tập train",
        "sample_submission.csv — file nộp mẫu demonstrating đúng định dạng",
      ],
    },
  ],
} as const;

export const evaluation = {
  formula: "score = adjusted_edge_jaccard + 0.1 × division_jaccard",
  note: "Do bản chất của metric, điểm số hoàn toàn có thể vượt quá 1.0. Ground-truth gắn nhãn thưa và metric đã tính đến điều này.",
  edgeJaccard: {
    title: "Edge Jaccard (điều chỉnh) — đo độ chính xác liên kết",
    steps: [
      "Các node dự đoán được ghép với node ground-truth ở từng mốc thời gian bằng phép gán song phân tối ưu (optimal bipartite assignment) trên khoảng cách trọng tâm đã hiệu chỉnh theo thang vật lý — ngưỡng tối đa 7.0 µm (thang vật lý z = 1.625, y = x = 0.40625 µm/voxel).",
      "Một cạnh dự đoán được tính là True Positive (TP) khi cả hai đầu của nó khớp với các node ground-truth mà ground-truth nối bằng một cạnh.",
      "Edge Jaccard = TP / (TP + FP + FN), được điều chỉnh bằng hình phạt (penalty) nếu dự đoán quá nhiều node so với tổng số node thật.",
    ],
  },
  divisionJaccard: {
    title: "Division Jaccard — đo độ chính xác phát hiện phân bào",
    steps: [
      "Một lần phân bào (cell division) là một node có từ hai cạnh đi ra trở lên (outgoing edges).",
      "Với mỗi lần phân bào trong ground-truth, đồ thị dự đoán được kiểm tra xem có một thành phần liên thông phủ giai đoạn trước khi tách và chạm vào cả hai dòng con gái (daughter lineages) hay không.",
      "TP/FP/FN của phân bào được tính và gộp thành Jaccard dạng micro-averaged.",
    ],
  },
  aggregation:
    "Adjusted Edge Jaccard của từng mẫu được lấy trung bình có trọng số theo (TP + FP + FN); Division Jaccard được micro-averaged trên toàn bộ mẫu.",
} as const;

export const submissionFormat = {
  csvExample: `id,dataset,row_type,node_id,t,z,y,x,source_id,target_id
0,44b6,node,1,0,32,128,128,-1,-1
1,44b6,node,2,1,33,130,125,-1,-1
2,6bba,edge,-1,-1,-1,-1,-1,1,2`,
  rules: [
    "Hàng node: row_type=node, kèm node_id, t, z, y, x là tọa độ trọng tâm nguyên (voxel). source_id và target_id để -1.",
    "Hàng edge: row_type=edge, source_id và target_id trỏ tới ID của node. node_id, t, z, y, x để -1.",
    "Cột id là chỉ số vứt đi bắt buộc (số nguyên liên tiếp).",
    "Cột dataset phải khớp tên thư mục trong tập test (không kèm đuôi .zarr).",
    "Mọi dataset trong tập test đều phải xuất hiện trong file nộp.",
  ],
} as const;

export const leaderboardTop = [
  { rank: 1, team: "Sergio Alvarez", score: 0.97, entries: 60 },
  { rank: 2, team: "Soheil Ayati", score: 0.967, entries: 55 },
  { rank: 3, team: "unicellular", score: 0.966, entries: 112 },
  { rank: 4, team: "Tang", score: 0.964, entries: 123 },
  { rank: 5, team: "yu4u", score: 0.963, entries: 73 },
  { rank: 6, team: "z7777", score: 0.962, entries: 55 },
  { rank: 7, team: "que la cuenten como quieran", score: 0.958, entries: 8 },
  { rank: 8, team: "Masha Mikhisor", score: 0.958, entries: 36 },
  { rank: 9, team: "tatsutaka", score: 0.957, entries: 36 },
  { rank: 10, team: "TWEAK", score: 0.957, entries: 302 },
] as const;

export const leaderboardNote =
  "Bảng xếp hạng công khai được tính trên khoảng 29% dữ liệu test. Kết quả cuối cùng sẽ dựa trên 71% còn lại, vì vậy thứ hạng chung kết có thể thay đổi.";

export const citation =
  "Thibaut Goldsborough, Jordão Bragantini, Xiang Zhao, Gordon Leary, Teun Huijben, Ilan da Silva Theodoro, Kyle Harrington, Chi-Li Chiu, Walter Reade, María Cruz, and Loïc A. Royer. Biohub - Cell Tracking During Development. https://www.kaggle.com/competitions/biohub-cell-tracking-during-development, 2026. Kaggle.";

export const roadmap = [
  {
    step: 1,
    title: "Hiểu dữ liệu Zarr & GEFF",
    time: "1–2 ngày",
    detail:
      "Mở vài mẫu train bằng zarr-python, đọc 0/zarr.json, render vài timepoint bằng matplotlib để làm quen ảnh huỳnh quang. Đọc ground-truth .geff, vẽ đồ thị node/edge lên ảnh để hiểu cách chú thích thưa (sparse).",
    deliver: "Notebook EDA với trực quan hóa ảnh + overlay GT",
  },
  {
    step: 2,
    title: "Baseline phát hiện tế bào (detection)",
    time: "3–5 ngày",
    detail:
      "Bắt đầu đơn giản: threshold intensities + connected components / LoG blob detection hoặc chạy sẵn mô hình như Cellpose / StarDist 3D. Đánh giá node matching theo ngưỡng 7.0 µm đã hiệu chỉnh thang vật lý.",
    deliver: "Node recall tốt trên tập validation tự chia theo phôi",
  },
  {
    step: 3,
    title: "Ghép liên kết qua thời gian (tracking)",
    time: "1 tuần",
    detail:
      "Gán song phân (Hungarian) giữa node ở frame t và t+1 trên khoảng cách hiệu chỉnh — hoặc dùng tracker mạnh hơn như bTrack / LapTrack. Sinh edges cho submission.csv.",
    deliver: "Pipeline sinh node + edge đầu tiên, nộp bài đầu tiên",
  },
  {
    step: 4,
    title: "Phát hiện phân bào (division)",
    time: "1–2 tuần",
    detail:
      "Phân bào chỉ chiếm 0.1 trọng số nhưng tạo khác biệt lớn ở top đầu. Tìm node có 2 cạnh đi ra: tăng động học bất thường, hình dạng thoi, khoảng cách con gái tăng dần sau khi tách.",
    deliver: "Division detector + validation qua division Jaccard",
  },
  {
    step: 5,
    title: "Tối ưu & submit",
    time: "Liên tục",
    detail:
      "Chạy cross-validation theo phôi (embryo-disjoint), tinh chỉnh ngưỡng phát hiện, kiểm tra submission cục bộ trước khi nộp. Chú ý giới hạn 12 giờ runtime và không có internet khi rerun.",
    deliver: "submission.csv cuối cùng vượt qua local scorer trước khi nộp",
  },
] as const;

/* =========================================================================
 * KẾT QUẢ KAGGLE THẬT của các phiên bản pipeline đã nộp / đang chạy
 * (số liệu đo được — không suy đoán)
 * ========================================================================= */

export type KaggleRunStatus = "COMPLETE" | "PENDING" | "RUNNING" | "SUBMITTED";

export interface KaggleVersionResult {
  id: string;
  label: string;
  /** Kernel / submission reference trên Kaggle */
  kaggleRef: string;
  /** Điểm public leaderboard; null = chưa chấm xong */
  lbScore: number | null;
  submittedAt: string;
  status: KaggleRunStatus;
  /** Thời lượng chạy trên Kaggle (giây); null = chưa xong */
  runSeconds: number | null;
  /** Số dòng submission.csv */
  submissionRows: number | null;
  /** Điểm proxy trên validator nội bộ (rule cũ) */
  proxy: number | null;
  adjEJ: number | null;
  divJ: number | null;
  notes: string[];
}

export const KAGGLE_RESULTS: KaggleVersionResult[] = [
  {
    id: "ver6-v2",
    label: "Ver 6 · bản v2",
    kaggleRef: "vietnguyen130593/biohub-ver6 · submission 56207468",
    lbScore: 0.945,
    submittedAt: "2026-09 · đã chấm",
    status: "COMPLETE",
    runSeconds: 2147,
    submissionRows: 241761,
    proxy: 0.943,
    adjEJ: 0.923,
    divJ: 0.2,
    notes: [
      "Kernel vietnguyen130593/biohub-ver6 — dual-seed ensemble + bidirectional fusion + safe-div + retention guard",
      "Cùng 0.945 với bản v3 — deterministic khớp tuyệt đối",
      "Validator nội bộ 4 video (rule cũ): adjEJ 0.9230 · divJ 0.2000 · PROXY 0.9430",
      "122.975 node + 118.786 cạnh · 200 phân bào trên 4 phim test (62/51/9/78)",
    ],
  },
  {
    id: "ver6-v3",
    label: "Ver 6 · bản v3",
    kaggleRef: "vietnguyen130593/biohub-ver6 · submission 56210873",
    lbScore: 0.945,
    submittedAt: "2026-09 · đã chấm",
    status: "COMPLETE",
    runSeconds: 2290,
    submissionRows: 241761,
    proxy: 0.943,
    adjEJ: 0.923,
    divJ: 0.2,
    notes: [
      "Nộp lại cùng pipeline — điểm khớp tuyệt đối với v2 (0.945)",
      "T4×2: 2290 s (v2: 2147 s)",
      "Điểm yếu định lượng: phân bào 100% FN (div tp=0/fp=0) · retention worst 0.453 tại 44b6_0b24845f (65/400 frame fallback) · over-prediction +17%/+35% ở 2 phim",
    ],
  },
  {
    id: "ver7",
    label: "Ver 7 · port Reyhan 0.947",
    kaggleRef: "vietnguyen130593/biohub-ver7 v1 · submission 56217216",
    lbScore: 0.947,
    submittedAt: "2026-09-14 · đã chấm",
    status: "COMPLETE",
    runSeconds: 7020,
    submissionRows: 241356,
    proxy: 0.949,
    adjEJ: 0.9345,
    divJ: 0.0,
    notes: [
      "Port nguyên văn notebook public LB 0.947 của Reyhan Ksatria — chỉ vá 5 dòng env path sang dataset pilkwang public, SHA256 khớp 100%",
      "★ PUBLIC LB = 0.947 — ĐẠT KỲ VỌNG CHÍNH XÁC (+0.002 so với ver-6) · hạng 342/3523, cụm 401 đội cùng điểm",
      "Mục tiêu kế tiếp ≥ 0.948 (cụm 40 đội hạng 66–105) — nghiên cứu ver-8: kaggle/ver-8-planning/VER8-RESEARCH.md",
      "Run T4×2 ~117 phút COMPLETE · submission 241.356 dòng · sha256 d34533806b3153dd…",
      "Phase B official eval (scorer 075fc5f, 8 video held-out): adjEJ micro 0.9345 · div 0/0/12",
      "Paired A/B vs ver-6 trên 4 video chung: ΔadjEJ +0.0000 (CI95 ±0.0001) — KHÔNG regression · guards 5/5",
      "PPSWEEP tự chọn config tight55 (MOTION_RELINK_TIGHT_UM 5.5) nâng proxy held-out 0.9490 → 0.9511",
    ],
  },
  {
    id: "ver7b",
    label: "Ver 7b · Phase C divnet",
    kaggleRef: "vietnguyen130593/biohub-ver7b v1",
    lbScore: null,
    submittedAt: "Chạy xong 14/9 — KHÔNG nộp (thất bại cổng held-out)",
    status: "COMPLETE",
    runSeconds: 6300,
    submissionRows: 241643,
    proxy: 0.938,
    adjEJ: 0.9259,
    divJ: 0.1212,
    notes: [
      "Phase C: divnet division ranker RANK-ONLY W=15 µm + nới gate tau 0.6→1.2 / diverge 2.25→1.0",
      "KẾT QUẢ held-out (rule cũ, 8 video): div_tp 3→4 nhưng div_fp 1→21 → proxy 0.9511→0.9380 (−0.013)",
      "Phán quyết: REGRESSION — không submit (đúng kịch bản cảnh báo megayak); Phase C v2 = giữ gate gốc",
      "Run T4×2 ~105 phút COMPLETE · submission 241.643 dòng (không nộp) · core view = ver-7 (adjEJ 0.9345)",
    ],
  },
  {
    id: "ver8",
    label: "Ver 8 · Phase D re-parenting",
    kaggleRef: "vietnguyen130593/biohub-ver8 v1+v2+v3fast · GPU T4×2",
    lbScore: null,
    submittedAt: "2026-09-15 01:09 · v1 nộp nhưng FAIL runtime (56242181) — v3-fast đã push",
    status: "RUNNING",
    runSeconds: 22380,
    submissionRows: 241330,
    proxy: 0.9591,
    adjEJ: 0.9284,
    divJ: 0.3077,
    notes: [
      "★ v1 (56242181) nộp 01:09 UTC 15/9 → FAIL sau ~12h: rerun notebook trên HIDDEN TEST (lớn hơn public ~2×) vượt runtime limit — errorDescription + totalBytes=0, không có điểm",
      "Nguyên nhân gốc: PPSWEEP 16-19 candidates chiếm 86% runtime kernel (6,87/7,95h) — kernel public 6,2h × hidden ~2× ≈ 12,4h > hạn 12h. ver-7 (117 phút) pass vì đủ nhanh",
      "Bài học hạ tầng: mọi submission đều rerun trên hidden test lớn hơn — ngân sách runtime là ràng buộc CỨNG (public ≤ 2h an toàn)",
      "Giữ nguyên giá trị thuật toán (đo trên held-out, không đổi): re-parent +1 sự kiện thật (div 3/1/9 → 4/1/8) · Δproxy +0,0080 vs ver-7 — đạt ELEVEN",
      "v2 COMPLETE 09:13 (7,9h): chọn ppTight5565 (proxy 0,9594) nhưng KHÔNG nộp — cả v1/v2 đều quá chậm cho hidden test",
      "Bài học v2: rp-ep50 no-op · rp-ep75 làm div_fp 2→4 mà div_tp đứng ở 4 → REPARENT_EDGE_PROB giữ 0,25",
      "★ v3-fast PUSH 13:57 UTC (kernel version 3): sweep rút còn 1 candidate ppTight5565fb (per-prefix + fallback global 5.5) → public ~1,3-1,8h → hidden ~2,5-3,6h — an toàn trong hạn · py_compile + 7/7 unit test PASS",
    ],
  },
];

/** Bối cảnh leaderboard cập nhật 15/9 13:15 UTC (3569 đội) */
export const LB_CONTEXT = {
  ourTeam: "daoviet",
  ourScore: 0.947,
  ourRank: 183,
  /** Cụm 479 đội fork notebook Reyhan Ksatria cùng 0.947 */
  wallScore: 0.947,
  wallTeams: 479,
  /** Cụm kế tiếp cần vượt: 46 đội 0.948 (hạng 79–124) */
  nextClusterScore: 0.948,
  nextClusterTeams: 46,
  topScore: 0.97,
} as const;

export interface HeldoutVideo {
  stem: string;
  embryo: "44b6" | "6bba";
  /** adjEJ official của ver-7 trên video này; null = chưa công bố số từng video */
  adjEJ: number | null;
  /** Giá trị hiển thị — video chưa có số dùng trung bình micro 0.9345 */
  adjEJDisplay: number;
  estimated: boolean;
}

/** 8 video held-out của validator ver-7 (4/phôi) */
export const HELDOUT_STEMS: HeldoutVideo[] = [
  { stem: "44b6_12dfb391", embryo: "44b6", adjEJ: 0.9045, adjEJDisplay: 0.9045, estimated: false },
  { stem: "44b6_267148e4", embryo: "44b6", adjEJ: 0.8506, adjEJDisplay: 0.8506, estimated: false },
  { stem: "44b6_2a2eff9f", embryo: "44b6", adjEJ: null, adjEJDisplay: 0.9345, estimated: true },
  { stem: "44b6_341df25f", embryo: "44b6", adjEJ: null, adjEJDisplay: 0.9345, estimated: true },
  { stem: "6bba_062c8d37", embryo: "6bba", adjEJ: 0.9972, adjEJDisplay: 0.9972, estimated: false },
  { stem: "6bba_07e24132", embryo: "6bba", adjEJ: 0.82, adjEJDisplay: 0.82, estimated: false },
  { stem: "6bba_085bf656", embryo: "6bba", adjEJ: null, adjEJDisplay: 0.9345, estimated: true },
  { stem: "6bba_09961292", embryo: "6bba", adjEJ: null, adjEJDisplay: 0.9345, estimated: true },
];

/** adjEJ micro official của ver-7 trên 8 video held-out */
export const HELDOUT_MICRO_ADJEJ = 0.9345;
