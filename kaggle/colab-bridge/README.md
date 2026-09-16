# COLAB BRIDGE v1

Cơ chế cho **Z.ai (orchestrator) điều khiển từ xa runtime Google Colab T4** của anh —
không cần Google login/credential, không dùng API chính thức của Colab (không có API như vậy),
chỉ dùng một HTTP server nhỏ chạy nền trong runtime + tunnel công khai + token bridge riêng.

## Mục đích

- Z.ai chạy code Python, đẩy/kéo file trực tiếp bên trong runtime Colab (GPU T4) của anh
  qua internet, như một phiên REPL từ xa.
- Anh chỉ việc: **paste 1 cell → chạy → copy 2 dòng (URL + TOKEN) gửi Z.ai**. Xong.
- Bridge chạy nền (daemon thread) — các cell khác của notebook vẫn chạy bình thường.

## Kiến trúc

```
[Z.ai sandbox]                                     [Runtime Colab T4 của anh]
  colabctl.py ──HTTPS──> cloudflared quick tunnel ──> cell 0 (bridge_cell.py)
  (header X-Bridge-Token)  https://<random>.trycloudflare.com
                                                        HTTP server 0.0.0.0:8899
                                                        (daemon thread, thuần stdlib)
                                                        routes: /health /exec /put /get
```

- `bridge_cell.py` ("cell 0"): thuần stdlib, dán vào MỘT cell notebook, chạy 1 lần.
  Tự tải `cloudflared` (nếu thiếu) và dựng **quick tunnel** (không cần tài khoản
  Cloudflare, URL dạng `https://<random-words>.trycloudflare.com`).
- `colabctl.py`: CLI phía Z.ai (cũng thuần stdlib) gọi bridge qua URL + TOKEN.
- `download/colab-bridge-cell-v1.txt`: bản paste-ready, byte-identical với `bridge_cell.py`.

## Phía USER (anh) — 3 bước

1. Mở notebook Colab (runtime T4), thêm 1 cell **ở trên cùng**, dán toàn bộ nội dung
   `download/colab-bridge-cell-v1.txt` vào cell đó.
2. Chạy cell. Lần đầu đợi ~10–60 giây (tải cloudflared + dựng tunnel). Cell in ra khung:

   ```
   ==============================================================
   COLAB BRIDGE v1 — sẵn sàng
   URL   : https://<random-words>.trycloudflare.com
   TOKEN : <chuỗi token ngẫu nhiên>
   GPU   : Tesla T4
   → Copy 2 dòng URL + TOKEN này gửi Z.ai; các cell khác vẫn chạy bình thường (bridge chạy nền).
   ==============================================================
   ```

3. Copy **2 dòng URL + TOKEN** gửi Z.ai (qua chat). **GIỮ TAB COLAB MỞ** — bridge sống
   theo kernel Colab.

## Phía Z.ai (orchestrator)

```bash
# trong sandbox Z.ai:
export COLAB_BRIDGE_URL=https://<random-words>.trycloudflare.com   # user gửi
export COLAB_BRIDGE_TOKEN=<token user gửi>

python3 /home/z/my-project/kaggle/colab-bridge/colabctl.py health
python3 /home/z/my-project/kaggle/colab-bridge/colabctl.py exec "print(6*7)"
python3 /home/z/my-project/kaggle/colab-bridge/colabctl.py exec "import torch; print(torch.cuda.get_device_name(0))"
python3 /home/z/my-project/kaggle/colab-bridge/colabctl.py put job.py /content/job.py
python3 /home/z/my-project/kaggle/colab-bridge/colabctl.py exec "import subprocess; subprocess.run(['python','/content/job.py'])"
python3 /home/z/my-project/kaggle/colab-bridge/colabctl.py get /content/job.log --out job.log
```

Lưu ý: biến trong `/exec` **tồn tại qua các lần gọi** (namespace REPL chung) —
`exec "zz=99"` rồi `exec "print(zz+1)"` in ra `100`.

## Pattern chạy job dài (không giữ HTTP request)

Job dài (train model, xử lý dữ liệu…) KHÔNG nên chạy trực tiếp trong 1 lần `/exec`
(request sẽ treo tới timeout). Chạy nền rồi poll log:

```bash
# 1) đẩy script lên + khởi động nền:
colabctl.py put train.py /content/train.py
colabctl.py exec "import subprocess; subprocess.Popen(['python','/content/train.py'], stdout=open('/content/train.log','w'), stderr=subprocess.STDOUT)"

# 2) poll tiến độ (lặp nhiều lần tuỳ ý):
colabctl.py exec "print(open('/content/train.log').read()[-2000:])"

# 3) kéo kết quả về:
colabctl.py get /content/result.csv --out result.csv
```

## Bảo mật

- **TOKEN = toàn quyền chạy code trên runtime Colab của anh.** Chỉ gửi cho Z.ai,
  **KHÔNG đăng công khai** (không đưa vào repo công khai, forum, screenshot).
- Token sinh ngẫu nhiên mỗi lần chạy cell 0 (trừ khi đặt sẵn env `BR_TOKEN`).
- Mọi route trừ `/health` đều yêu cầu header `X-Bridge-Token` đúng, sai → HTTP 401.
- Tunnel là **quick tunnel** của cloudflared — URL random, không ai đoán được; nhưng
  URL + token đều là "khóa", lộ một trong hai thì đổi bằng cách chạy lại cell 0.

## Hạn chế (quan trọng)

- **Giữ tab Colab mở**: free tier ngắt runtime khi đóng tab hoặc idle (~90 phút không
  tương tác) → bridge chết theo. Mở lại tab + chạy lại cell 0.
- **URL tunnel đổi mỗi lần chạy lại cell 0** (quick tunnel không cố định) → mỗi lần
  restart bridge, anh chạy lại cell 0 rồi **gửi URL mới** cho Z.ai (token cũng mới
  nếu không đặt env `BR_TOKEN`).
- Cell 0 chỉ cần paste MỘT LẦN cho mỗi notebook; chạy lại cell là restart bridge (idempotent).
- Muốn pin token để dễ nhớ/nhớ lại: chạy `%env BR_TOKEN=...` ở cell trước, rồi chạy cell 0.
- `/exec` bị tuần tự hoá (lock) — các lần gọi xếp hàng; stdout/stderr của đoạn code
  được trả kèm response.

## File

| File | Vai trò |
|---|---|
| `kaggle/colab-bridge/bridge_cell.py` | cell 0 — dán vào Colab (bản gốc) |
| `kaggle/colab-bridge/colabctl.py` | CLI phía Z.ai |
| `kaggle/colab-bridge/README.md` | file này |
| `download/colab-bridge-cell-v1.txt` | artifact paste-ready (== bridge_cell.py) |
