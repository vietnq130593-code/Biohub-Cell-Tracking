# ⛽ GPU-WASTE-PREVENTION.md
## LUẬT PHÒNG CHỐNG LÃNG PHÍ GPU & KHÔNG LẶP LẠI LỖI CŨ — BẮT BUỘC

> **⛔ TÀI LIỆU ĐỌC BẮT BUỘC** trước khi: tạo/sửa kernel GPU, push kernel, submit competition,
> viết bất kỳ tài liệu triển khai mới nào (V12-RESEARCH, V*-PLAN, deployment doc, watcher script).
> Mọi agent (main lẫn subagent) phải đọc file này TRƯỚC khi chạm vào GPU/Kaggle.
>
> - Tạo: 2026-09-20, sau sự cố v11-lab đốt ~7h GPU không submit được + variant A 0.911 + 2 lần sandbox reset mất việc không push
> - Vị trí: `/home/z/my-project/GPU-WASTE-PREVENTION.md` (bản chính) + `kaggle/GPU-WASTE-PREVENTION.md` trong repo Biohub-Cell-Tracking (commit theo mỗi thay đổi)
> - Cập nhật cuối: 2026-09-20 (ver11 ref 56403231 vừa submit)

---

## 0. QUY TẮC VÀNG (một dòng, không thương lượng)

**GPU chỉ dành cho kernel PRODUCTION (~2.2h/run). Mọi thí nghiệm = CPU-only trên cache local.
Mọi ý tưởng phải qua CỔNG CPU + receipt TRƯỚC khi được phép chạm GPU.**

---

## 1. SỔ GPU TRUNG THỰC (cập nhật mỗi lần dùng)

| Ngày | Khoản | GPU | Phân loại |
|---|---|---|---|
| 19/9 | v11-lab v1 (3 bug, chết) | ~2.5-3h | 🔴 LÃNG PHÍ (L2) |
| 19/9 | v11-lab v2 (dump OK — tài sản replay vĩnh viễn) | 3.02h | 🟡 Tài sản |
| 20/9 | v11-lab v4 grid (kế hoạch gốc là CPU replay!) | 4.13h | 🔴 CÓ THỂ TRÁNH (L8) |
| 19/9 | ver-10 production 0.947 banked | 1.28h | 🟢 Tài sản |
| 19/9 | v10-linear-gpu variant A (A/B −0.036) | ~2.2h | 🟡 Học phí A/B |
| 20/9 | biohub-ver11 production (submit ref 56403231) | ~1.3h | 🟢 Tài sản |
| **Tổng đã dùng** | | **~15.1h / 30h** | refresh **26/9** |
| **Còn lại** | | **~14.9h** | |

**Kế hoạch khóa ngân sách còn lại:** tối đa 3 lần production nữa (6.6h) + ~8h dự phòng đến 26/9.
Mọi run GPU ngoài kế hoạch này → VI PHẠM §0, phải dừng và báo user.

---

## 2. SỔ KY ÁN — LỖI CŨ ĐÃ MẮC (⛔ KHÔNG ĐƯỢC LẶP LẠI)

| # | Lỗi đã mắc | Thiệt hại | Luật phòng (chỉ mục) |
|---|---|---|---|
| **L1** | Submit/nhầm kernel **LAB** (Internet ON, không competition data source, không ghi submission.csv) → Kaggle chặn cứng *"Did not find provided Notebook Output File"*. Xảy ra với v10-lab-gpu-t4 VÀ cả 4/4 phiên bản v11-lab | ~7h GPU + ngày chậm tiến độ | §3.1 LAB≠PRODUCTION |
| **L2** | Chạy GPU trên kernel có bug chưa smoke-test: rawgraphs cache không load (anchor D2 0.9235 ≠ 0.9305), B2/B3 dump FileNotFoundError (thư mục output chưa mkdir), LAB_MODE test_stems=[] validation fail | ~3h GPU đốt vô ích | §3.2 PRE-GPU |
| **L3** | Submit quá sớm sau COMPLETE (28s) → **totalBytes=0**, fail 2 lần liên tiếp (56368004 v1+v2) | 2 slot submission + ~40' | §3.3 persist ≥20' + pull verify |
| **L4** | submission.csv **float64** ("24.0") thay vì INT → 0 điểm format (variant A ref 56361889) | 1 slot + biến thể chết | §3.4 INT/DAG/census |
| **L5** | Fix xong chỉ để **local, không push** → sandbox reset 2 lần → mất vĩnh viễn (v2int fix, round4 CSV, commit 81685f1, round-5 work) | ~1 ngày công + artifacts | §3.7 commit NGAY mỗi milestone |
| **L6** | **Purge 188 forks** → giết division TP duy nhất trên LB → 0.911 (−0.036 so 0.947) | 1 slot + hướng chết | §3.3 "forks > 0" + KY ÁN: div TP nằm TRONG forks |
| **L7** | Tin receipt validator (+0.0018 veto1) là sẽ transfer LB → KHÔNG transfer (0.947 giữ nguyên) | 1 slot | §3.3 replica + kỳ vọng thực dụng; LB là chân lý duy nhất |
| **L8** | Chạy grid trên GPU trong khi kế hoạch gốc (§5.2) là **CPU replay 0 GPU** | 4.13h GPU | §0 + phải hỏi "cách CPU nào?" TRƯỚC mọi run GPU |
| **L9** | Watcher chạy nền chết → kernel COMPLETE mà không ai submit (ver11 20/9, may mắn cứu kịp). **Root-cause thật (xác minh 20/9 18:22): sandbox này KILL mọi tiến trình nền (kể cả nohup + disown) ngay khi lệnh Bash tool kết thúc** — watcher không thể sống qua các lần gọi tool | rủi ro mất slot/ngày | §3.6 poll ĐỒNG BỘ trong lệnh Bash (sleep trong lệnh), hoặc cron job; sau mỗi batch phải kiểm tra lại |
| **L10** | Đọc code/log bằng `cat` trong Bash → ăn mất chuỗi `[m` → kết luận sai notebook lỗi cú pháp | ~30' lừa mình | §3.6 dùng Read tool cho file chứa subscript |
| **L11** | Pull output (51MB) timeout 180s trong lệnh foreground → tưởng hỏng, thực tế vẫn tải được file chính | ~5' | §3.6 pull nền / timeout ≥600s, kiểm file thay vì tin exit code |
| **L12** | Bỏ qua bước verify census đúng cột (đếm ID trùng liên dataset → 28,540 "forks" ảo) | rủi ro kết luận sai | §3.4 census LUÔN partition theo dataset |

**Nguyên tắc đọc sổ KY ÁN:** mỗi kế hoạch mới phải tự đối chiếu TỪNG dòng L1-L12 và ghi
vào section [GPU WASTE CHECK] (§4) những lỗi nó có nguy cơ mắc.

---

## 3. CHECKLIST CỔNG BẮT BUỘC (không pass = không đi tiếp)

### 3.1 LAB ≠ PRODUCTION (chống L1, L8)
- Kernel **LAB**: Internet ON, runners riêng, output = artifacts/dumps. **KHÔNG BAO GIỜ submit.**
- Kernel **PRODUCTION**: Internet **OFF** + gắn competition data source + **ghi submission.csv**. Duy nhất loại này được submit.
- Thí nghiệm mặc định = **CPU-only** trên cache local đã có: rawgraphs (27MB) + dumps (41MB) + GT 4 phim test (`/home/z/v11-recovery/test-gt`) + LB-replica engine + v10 output banked.
- Trước mỗi run GPU phải trả lời bằng văn bản: *"Cách CPU nào đã bị loại trừ và tại sao?"*

### 3.2 PRE-GPU — trước khi chạy kernel GPU (chống L2)
- [ ] Smoke test ≤5' CPU local: 6/6 pass, 0 exception
- [ ] **Cache anchor**: sha256 + anchor score khớp banked ±0.0001 (D2 = 0.930492) — lệch → DỪNG, điều tra cache load
- [ ] Mọi đường dẫn output tồn tại trước khi dump (mkdir -p + pre-flight check trong kernel)
- [ ] Ước lượng runtime + timeout margin (T4×2: 9-36'/phim, 4 phim ≈ 1.3-2.2h)
- [ ] Guard `must_count` / `_EXPECTED_NUMERIC` còn nguyên trong kernel (chống sai số env)

### 3.3 PRE-SUBMIT — trước khi create_code_submission (chống L3, L4, L6, L7)
- [ ] Kernel COMPLETE ≥ **20 phút** (output persist)
- [ ] Pull output thành công HOÀN CHỈNH: `wc -l` khớp id dòng cuối (chống truncate)
- [ ] **INT**: 0 trường số chứa "." ; không zero-value/"-1" sai chỗ
- [ ] **DAG**: node ≤2 out-edges; **forks > 0** và ≤ ~300 (forks=0 = hướng purge ĐÃ CHẾT — L6)
- [ ] **Census theo dataset** (L12!) so với base: Δnodes/Δedges/Δforks phải giải thích được
- [ ] run_stats.csv: `experiment_tag` = đúng config định chạy; `ground_truth_accessed=false`
- [ ] **Replica 0-GPU** (nếu áp dụng): ghi div tp/fp/fn + kỳ vọng vào submission message
- [ ] Quota hôm nay + ngân sách GPU còn lại (§1)
- [ ] Base banked (v10 = 0.947) vẫn selectable — submission mới không được làm mất nó

### 3.4 Kiểm format + census (copy-paste, ~5s, 0 GPU)
```bash
python3 - <<'EOF'
import csv
per={}
for row in csv.reader(open('submission.csv')):
    if row[0]=='id': continue
    c=per.setdefault(row[1],{'n':0,'e':0,'out':{}})
    if row[2]=='node': c['n']+=1
    else:
        c['e']+=1; c['out'][row[8]]=c['out'].get(row[8],0)+1
    assert '.' not in ''.join(row[3:]), f'FLOAT LEAK: {row}'
N=sum(c['n'] for c in per.values()); E=sum(c['e'] for c in per.values())
F=sum(1 for c in per.values() for v in c['out'].values() if v>=2)
print(f'NODES={N} EDGES={E} FORKS={F}  (per-dataset: '+', '.join(f'{k}:{c["n"]}/{c["e"]}' for k,c in per.items())+')')
assert F>0, 'FORKS=0 — HƯỚNG PURGE ĐÃ CHẾT (L6)'
EOF
```

### 3.5 POST-SUBMIT
- [ ] Ghi ref + message + receipt đầy đủ vào worklog NGAY (đừng chờ)
- [ ] Poll điểm sau ≥30' (scoring 20-40'); dùng watcher nohup, không poll tay trong session
- [ ] Nếu điểm < base → **POSTMORTEM bắt buộc** (root cause → thêm dòng mới vào §2 sổ KY ÁN) TRƯỚC khi submit tiếp theo
- [ ] Cập nhật sổ GPU §1 (số phút thực tế vs ước lượng, waste hay không)

### 3.6 Tooling (chống L9, L10, L11)
- kaggle CLI: `/home/z/.venv/bin/kaggle`, token từ `~/.kaggle/access_token` (export KAGGLE_ACCESS_TOKEN)
- Pull output ~51MB: chạy nền hoặc timeout ≥600s; file chính (submission.csv) tải xong là dùng được — kiểm nội dung thay vì tin exit code
- Đọc code/log chứa subscript (`[...]`) → **Read tool**, không dùng cat
- **Watcher/polling**: sandbox này KILL tiến trình nền khi lệnh Bash tool kết thúc (nohup cũng chết — L9) → poll ĐỒNG BỘ trong 1 lệnh Bash (`sleep N; query`), hoặc dùng cron job hệ thống; script watcher vẫn giữ làm one-shot; sau mỗi batch `ps aux | grep watch` để xác nhận
- Lệnh quan trọng (push/submit) không được nằm "chờ cuối session" (L5, L9)

### 3.7 PERSISTENCE — không mất việc nữa (chống L5)
- Sau MỖI milestone (fix / build / receipt / artifact): `git add -A && git commit -m "..."` trong repo **NGAY LẬP TỨC** (repo: /home/z/Biohub-Cell-Tracking)
- Standing rule "không push không có lệnh" vẫn giữ cho CODE — nhưng sau mỗi commit phải **xin phép push trong báo cáo ngay**, không để commit nằm local quá 1 session
- Artifacts quan trọng nhân đôi: `/home/z/v11-recovery/` (hoặc tương đương) + trong repo
- Secrets/tokens lưu lại trong `~/.kaggle/access_token` + `~/.secrets/` ngay khi nhận (sandbox reset bất kỳ lúc nào)

---

## 4. TEMPLATE BẮT BUỘC — section [GPU WASTE CHECK] trong MỌI tài liệu triển khai mới

> Mọi tài liệu triển khai mới (V12-RESEARCH.md, V*-PLAN.md, deployment doc, kernel plan…)
> **PHẢI chèn nguyên văn block sau ngay đầu file**, điền đầy đủ trước khi review/phan duyệt:

```markdown
## ⛽ GPU WASTE CHECK — bắt buộc (theo GPU-WASTE-PREVENTION.md)
- GPU ước tính: ___h (___ lần production × 2.2h) + ___h thí nghiệm (mặc định 0 — CPU-only)
- Cách CPU cho thí nghiệm này: ___ (cache nào / replica / validator) — lý do nếu cần GPU: ___
- PRE-GPU đã pass: [ ] smoke 6/6  [ ] cache anchor ±0.0001  [ ] must_count  [ ] timeout margin
- PRE-SUBMIT đã pass: [ ] persist ≥20'  [ ] INT/DAG/census-theo-dataset  [ ] run_stats tag  [ ] quota  [ ] base banked còn selectable
- Chính sách fork: KHÔNG purge (L6); census kỳ vọng ~___
- Rollback nếu hỏng: ___ (base banked 0.947 luôn giữ selectable)
- Lỗi cũ có nguy cơ mắc (đối chiếu L1-L12): L___, L___ — phòng bằng: ___
- Watcher: script ___ + nohup + PID ___ + log ___ (check ps aux đầu session)
- Cam kết sau hoàn thành: commit ngay (L5) + cập nhật sổ GPU §1 + postmortem nếu dưới base
```

---

## 5. QUY ƯỚC WORKLOG

1. Mọi entry worklog liên quan GPU phải khai: **GPU-phút thực tế vs ước tính, waste hay không, lý do**.
2. Đầu mỗi session mới (trước khi làm việc Kaggle): kiểm `ps aux | grep watch` + status kernel đang chạy + quota — watcher chết thì khởi động lại TRƯỚC (bài học L9 ngày 20/9).
3. Entry postmortem sau mỗi điểm LB dưới kỳ vọng là BẮT BUỘC, có số dòng mới thêm vào sổ KY ÁN §2.

---

## 6. CAM KẾT HIỆN TẠI (từ V11LAB-NOSUBMIT-DIAG-R2, 20/9 — vẫn hiệu lực)

1. **KHÔNG kernel lab GPU nữa** — mọi thí nghiệm CPU-only bằng cache local
2. **v12-lab tái thiết kế CPU-only** ngay từ đầu
3. **GPU chỉ dành cho production submit** 2.2h/lần — ngân sách ≤6.6h GPU còn lại cho tối đa 3 lần
4. **Mọi ý tưởng phải qua cổng CPU + receipt trước khi chạm GPU** — không ngoại lệ

---

*Tài liệu này sống lâu hơn mọi session. Khi sandbox reset: file này (bản my-project) + bản trong repo GitHub là nguồn sự thật duy nhất về lỗi cũ. Đọc trước, hành động sau.*
