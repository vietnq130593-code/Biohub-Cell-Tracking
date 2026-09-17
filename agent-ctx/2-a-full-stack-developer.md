# Work Record — Task 2-a (full-stack-developer)

## Task
Tạo component tương tác mô phỏng nhiệm vụ cốt lõi của cuộc thi Kaggle "Biohub - Cell Tracking During Development": trình xem dữ liệu kính hiển vi 3D+time của phôi zebrafish với node (tế bào) + edge (liên kết frame) + division (phân bào), dạng "mini exam interface".

File tạo: `src/components/competition/tracking-demo.tsx` (file duy nhất được phép tạo/sửa).

## Work Log
1. Đọc `worklog.md` (Task 1 — thu thập dữ liệu cuộc thi) để lấy bối cảnh.
2. Kiểm tra props các component shadcn/ui đã cài: `card.tsx`, `button.tsx`, `slider.tsx` (value: number[]), `switch.tsx`, `toggle-group.tsx` (type="single"), `badge.tsx`, `label.tsx`, `toggle.tsx` — tất cả theo chuẩn shadcn mới (New York).
3. Thiết kế & viết component:
   - **Mô phỏng tất định** (mulberry32, seed `0x51f00d2a`): 60 frame, trường nhìn 160×90 µm (16:9), 26 tế bào đầu + 3 entry + 12 daughter từ 6 phân bào (frame ~12/19/26/35/42/50) − 6 exit sớm → **26–32 tế bào sống/frame**.
   - Chuyển động: random walk + damping + swirl/drift phôi nhất quán + biên mềm; z (0..63 voxel) random walk; bán kính/cường độ biến đổi; mẹ phình trước phân bào; con tách theo hướng đối xứng (bias 15 frame đầu).
   - **Sparse GT ~88%**: cửa sổ mờ 2–7 frame ngẫu nhiên/track; quanh phân bào luôn có nhãn.
   - **Render Canvas 2D**: nền tối + nhiễu sensor + illumination + vignette; tế bào = radial gradient emerald/teal (hue 148–170) + nhân sáng; z → size/opacity (parallax); ghost = dashed; trail = polyline mờ dần, đứt khi không nhãn; phân bào = 2 vòng amber lan tỏa + nhãn "phân bào" + viền amber; HUD: t, mpf (150 + 1.5·t), ⟨I⟩, (T,Z,Y,X)=(60,64,256,256)·uint16, voxel 0.40625/1.625 µm, thước 50 µm, glyph play/pause.
   - **Nội suy mượt** giữa frame (tau liên tục): lerp vị trí; phân bào diễn ra trong cửa sổ d→d+1 (mẹ tan, con trồi từ vị trí mẹ); fade in/out 4 frame ở rìa đời sống.
   - **Điều khiển**: Play/Pause, Reset, slider t=0..59 (pause khi kéo), tốc độ 0.5×/1×/2× (BASE_FPS=2.5), 4 switch (Hiện track / Hiện nhãn node / Hiện phân bào / Chế độ GT thưa), chips: Node, Cạnh, Phân bào N/6, ⟨I⟩ TB — tính đúng ngữ nghĩa cạnh (mẹ→2 con = 2 cạnh). Legend 4 mục.
   - **Hiệu năng**: rAF + cleanup, skip khi `document.hidden`, ResizeObserver + DPR (cap 2), state động đọc qua ref (vòng lặp không tái tạo), texture nhiễu cache.
4. Kiểm chứng logic bằng harness (`/tmp/sim-check.ts`, ngoài project): 41 track, 6/6 phân bào, alive 26–32, 0 frame NaN/out-of-bounds, labeled 87.9%, stats hợp lý mọi frame.
5. `bunx tsc --noEmit` → 0 lỗi cho file này; `bun run lint` → sạch; `dev.log` → server chạy bình thường.
6. Append bản ghi vào `worklog.md`.

## Kết quả chính
- `src/components/competition/tracking-demo.tsx` — 'use client', default export `TrackingDemo`, không props, strict TS không `any`, chỉ import react/lucide-react/@/components/ui/*, không ảnh ngoài, không WebGL.

## Ghi chú tích hợp (cho task 2-b)
```tsx
import TrackingDemo from '@/components/competition/tracking-demo'
...
<TrackingDemo />
```
- Component tự chứa, tự quản state, responsive (aspect-video, mobile-first), không cần prop.
- Canvas luôn nền tối (dùng được ở cả light/dark theme); phần vỏ Card theo theme.
- Đặt trong section nào có width đủ lớn (max-w-4xl trở lên) để HUD/legend thoáng.
