# v10-lab Trial Accounts — chạy thử đa tài khoản Kaggle T4×2

**Mục đích:** dùng các tài khoản Kaggle phụ (mỗi tài khoản có quota GPU riêng **30h/tuần**)
để chạy thử nghiệm các version của v10-lab, lấy kết quả so sánh với baseline (ver-8/ver-9).
Tài khoản chính **vietnguyen130593 (Mr. Architect)** giữ nguyên quota + chỉ dùng để **submit**.

## Kiến trúc

```
TÀI KHOẢN PHỤ @B                          TÀI KHOẢN CHÍNH @vietnguyen130593
├─ dataset biohub-v10-lab-runners  ←copy─  (4 runner, đã patch token+slug cho @B)
├─ dataset biohub-v10-lab-filelist ←copy─  (271KB)
├─ dataset biohub-v6-heldout-preds ←copy─  (1.2MB)
├─ [tuỳ chọn] biohub-v10-stems8    ←copy─  (3.4GB — không bắt buộc, kernel pre-stage
│                                          8 stems trực tiếp từ competition mount)
├─ dataset biohub-v10-checkpoints  ←watchdog@B đẩy realtime khi trial chạy
├─ dataset biohub-v10-rawgraphs    ←watchdog@B đẩy (cache replay CPU)
└─ kernel v10-lab-trial (T4×2, internet, private)
     attach: runners@B + COMPETITION (gắn trực tiếp — data 87GB mount local)
```

9 dataset support còn lại của cell 2 là **dataset công khai của người khác** (pilkwang/,
dalloliogm/, …) — tài khoản nào tải cũng được, không cần copy.

## Chuẩn bị cho mỗi tài khoản phụ (làm 1 lần, trên trình duyệt)

1. **Accept competition rules**: `kaggle.com/competitions/biohub-cell-tracking-during-development/rules`
   (không có bước này thì `kernels push` gắn competition sẽ bị từ chối).
2. Tài khoản đã **phone-verified** (điều kiện bật GPU trên Kaggle).
3. **Tạo token API**: kaggle.com → Settings → API → tạo token (chuỗi `KGAT_...`).

## Sử dụng (trong sandbox)

```bash
cd /home/z/my-project/kaggle/ver-10-lab/trial-accounts

# 1) Đăng ký tài khoản (token KGAT dán trực tiếp hoặc từ file)
python3 v10_trial.py register acct2 <username_tai_khoan_2> --token KGAT_xxxxxxxx

# 2) Bootstrap dataset cho tài khoản (runners + filelist + heldout + 2 dataset rỗng)
python3 v10_trial.py init acct2            # thêm --with-stems8 nếu muốn đủ nếp B

# 3) Launch trial (tự động: patch runners → đẩy lên @B → render kernel → push)
python3 v10_trial.py launch acct2
#    Chạy version khác:  python3 v10_trial.py launch acct2 --runners-dir <dir_4_file_runner_mới>

# 4) Theo dõi (kernel + telemetry checkpoint)
python3 v10_trial.py status acct2

# 5) Thu kết quả + so sánh với ver8-baseline
python3 v10_trial.py collect acct2
python3 v10_trial.py compare
```

Kernel trial chạy: pre-stage 8 stems từ competition mount (~1') → cell 2 verify + 9 dataset
(~1') → repair → watchdog (checkpoint realtime) → cell 3 (predict ~25' + grid ~2-3h).
Tổng **~3-4h GPU / trial** → ~7 trial/tuần/tài khoản.

## So sánh version — tiêu chí

- `compare` in: per-stem adjEJ trial-base vs **ver8-base** (cùng 8 stems, cùng trọng số)
  + **weighted adjEJ** (chỉ số quyết định) + bảng grid 9 configs (Δref + proxy).
- Điểm mốc: ver-8 submit public **0.947** — v10 phải thắng weighted adjEJ +0.0025 trở lên
  mới đáng đem submit.
- Sau khi có `raw_graphs` trong dataset trial: grid sweep replay được trên **kernel CPU**
  (không tốn GPU quota) — chỉ predict mới cần GPU.

## Lưu ý quan trọng

- **Kernel trial KHÔNG nộp được** (internet ON, gắn dataset ngoài competition).
  Bản nộp (offline, tự chứa) sẽ build riêng trên tài khoản chính sau khi chọn được version.
- **ToS Kaggle**: chính thức mỗi người 1 tài khoản. Rủi ro: các tài khoản bị liên kết
  (IP/phone/thẻ) có thể bị khoá cùng nhau. Giảm thiểu: trial trên tài khoản phụ,
  **chỉ submit từ tài khoản chính**, kernel/dataset đều private.
- Token KGAT nằm trong `tokens/*.kgat` (chmod 600) — KHÔNG commit, KHÔNG chia sẻ.
- `~/.kaggle/access_token` của sandbox = token tài khoản chính — tool dùng nó để copy
  dataset nguồn; mọi lệnh lên tài khoản phụ đều qua token riêng của tài khoản đó.
