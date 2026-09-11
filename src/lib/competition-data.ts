/**
 * Dữ liệu cuộc thi Kaggle: Biohub - Cell Tracking During Development
 * Nguồn: https://www.kaggle.com/competitions/biohub-cell-tracking-during-development/overview
 * Tổng hợp ngày 11/09/2026
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
  totalPrize: 60000,
  stats: {
    entrants: 12477,
    participants: 3716,
    teams: 3386,
    submissions: 62301,
  },
  tags: ["Image", "Video", "Computer Vision", "Object Detection", "Biology", "Custom Metric"],
} as const;

/** Mốc thời gian — tất cả deadline lúc 23:59 UTC */
export const timeline = [
  {
    date: "2026-06-29T23:59:00Z",
    label: "Ngày khai mạc",
    detail: "Cuộc thi chính thức bắt đầu nhận submission.",
    passed: true,
  },
  {
    date: "2026-09-22T23:59:00Z",
    label: "Hạn chót đăng ký tham gia (Entry Deadline)",
    detail: "Bạn phải chấp nhận quy tắc cuộc thi trước ngày này để được thi. Đây cũng là hạn chót cuối cùng để tham gia hoặc sáp nhập đội (Team Merger Deadline).",
    passed: false,
  },
  {
    date: "2026-09-29T23:59:00Z",
    label: "Hạn chót nộp bài cuối cùng (Final Submission)",
    detail: "Deadline cuối cùng để chọn submission cuối cùng cho vòng private leaderboard.",
    passed: false,
  },
] as const;

export const PRIZE_DEADLINE = "2026-09-29T23:59:00Z";
export const ENTRY_DEADLINE = "2026-09-22T23:59:00Z";

export const prizes = [
  { rank: 1, amount: 18000, emoji: "🥇" },
  { rank: 2, amount: 12000, emoji: "🥈" },
  { rank: 3, amount: 8000, emoji: "🥉" },
  { rank: 4, amount: 6000, emoji: "🏅" },
  { rank: 5, amount: 6000, emoji: "🏅" },
  { rank: 6, amount: 5000, emoji: "🏅" },
  { rank: 7, amount: 5000, emoji: "🏅" },
] as const;

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
    deliver: "submission.csv cuối cùng trước 29/09/2026",
  },
] as const;
