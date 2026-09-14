# Work Record — APP-VER8 (frontend subagent)

- **Task ID**: APP-VER8
- **Agent**: frontend subagent
- **Ngày**: 14/9 (sau push ver-8 GPU 21:20)
- **Ngữ cảnh**: đọc `/home/z/my-project/worklog.md` Task 36 (selector Ver 7/6/Custom + KAGGLE_RESULTS), Task 38 (ver-7 = 0.947, nghiên cứu ver-8), Task 39 (Wave-1 E0/E1/E4 → re-parenting, push biohub-ver8 v1 GPU T4×2).

## Thay đổi (4 file, chỉ dữ liệu + thêm mục version — không đổi cấu trúc)

1. `src/lib/competition-data.ts` — thêm mục `ver8` vào cuối `KAGGLE_RESULTS`:
   - `status: "RUNNING"`, `submittedAt: "2026-09-14 21:20 · ĐANG CHẠY (~2,5–3 h)"`, mọi số liệu `null` (type `KaggleVersionResult` đã cho phép null — không cần chỉnh type).
   - 4 notes: cơ chế re-parenting (6/12 GT, tháo cạnh sai Y→D2, nối M→D2 khi DivNet + geometry + DeepCenter đồng thuận, ≈ +0,0077/ca) · DivNet RANK-ONLY W=15 µm giữ NGUYÊN gate tau 0,6/diverge 2,25 (khác ver-7b) · PPSWEEP 16 candidates (6 rp-* + 7 gốc + 3 adjEJ, gate ±0,0005 adjEJ) · cơ sở E0 trần div_tp=3.
   - Sửa nhỏ trong đề bài: "已达" → "đã đạt" (lẫn chữ Hán). `LB_CONTEXT` comment + `HELDOUT_STEMS`/`HELDOUT_MICRO_ADJEJ` giữ nguyên.

2. `src/components/competition/tracking-demo.tsx`:
   - `type Mode` + `MODE_LABEL` + default state thêm `ver8` ("Ver 8 · đang chạy", đứng đầu, MẶC ĐỊNH).
   - `VERSION_INFO` (type mở rộng `Record<Exclude<Mode,'custom'>,…>`) + 6 chips pipeline ver-8.
   - `analysis` + console log map `ver8 → ensembles.ver7` (core view ver-8 = ver-7 + postprocess re-parenting; KHÔNG đụng `tracking-pipeline.ts`).
   - Selector: ToggleGroupItem "Ver 8 · đang chạy" ở đầu + onValueChange nhận 'ver8'.
   - Console log ver-8 đúng **8 dòng**: ensemble → fusion → link → safe-div → `[ver8·divnet]` rank giữ gate gốc → `[ver8·re-parent]` (Y→D2, M→D2, 6/12 GT) → `[ppsweep]` 16 candidates → `[submit]` ĐANG CHẠY (~2,5–3 h).
   - CardDescription + header comment nhắc ver-8. Bảng so sánh ver6/ver7 giữ nguyên.

3. `src/components/competition/hero.tsx` — badge → amber **"Ver 8 · re-parenting division recovery — ĐANG CHẠY (GPU T4×2)"** (Loader2 animate-spin, amber-400/10); 4 stat thành tích giữ nguyên.

4. `src/components/competition/submission-lab.tsx` — tab "Phiên bản & điểm" thêm **card ver-8** (amber, `md:col-span-2`, đầu registry): kiến trúc (re-parent + DivNet rank giữ gate + 16 candidates + validator ±0.0005), badge "ĐANG CHẠY · GPU T4×2 (~2,5–3 H)", bảng cơ sở Wave-1: E1 system view official **adjEJ 0.9280 · div 2/1/10 · proxy 0.9434** · E0 grid 15 combo không combo tăng div_tp (trần safe-div) · phân rã 12 GT: 6/12 → re-parent, 3/12 thiếu detection.

## Kết quả

- **Lint**: `bun run lint` EXIT 0 sạch · `tsc --noEmit` 0 lỗi src/.
- **Browser (agent-browser, port 3000 có sẵn)**: 200, 0 lỗi console/page; hero badge amber đúng; selector "Ver 8 · đang chạy" đầu danh sách + bấm hoạt động (Ver 6 → 9 dòng, Ver 8 → 8 dòng đúng mẫu); hàng Ver 8 trong bảng KAGGLE_RESULTS ("—" cho null) + notes; card ver-8 hiển thị E1/E0/6-12; mobile 390px scrollWidth=390 không tràn; footer đáy (`footerAtBottom=true`); layout/footer không đổi.
- Screenshots: `kaggle/tools/e2e-ver8-{hero,selector,card,mobile-footer}.png`.
- Worklog: appended `/home/z/my-project/worklog.md` (Task ID: APP-VER8).
