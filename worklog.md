# Worklog

---
Task ID: 1
Agent: main
Task: Thu thập thông tin cuộc thi Kaggle "Biohub - Cell Tracking During Development" và khởi tạo dự án giao diện

Work Log:
- Đọc trang overview của cuộc thi bằng agent-browser (Kaggle là SPA nên page_reader không đủ)
- Đọc trang /data (mô tả dataset Zarr v3 + geff) và /leaderboard (top 10 + thống kê)
- Tổng hợp thông tin: task (detect + track tế bào phôi zebrafish 3D+time), metric (adjusted_edge_jaccard + 0.1 × division_jaccard), timeline (start 29/6/2026, entry 22/9/2026, final submission 29/9/2026), prizes ($60,000 tổng, 1st $18k), stats (12,477 entrants, 3,716 participants, 3,386 teams, 62,301 submissions), code requirements (notebook ≤12h, no internet, submission.csv), submission format CSV nodes/edges
- Tạo file worklog.md này
- Sẽ tạo src/lib/competition-data.ts chứa toàn bộ dữ liệu tiếng Việt cho UI

Stage Summary:
- Thông tin cuộc thi đã thu thập đầy đủ (overview + data + leaderboard)
- Sản phẩm: /tmp/kaggle_overview.json, dữ liệu tổng hợp sẽ đưa vào competition-data.ts
- Kế hoạch: giao diện 1 trang tại / gồm hero + countdown + canvas mô phỏng tracking (subagent) + tabs nội dung (tổng quan/dữ liệu/đánh giá/xếp hạng) + hướng dẫn + footer sticky

---
Task ID: 2-a
Agent: full-stack-developer
Task: Xây dựng component mô phỏng tương tác "trình xem kính hiển vi" cho phần cốt lõi của cuộc thi: theo dõi tế bào (node/edge/division) trên dữ liệu 3D+time của phôi zebrafish — file duy nhất: src/components/competition/tracking-demo.tsx

Work Log:
- Đọc worklog.md (Task 1: đã thu thập thông tin cuộc thi) và kiểm tra props của các component shadcn/ui đã cài (card, button, slider, switch, toggle-group, badge, label)
- Thiết kế mô phỏng tất định với mulberry32 (seed cố định): 60 frame (t=0..59), trường nhìn 160×90 µm (16:9, chiếu max-projection của khối ~104 µm), 26 tế bào ban đầu + 3 tế bào đi vào giữa phim + 12 con từ 6 phân bào (frame ~12,19,26,35,42,50) − 6 track kết thúc sớm → 26–32 tế bào sống qua từng frame
- Chuyển động: random walk trơn (damping 0.93) + dòng chảy phôi nhất quán (swirl + drift đổi hướng chậm) + biên mềm giữ trong FOV; z random-walk 3..60 voxel; bán kính 2.7–3.8 µm, mẹ phình trước phân bào, con lớn dần; cường độ dao động; con tách khỏi mẹ theo hướng đối xứng + bias tách 15 frame đầu
- Gắn nhãn thưa (sparse GT ~88%): các "cửa sổ mờ" 2–7 frame ngẫu nhiên từng track; luôn gắn nhãn quanh phân bào để cạnh phân bào tồn tại trong GT
- Vẽ Canvas 2D: nền tối #04100b + illumination field lệch tâm + nhiễu sensor (pattern 128×128, composite lighter, nảy mỗi frame) + vignette; tế bào = radial gradient emerald/teal (hue 148–170) + nhân sáng; depth z ảnh hưởng kích thước & độ mờ; ghost = nét đứt mờ; track = polyline mờ dần (đứt tại frame không nhãn) + cạnh sống; phân bào = xung 2 vòng amber lan tỏa + nhãn "phân bào" + viền amber cho mẹ/con lân cận; HUD = t/mpf (2.5hpf + 1.5 phút/frame), ⟨I⟩, shape (60,64,256,256)·uint16, voxel 0.40625/1.625 µm, thước 50 µm, glyph play/pause
- Nội suy mượt giữa 2 frame (lerp theo tau liên tục), mẹ tan/con trồi ra trong cửa sổ phân bào; fade in/out 4 frame ở rìa đời sống track
- Điều khiển: Play/Pause, Reset (RotateCcw), slider tua t=0..59 (pause khi kéo), ToggleGroup tốc độ 0.5×/1×/2× (BASE_FPS 2.5), 4 switch: Hiện track / Hiện nhãn node / Hiện phân bào / Chế độ GT thưa; chips thống kê Node/Cạnh/Phân bào N/6/⟨I⟩ TB tính đúng ngữ nghĩa cạnh của cuộc thi (mẹ→2 con = 2 cạnh); chú giải 4 mục
- rAF loop + cleanup, bỏ qua khi document.hidden; ResizeObserver + devicePixelRatio (cap 2) cho canvas nét; mọi state động đọc qua ref để không tái tạo vòng lặp
- Kiểm chứng bằng harness tách riêng (bun /tmp/sim-check.ts): 41 track, 6/6 phân bào, 26–32 tế bào sống, 0 frame lỗi, ~88% được gắn nhãn, khoảng cách con sau sinh 1.6→4.5..46 µm
- bunx tsc --noEmit: 0 lỗi cho file này; bun run lint: sạch; dev.log: server OK

Stage Summary:
- Đã tạo: src/components/competition/tracking-demo.tsx (~1130 dòng, 'use client', default export TrackingDemo, không props, TypeScript strict không any, chỉ import từ react / lucide-react / @/components/ui/*)
- Self-contained, xác thực với cuộc thi (voxel scale, uint16, mpf, node/edge/division, GT thưa); màu emerald/teal + amber cho phân bào, không dùng blue/indigo
- Cách tích hợp (cho task 2-b): import TrackingDemo from '@/components/competition/tracking-demo' và nhúng vào trang (không cần props, tự quản state, responsive, aspect-video)

---
Task ID: 3-7 (main)
Agent: main
Task: Xây dựng toàn bộ giao diện, tích hợp, kiểm thử E2E và sửa lỗi

Work Log:
- Sinh ảnh nền hero microscopy bằng z-ai SDK (1440x736, public/images/hero-cells.png)
- Cập nhật globals.css: theme emerald/teal (light + dark), scrollbar tùy chỉnh, texture micro-grid
- Tạo các component: theme-provider, site-header (sticky + mobile nav + theme toggle), hero (countdown 2 deadline + 4 stats + tags + CTA), content-tabs, overview-tab (bài toán 3 bước, thử thách, timeline, giải thưởng, quy định), data-tab (dataset + accordion định dạng + CSV mẫu), evaluation-tab (công thức metric + TP/FP/FN + pipeline 5 bước), leaderboard-tab (top 10 + tìm kiếm + thống kê), getting-started (lộ trình 5 bước + citation), footer sticky
- Lắp ráp page.tsx, cập nhật layout.tsx (lang=vi, metadata tiếng Việt, ThemeProvider next-themes)
- Thêm allowedDevOrigins vào next.config.ts cho preview domain
- SỬA BUG quan trọng trong tracking-demo.tsx (lỗi của subagent): wrapRef được khai báo nhưng KHÔNG gán ref vào div wrapper → ResizeObserver không chạy → sizeRef giữ {0,0} → draw() thoát sớm → canvas đen 300x150. Đã thêm ref={wrapRef}, canvas render 1230x692 với 16k+ pixel sáng
- Kiểm thử E2E bằng agent-browser + VLM phân tích ảnh chụp:
  * Hero + countdown hiển thị đúng (18 ngày)
  * Canvas hiển thị tế bào phát sáng + trails + nhãn node + phân bào amber
  * Pause/Play dừng/tiếp tục frame; slider, speed, 4 switch hoạt động
  * 4 tab đều có nội dung đúng; accordion mở được; tìm kiếm leaderboard lọc đúng (gõ "tang" → 1 hàng)
  * Dark mode đồng bộ, không lỗi tương phản
  * Mobile 390px: không tràn ngang, stats grid 2 cột, điều khiển stack dọc
  * Không lỗi console, lint sạch, tsc src/ sạch

Stage Summary:
- Website hoàn chỉnh tại / gồm: hero + đếm ngược, trình mô phỏng tracking tương tác (60 frame, 6 phân bào, GT thưa), 4 tab nội dung đề bài, lộ trình 5 bước, footer sticky, light/dark mode, responsive
- Đã fix bug canvas đen, verified E2E trên desktop + mobile + dark mode
- Không dùng màu blue/indigo làm primary (emerald/teal/amber)
