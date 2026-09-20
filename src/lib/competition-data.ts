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

export type KaggleRunStatus =
  | "COMPLETE"
  | "PENDING"
  | "RUNNING"
  | "SUBMITTED"
  | "RESEARCH"
  | "BUILD"
  | "FAILED";

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
    id: "ver8",
    label: "Ver 8 · Phase D re-parenting",
    kaggleRef: "vietnguyen130593/biohub-ver8 v1+v2+v3fast · GPU T4×2",
    lbScore: 0.947,
    submittedAt:
      "2026-09-15 19:09 UTC · v3-fast (56261360) CHẤM XONG — LB 0.947 · HẠNG 165/3602",
    status: "COMPLETE",
    runSeconds: 6264,
    submissionRows: 241355,
    proxy: 0.9594,
    adjEJ: 0.9287,
    divJ: 0.3077,
    notes: [
      "★★ 16/9 KẾT QUẢ LB: v3-fast (56261360) = 0.947 → HẠNG 165/3602 — HUY CHƯƠNG BẠC (top 5%, cắt hạng 180, dư 15 chỗ) — THÀNH TỰU LỚN NHẤT: từ đáy cụm 0.947 (ver-7 ~500+) lên vị trí 22/525 đầu cụm",
      "Vì sao cùng hiển thị 0.947 mà hạng nhảy 500+ → 165: LB sắp theo điểm full-precision — v3-fast ≈ 0,9475-0,9479 (re-parent + DivNet rank + tight hardcode cho +~0,0005-0,0009 THẬT trên hidden test) vượt 503/525 đội cùng điểm hiển thị",
      "v1 (56242181) nộp 01:09 UTC 15/9 → FAIL runtime hidden test; v2 (7,9h) cũng chậm; v3-fast (kernel v3, push 13:57) COMPLETE 1,74h — single-candidate ppTight5565fb — duy nhất pass runtime",
      "Giữ nguyên giá trị thuật toán (đo trên held-out): re-parent +1 sự kiện thật (div 3/1/9 → 4/1/8) · Δproxy +0,0080 vs ver-7 — đạt ELEVEN · proxy 0,9594 · adjEJ +0,0025",
      "Bài học hạ tầng: submission rerun trên hidden test lớn hơn public NHIỀU lần (v3-fast 1,74h pass nhưng ver-9 2,4h fail → hidden ≈ 5-7× public) — ngân sách runtime là ràng buộc CỨNG",
      "Lộ trình tiếp: cụm 0.948 (55 đội, hạng 89-143) cần +~0,0003-0,0008 full-precision — RLF + tight tinh chỉnh là ứng viên; vàng cần 0.957+",
    ],
  },
  {
    id: "ver9",
    label: "Ver 9 · HOCT veto + RLF",
    kaggleRef: "vietnguyen130593/biohub-ver9 v1 · GPU T4×2 · 9 input",
    lbScore: null,
    submittedAt:
      "2026-09-15 19:07 · 56261328 FAIL runtime · user gửi lại 16/9 10:29 (56276434) — PENDING",
    status: "FAILED",
    runSeconds: 8663,
    submissionRows: 240871,
    proxy: 0.9534,
    adjEJ: 0.9303,
    divJ: 0.2308,
    notes: [
      "★ 56261328 (nộp 19:07 UTC 15/9) FAIL rerun hidden test: 'Your submission notebook exceeded the allowed runtime' — không có điểm, cùng lỗi với ver-8 v1/v2",
      "★ User đã gửi lại 10:29 UTC 16/9 (56276434) — CÙNG kernel biohub-ver9 v1 (scriptVersionId 350108883 trùng khớp bản fail) → cùng code + cùng hidden test + cùng limit 12h = gần như chắc chắn fail lần nữa; cần kernel v2 sửa runtime mới hy vọng pass",
      "Phân tích nguyên nhân (v3-fast 1,74h public PASS ≠ ver-9 2,4h public FAIL → hidden ≈ 5-7× public, không phải ~2× ước tính cũ): (1) HOCT veto transformer chi phí ~bậc 2 theo node/frame — hidden test là embryo-3 DÀY nhất (124 forks/video, mật độ 12× train) → mỗi video tốn nhiều hơn mức 237s trung bình public; (2) notebook còn ~2h [ver9-gate] validator replay + HOCT 8 stems — overhead thuần trên rerun (chỉ có giá trị validate public); (3) budget max_video_s=900 × nhiều video hidden có thể tích lũy vượt deadline",
      "Kernel public COMPLETE 2,4h: 240.871 dòng (veto 4 cạnh + RLF bỏ 2) · topology 0 lỗi · [ver9-gate] trên 8 stems: adjEJ +0,0017 nhưng div_tp 4→3 → verdict FALLBACK_V3FAST — cổng đã đúng khi cảnh báo rủi ro",
      "Kết luận field: HOCT veto mode 2 KHÔNG đáng giá trên hidden test dày — chi phí runtime vượt ngưỡng trong khi lợi ích validator chỉ +0,0017 (không đủ CI); hướng đi v10: v3-fast + RLF (chi phí ~0) + bỏ HOCT + strip validator replay khỏi notebook production",
      "Bài học cho mọi version sau: notebook submission phải TỐI THIỂU (không validator replay, không gate report, không sweep) — mọi giây public nhân ~5-7× trên hidden",
      "Cập nhật 17/9 sau v10-lab: grid chứng minh mode 1 > mode 2 trên mọi chỉ số (adjEJ +0.0018 vs +0.0017, div giữ nguyên vs mất 1 tp, proxy +0.0018 vs −0.0060) — ver-9 chọn nhầm mode 2",
    ],
  },
  {
    id: "ver10",
    label: "Ver 10 · LAB grid T4×2 (so sánh vs ver-8 v3)",
    kaggleRef: "vietnguyen130593/v10-lab-gpu-t4 v2 · GPU T4×2 · COMPLETE 3h36m (17/9)",
    lbScore: null,
    submittedAt: "2026-09-17 · CHƯA nộp — lab đánh giá 9 cấu hình trên 8 stems validator",
    status: "COMPLETE",
    runSeconds: 12858,
    submissionRows: null,
    proxy: 0.961262,
    adjEJ: 0.930492,
    divJ: 0.307692,
    notes: [
      "★ ĐỘ TIN CẬY: ref tái lập v3-fast CHÍNH XÁC đến 6 chữ số (adjEJ 0.928665 = gate ver-9 0.9287 · proxy 0.959434 = 0.9594 · div 4/1/8) → replay deterministic, mọi delta grid dùng trực tiếp được",
      "★ VETO MODE 1 THẮNG MỌI CHỈ SỐ: adjEJ +0.001828 (cao nhất grid) + proxy +0.001828 (DUY NHẤT dương) + division NGUYÊN VẸN 4/1/8 — khác mode 2 (ver-9) đúng 1 dòng code: giữ nguyên cả 2 cạnh của node cha ≥2 con, chỉ veto cạnh đơn",
      "KẾT QUẢ GRID 9 configs (weighted 8 stems): veto1 0.930492 · veto2/veto2rlf 0.930328 (div_tp 4→3, proxy −0.0060) · rlf_only ±0.000000 (21 cạnh bỏ, KHÔNG đổi gì) · tight 4.5/5.0/6.0/7.0 toàn bộ ÂM (−0.0004…−0.0026) — xác nhận per-prefix 5.5/6.5 của v3-fast tối ưu",
      "★ SO SÁNH v10-veto1 vs ver-8 v3-fast (0.947 LB): nếu +0.0018 transfer sang hidden → 0.9493-0.9497 → vượt cụm 0.948 (55 đội hạng 89-143) → hạng ~89-120, bảo vệ chắc huy chương bạc (hiện 165, cắt 180, chỉ dư 15 chỗ trong cụm 525 đội)",
      "Nguồn gain veto1: 2 stem dày 6bba_09961292 +0.0049 (w=1997, trọng số lớn nhất 33%) + 6bba_07e24132 +0.0045 — thiệt hại nhỏ 44b6_267148e4 −0.0005 + 44b6_2a2eff9f −0.0045, 4 stem còn lại ±0",
      "PHÁN QUYẾT: KHÔNG nộp v10-RLF (≡ v3-fast) / v10-tight (tệ hơn) — ứng viên duy nhất là v3-fast + veto1 + guard thắt (MAX_VIDEO_S 300s · deadline 7.5h · dự đoán theo mật độ node/frame thay vì tổng node · strip toàn bộ validator replay)",
      "Runtime HOCT đo thực: 6.6s/1000 nodes trên T4 (1249s/189k nodes, dưới slope 9s của guard) — nhưng ver-9 đã TLE chứng minh chi phí bậc 2 theo node/frame trên embryo-3 dày → rủi ro TLE TRUNG BÌNH, cần guard mật độ + abort giữa video",
      "Raw graphs cache 27MB đã an toàn trên dataset biohub-v10-rawgraphs → mọi grid sweep sau replay được trên CPU 0 GPU; kernel v10 production đã push 02:57 UTC 19/9 sau quota refresh — xem thẻ ver10prod bên dưới",
    ],
  },
  {
    id: "ver10prod",
    label: "Ver 10 · PRODUCTION kernel — veto mode 1 + guard mật độ",
    kaggleRef: "vietnguyen130593/biohub-ver10 v1 · submission 56348119 · GPU T4×2",
    lbScore: 0.947,
    submittedAt:
      "2026-09-19 04:23 UTC · ref 56348119 · COMPLETE 1h17m — LB 0.947 (veto1 +0.0018 validator không transfer)",
    status: "COMPLETE",
    runSeconds: 4620,
    submissionRows: null,
    proxy: null,
    adjEJ: null,
    divJ: null,
    notes: [
      "★ KẾT QUẢ THẬT 20/9 (đã verify): ref 56348119 = LB 0.947 COMPLETE — submit 19/9 04:23 UTC, chạy 1h17m. KHÔNG phải 0.949 như kỳ vọng: veto1 (+0.0018 validator) KHÔNG transfer lên hidden — dưới ngưỡng hiển thị 0.001 hoặc bị guard bù (2 video 44b6 khổng lồ bị skip vốn gỡ thiệt hại)",
      "★ KERNEL CHẠY ĐÚNG THIẾT KẾ: v3-fast (0.947) + HOCT veto MODE 1 (division-safe — cấu hình duy nhất thắng cả adjEJ +0.0018 LẪN proxy +0.0018 mà không đụng division 4/1/8) + guard mật độ chống TLE — pass hidden trong 1h17m, far dưới hạn 12h, không TLE",
      "GUARD MẬT ĐỘ (bài học TLE ver-9): cap 300s/video (từ 900) · deadline 7.5h (từ 10.5) · ước lượng k·n·d_max + 50s với k=2.2e-5 hiệu chuẩn từ 8 stems đo thật (est ≥ actual trên TẤT CẢ 8 video, thiên về an toàn 1.7-1.9×) · ×3 khi d_max > 550 nodes/frame (vùng ngoài hiệu chuẩn đã giết ver-9) · abort giữa video ở biên chunk (_hvDeadlineAbort — không retry, fail-safe giữ graph gốc)",
      "★ HIỆU CHỈNH GUARD TRÊN DỮ LIỆU THẬT: 6/8 video validator được veto (gồm CẢ HAI stem sinh gain chính 6bba_09961292 est 279s + 6bba_07e24132 est 289s < cap 300) — 2 video 44b6 khổng lồ bị skip (est 576s/498s) đều vô hại: 44b6_12dfb391 delta ±0.0000, 44b6_2a2eff9f delta −0.0045 (skip còn GỠ thiệt hại)",
      "ĐÃ STRIP theo khuyến nghị: RLF (Δ 0.000000 — chết hoàn toàn) · [ver9-gate] validator replay (~45' public ×5-7 hidden) · S2 eval cell → notebook chỉ còn 1 code cell; public ~2h → hidden 1h17m thực tế",
      "BUILD KIỂM CHỨNG: phẫu thuật monolith ver-9 — xóa 207 dòng RLF+gate, chèn block [ver10-hoct] 609 dòng; py_compile PASS; test 65/65 PASS (veto mode 1/2, hiệu chuẩn 8 stems, budget, abort không-retry, strip sạch, thứ tự block)",
      "Bài học transfer: Δvalidator +0.0018 dưới ngưỡng hiển thị LB → coi như noise (đúng gate F6 của v12: ±0.001 = noise) — mọi trục sau phải có receipt ≥2 nguồn + kỳ vọng thực dụng; ver-10 giữ vai trò NỀN banked 0.947 cho v11/v12",
    ],
  },
  {
    id: "ver10linear",
    label: "Ver 10-linear · variant A purge fork — THẤT BẠI 0.911",
    kaggleRef: "vietnguyen130593/biohub-ver10-linear-gpu v1 · ref 56373784",
    lbScore: 0.911,
    submittedAt:
      "2026-09-20 00:00 UTC · ref 56373784 — THẤT BẠI LỚN (Δ −0.036 vs v10)",
    status: "FAILED",
    runSeconds: null,
    submissionRows: null,
    proxy: null,
    adjEJ: null,
    divJ: 0.0,
    notes: [
      "★ LÀM RÕ CHO USER: 0.911 KHÔNG phải ver-10 — là thí nghiệm ver-10-LINEAR (variant A purge fork) trên output v10; ver-10 thật = 0.947 COMPLETE (ref 56348119)",
      "Thí nghiệm post-link Cell 2 alfonso (linearize 188 fork + rescue ≤2) áp lên output v10 — hypothesis: fork là nhiễu làm cong metric cạnh",
      "★ ROOT CAUSE (khớp số học từ LB-replica): Δ −0.036 = divJ_LB 0.333→0 (giết division TP duy nhất trên hidden — 188 fork mình có chứa division TP thật) + edge −0.003; không cách nào xóa 186/118.401 cạnh lại mất −0.036 điểm bằng đếm cạnh thuần",
      "★ PHÁN QUYẾT: hướng linearize/purge fork CHẾT VĨNH VIỄN — fork chỉ được THÊM, không được XÓA (giữ luật D6/F2); replica cũng mù với biến thể A (Δreplica +0.0008) → chỉ LB weigh được",
      "Vận hành: 5 lần submit — 4 fail format/totalBytes (iterate submission CSV) + 1 thành công 0.911; tốn 1 ngày quota cho receipt phủ định",
    ],
  },
  {
    id: "ver11lab",
    label: "Ver 11 · LAB dump + grid mutual_nn — đang chạy",
    kaggleRef: "vietnguyen130593/biohub-v11-lab v2 dump ✅ / v4 grid RUNNING",
    lbScore: null,
    submittedAt: "2026-09-20 · kernel v4 GRID đang chạy GPU (~5h) — chưa nộp",
    status: "RUNNING",
    runSeconds: null,
    submissionRows: null,
    proxy: 0.930492,
    adjEJ: 0.930492,
    divJ: 0.307692,
    notes: [
      "★ KERNEL v2 (19/9 19:31) dump THÀNH CÔNG TRỌN VẸN: mỏ neo D2 tái lập adjEJ 0.930492 EXACT (div 4/1/8) — replay deterministic tiếp tục giữ",
      "Dumps đầy đủ: 193.841 node p_div DivNet + DC raw + 17.699 wide proposals + 183.338 HOCT pairs → grid CPU replay được mọi config sau này",
      "★ FUNNEL B-6 (8 stems, 12 GT division): 9 FN = 7 no_proposal + 2 mutual_nn → chỉ 2/9 FN mutual_nn hồi phục được = trần validator +2 TP",
      "★ KERNEL v4 (20/9) = GRID 6 configs mutual_nn×floor đang chạy GPU (~5h): v11_base · mn_off · mn_pdiv50 · mn_pdiv85 · mn_p85_geo14 · mn_p85_div05",
      "Pool division gate rộng 319 proposals → 46/39 theo p_div floor 0.5/0.85 — chọn config thắng làm production biohub-ver11",
    ],
  },
  {
    id: "ver11research",
    label: "Ver 11 · BUILD — kênh division: mutual_nn + p_div floor",
    kaggleRef: "kaggle/ver-11-planning/V11-RESEARCH.md + v11-lab dump v2 ✅ · production biohub-ver11 submit 20/9 sau grid",
    lbScore: null,
    submittedAt: "2026-09-20 · grid v4 chạy xong → build+submit production HÔM NAY",
    status: "BUILD",
    runSeconds: null,
    submissionRows: null,
    proxy: null,
    adjEJ: null,
    divJ: null,
    notes: [
      "★ FUNNEL RECEIPT (lab v2): 9 FN = 7 no_proposal + 2 mutual_nn → chỉ 2/9 FN mutual_nn hồi phục được — trần validator +2 TP; pool 319 proposals → 46/39 theo p_div floor 0.5/0.85",
      "★ PHÁT HIỆN TỪ NGHIÊN CỨU ĐỐI THỦ (api/research/ 30+ notebooks): sổ cái 6 submission của zhincez (0.952, hạng ~32) chứng minh trục DIVISION là trục duy nhất có offline sign khớp LB (3/3 đúng, trục edge 0/3)",
      "AUDIT GATE CỦA MÌNH (từ megayak đo trên 151 GT division): SAFE_DIV_MAX_UM 9.0 chỉ reach 71% parent (GT tới 10.4µm) · DIVERGE_UM 2.25 nằm ngay MEDIAN phân phối thật (giết ~50%) · SYMMETRY_TAU 0.6 ≈ p60 (giết ~40%) — nhưng mở hết không kèm ranker evidence đo −0.017 (FP nổ)",
      "THUẬT TOÁN V11: giữ DivNet rank W=15 (đã bank trong 0.947) + mutual_nn OFF + MIN_PDIV floor + geo-sister 8→14 + cap frame/global GIỮ NGUYÊN chống FP — chọn config từ grid v4 (6 configs)",
      "REVIEW 17/9 (tự soát đối chiếu code): (1) validator lab ĐÃ dùng rule patched (anchor + lineage-descendants) — số liệu 4/1/8 là rule official mới; (2) DIV_SISTER_MAX_UM 8.0µm geo-filter chặn ~50-70% division thật (GT median 10.4) — trục quan trọng nhất của grid",
      "VẬT LÝ HIỆN TƯỢNG (zhincez EDA paired-control): volume tế bào co từ t−2 TRƯỚC khi chia, peak intensity giữ nguyên — feature size-drop là tín hiệu sớm đúng; DivNet lags (−1,0,+1,+2) đã khớp cửa sổ này",
      "KỲ VỌNG THỰC DỤNG SAU FUNNEL: trần +2 TP validator → +0.001..+0.003 hiển thị (divJ 0.333→0.5 nếu 1 FN thật 05db hồi phục) — khiêm tốn hơn ước tính 0.951-0.955 ban đầu; nếu âm → v10 0.947 vẫn là final",
    ],
  },
  {
    id: "ver12research",
    label: "Ver 12 · ARCH — node-recall + association + division-real (0.948+)",
    kaggleRef: "kaggle/ver-12-planning/V12-RESEARCH.md — nghiên cứu hoàn thành 20/9 (phiên V12-ARCH)",
    lbScore: null,
    submittedAt: "2026-09-20 · lộ trình 20-29/9 · chưa build kernel",
    status: "RESEARCH",
    runSeconds: null,
    submissionRows: null,
    proxy: null,
    adjEJ: null,
    divJ: null,
    notes: [
      "★ KIẾN TRÚC V12 = v10 (0.947 banked, nguyên vẹn veto1 + guard) + 4 TRỤC CÓ RECEIPT: (1) division-real — mutual_nn+geo14+reparent (3 GT div thật 05db đo local được); (2) node-recall — READMIT+GAPFILL (+1.014 node/+1.002 cạnh hidden, receipt thtennant — hiệu ứng đơn lẻ lớn nhất từng thấy); (3) association — SEF_TTA 0.75→1.0 (keep-rate 67.5% vs 71.2%); (4) density-groups — motion-relink 3 nhóm mật độ (haideptry 0.948+)",
      "★ 2 PHÒNG LAB: v12-lab GPU (~4h, grid 8-10 configs + replay validator + hidden raw + đo 3 GT div 05db) + LB-REPLICA OFFLINE (0 GPU — engine scorer2code port metric chính thức, verify 100% tái tạo receipt alfonso 0.9605 EXACT 4 chữ số)",
      "Nguồn: 22 notebook nghiên cứu mới (3 batch, api/research/v12-sweep/ANALYSIS-BATCH-{A,B,C}.md) + giải phẫu 3 GT division thật trên 05db0fb1 (1/3 mồ côi geo-filter + 2/3 sai-gán-cha → trục reparent quan trọng hơn trên hidden thật)",
      "ĐÃ CHẾT (không đụng lại): purge fork/linearize (0.911) · hub/fork augmentation hack (patch aa65e90) · DivNet verify-gate no-op · noisyislands ML ×3",
      "GATES F1-F6 (định trước, không nới): division (Δdiv_tp > 0, 3 GT div 05db không giảm) · node set chỉ TĂNG · stack ≤ 2 trục mới/lượt · runtime ≤ 2.5h · mọi config ghi receipt · LB là trọng tài cuối (±0.001 = noise)",
      "LỘ TRÌNH 20-29/9: 20/9 submit ver-11 → 21/9 v12-lab GPU → 22/9 build+submit v12 → 23-24/9 iterate theo LB → 25/9 CHỌN 2 SUBMISSION CUỐI (v10 0.947 banked + tốt nhất v11/v12) → 26-28/9 dự phòng; mục tiêu 0.948+ (thực dụng 0.948-0.955)",
    ],
  },
];

/** Bối cảnh leaderboard cập nhật 16/9 10:39 UTC — 3602 đội */
export const LB_CONTEXT = {
  ourTeam: "Mr. Architect",
  ourScore: 0.947,
  ourRank: 165,
  /** huy chương bạc: top 5% = 180 hạng (dư 15 chỗ) */
  medal: "SILVER",
  silverCutoffRank: 180,
  /** Cụm 525 đội cùng 0.947 (hạng 144–668) — ta vị trí 22 nhờ full-precision cao */
  wallScore: 0.947,
  wallTeams: 525,
  ourPositionInCluster: 22,
  /** Cụm kế tiếp cần vượt: 55 đội 0.948 (hạng 89–143) */
  nextClusterScore: 0.948,
  nextClusterTeams: 55,
  topScore: 0.97,
  totalTeams: 3602,
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
