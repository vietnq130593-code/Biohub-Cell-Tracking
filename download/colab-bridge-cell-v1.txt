# -*- coding: utf-8 -*-
# ==============================================================================
# COLAB BRIDGE v1 — "CELL 0" — dán toàn bộ file này vào MỘT cell notebook
# Google Colab (Python 3.10 / 3.11) và chạy MỘT LẦN.
# ------------------------------------------------------------------------------
# MỤC ĐÍCH:
#   - Mở một kênh điều khiển từ xa cho Z.ai (orchestrator AI) vào runtime Colab
#     của anh — KHÔNG dùng Google login/credential, chỉ dùng TOKEN bridge riêng
#     được sinh ngay trong cell này (hoặc đặt trước qua env BR_TOKEN).
#   - Sau khi chạy, cell sẽ IN RA URL + TOKEN — copy 2 dòng đó gửi cho Z.ai.
#   - GIỮ TAB COLAB MỞ (free tier ngắt runtime khi đóng tab hoặc idle).
#
# CƠ CHẾ:
#   1. HTTP server thuần stdlib chạy nền (daemon thread) trong runtime Colab,
#      listen 0.0.0.0:8899 (đổi qua env BR_PORT).
#   2. cloudflared QUICK TUNNEL (không cần tài khoản Cloudflare) expose server
#      ra công khai: https://<random-words>.trycloudflare.com
#   3. Z.ai gọi URL đó kèm header X-Bridge-Token bằng CLI colabctl.py.
#
# Cell thuần stdlib, KHÔNG cần pip install; idempotent (chạy lại cell để
# restart bridge / lấy URL tunnel mới là an toàn). Các cell khác của notebook
# vẫn chạy bình thường — bridge chỉ chạy nền.
# ==============================================================================

import os
import sys
import re
import io
import json
import time
import base64
import secrets
import threading
import traceback
import subprocess
import contextlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# --------------------------------------------------------------- hằng số ----
BR_PORT = int(os.environ.get("BR_PORT", "8899"))
BR_TOKEN = os.environ.get("BR_TOKEN") or secrets.token_urlsafe(20)
BR_CF = "/usr/local/bin/cloudflared"
BR_LOG = "/tmp/colab-bridge-cloudflared.log"

# ------------------------- idempotent: dừng bridge cũ nếu chạy lại cell -----
_prev = globals().get("__BR_STATE__")
if isinstance(_prev, dict):
    _p_srv, _p_cf = _prev.get("srv"), _prev.get("cf")
    if _p_srv is not None:
        try:
            _p_srv.shutdown()
        except Exception:
            pass
        try:
            _p_srv.server_close()
        except Exception:
            pass
    if _p_cf is not None:
        try:
            _p_cf.terminate()
        except Exception:
            pass
    time.sleep(0.3)  # chờ OS nhả cổng
    print("[bridge] đã dừng bridge cũ (rerun trong cùng kernel)")

# ------------------------------------------------------- tên GPU (có cache) --
_BR_GPU_CACHE = {"name": None, "checked": False}


def _br_gpu_name():
    """Tên GPU nếu có; cache module-level để /health không import torch lại."""
    if not _BR_GPU_CACHE["checked"]:
        try:
            import torch  # import có điều kiện là chủ đích (Colab có sẵn torch)

            if torch.cuda.is_available():
                _BR_GPU_CACHE["name"] = torch.cuda.get_device_name(0)
        except Exception:
            _BR_GPU_CACHE["name"] = None
        _BR_GPU_CACHE["checked"] = True
    return _BR_GPU_CACHE["name"]


# ------------------------------------------- namespace REPL + lock /exec ----
_BR_NS = {"__name__": "__colab_bridge__"}  # biến tồn tại qua các lần /exec (như REPL)
_BR_LOCK = threading.Lock()  # tuần tự hoá các lần /exec


class _BRHandler(BaseHTTPRequestHandler):
    """Handler HTTP của bridge — mọi response đều là JSON."""

    # ------------------------------------------------------------- plumbing
    def log_message(self, fmt, *args):  # tắt access-log ồn ào
        pass

    def _send_json(self, obj, status=200):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self):
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n) if n > 0 else b""
        return json.loads(raw.decode("utf-8")) if raw else {}

    def _authed(self):
        return self.headers.get("X-Bridge-Token") == BR_TOKEN

    # --------------------------------------------------------------- routes
    def do_GET(self):
        if self.path.split("?", 1)[0] == "/health":
            self._send_json(
                {
                    "ok": True,
                    "gpu": _br_gpu_name(),
                    "cwd": os.getcwd(),
                    "python": sys.version.split()[0],
                }
            )
        else:
            self._send_json({"ok": False, "error": "no route"}, status=404)

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        if path not in ("/exec", "/put", "/get"):
            self._send_json({"ok": False, "error": "no route"}, status=404)
            return
        if not self._authed():
            self._send_json({"ok": False, "error": "bad token"}, status=401)
            return
        try:
            req = self._read_json()
        except Exception as exc:
            self._send_json({"ok": False, "error": "bad json body: %s" % exc}, status=400)
            return
        try:
            if path == "/exec":
                self._h_exec(req)
            elif path == "/put":
                self._h_put(req)
            else:
                self._h_get(req)
        except Exception as exc:  # phòng bug trong handler
            self._send_json(
                {"ok": False, "error": "handler error: %s: %s" % (type(exc).__name__, exc)},
                status=500,
            )

    # ----------------------------------------------------------------- /exec
    def _h_exec(self, req):
        code = req.get("code")
        if not isinstance(code, str):
            self._send_json(
                {"ok": False, "stdout": "", "stderr": "bad request: 'code' phải là string"},
                status=400,
            )
            return
        buf = io.StringIO()
        ok = True
        tb = ""
        with _BR_LOCK, contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                exec(compile(code, "<bridge>", "exec"), _BR_NS)
            except BaseException:
                ok = False
                tb = traceback.format_exc()
            out = buf.getvalue()  # phải lấy TRƯỚC khi dựng response
        self._send_json({"ok": ok, "stdout": out, "stderr": tb})

    # ------------------------------------------------------------------ /put
    def _h_put(self, req):
        rpath = req.get("path")
        b64 = req.get("content_b64")
        if not isinstance(rpath, str) or not isinstance(b64, str):
            self._send_json(
                {"ok": False, "error": "bad request: cần 'path' và 'content_b64'"},
                status=400,
            )
            return
        try:
            data = base64.b64decode(b64)
            parent = os.path.dirname(rpath)
            if parent:
                os.makedirs(parent, exist_ok=True)
            with open(rpath, "wb") as fh:
                fh.write(data)
        except Exception as exc:
            self._send_json({"ok": False, "error": "%s: %s" % (type(exc).__name__, exc)}, status=500)
            return
        self._send_json({"ok": True, "bytes": len(data), "path": rpath})

    # ------------------------------------------------------------------ /get
    def _h_get(self, req):
        rpath = req.get("path")
        if not isinstance(rpath, str):
            self._send_json({"ok": False, "error": "bad request: cần 'path'"}, status=400)
            return
        try:
            with open(rpath, "rb") as fh:
                data = fh.read()
        except Exception as exc:
            self._send_json({"ok": False, "error": "%s: %s" % (type(exc).__name__, exc)}, status=500)
            return
        self._send_json(
            {
                "ok": True,
                "content_b64": base64.b64encode(data).decode("ascii"),
                "bytes": len(data),
            }
        )


# ------------------------------------------------------ dựng + mở server ----
try:
    srv = ThreadingHTTPServer(("0.0.0.0", BR_PORT), _BRHandler)
except OSError as exc:
    print(
        "[bridge] LỖI: không bind được cổng %d (%s). Thử chạy lại cell này, "
        "hoặc đặt env BR_PORT sang cổng khác." % (BR_PORT, exc)
    )
    raise
srv.daemon_threads = True

if "--stay" not in sys.argv:
    # Colab: cell TRẢ VỀ NGAY, server sống trên daemon thread
    # (kernel còn sống thì bridge còn sống).
    threading.Thread(target=srv.serve_forever, name="colab-bridge-http", daemon=True).start()

# ---------------------------------------------------------------- tunnel ----
cf = None
public_url = None
if "--no-tunnel" not in sys.argv:
    try:
        if not os.path.exists(BR_CF):
            print("[bridge] tải cloudflared -> %s ..." % BR_CF)
            subprocess.run(
                [
                    "wget",
                    "-q",
                    "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64",
                    "-O",
                    BR_CF,
                ],
                check=True,
            )
            os.chmod(BR_CF, 0o755)
        cf_log = open(BR_LOG, "w")
        cf = subprocess.Popen(
            [BR_CF, "tunnel", "--url", "http://localhost:%d" % BR_PORT, "--no-autoupdate"],
            stdout=cf_log,
            stderr=subprocess.STDOUT,
        )
        _pat = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")
        _deadline = time.time() + 90
        while time.time() < _deadline:
            if cf.poll() is not None:
                break
            try:
                with open(BR_LOG, "r", errors="ignore") as lf:
                    _m = _pat.search(lf.read())
                if _m:
                    public_url = _m.group(0)
                    break
            except OSError:
                pass
            time.sleep(1.0)
    except Exception as exc:
        print("[bridge] tunnel lỗi: %r — bridge vẫn chạy local ở cổng %d" % (exc, BR_PORT))

# ------------------------------------------------------------------ state ---
globals()["__BR_STATE__"] = {
    "srv": srv,
    "cf": cf,
    "url": public_url,
    "token": BR_TOKEN,
    "port": BR_PORT,
}

# ----------------------------------------------------------------- banner ---
_gpu = _br_gpu_name()
_bar = "=" * 62
print(_bar)
print("COLAB BRIDGE v1 — sẵn sàng")
if public_url:
    _url_line = public_url
elif "--no-tunnel" in sys.argv:
    _url_line = "http://localhost:%d  (chế độ --no-tunnel, chỉ dùng trong cùng máy)" % BR_PORT
else:
    _url_line = "KHÔNG LẤY ĐƯỢC — xem %s" % BR_LOG
print("URL   : %s" % _url_line)
print("TOKEN : %s" % BR_TOKEN)
print("GPU   : %s" % (_gpu if _gpu else "(không phát hiện GPU)"))
print("→ Copy 2 dòng URL + TOKEN này gửi Z.ai; các cell khác vẫn chạy bình thường (bridge chạy nền).")
print(_bar)

# ---------------------------------------------------------- chế độ --stay ---
if "--stay" in sys.argv:
    print("[bridge] --stay: server chạy foreground ở cổng %d, Ctrl+C để dừng." % BR_PORT)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n[bridge] dừng theo Ctrl+C.")
    finally:
        try:
            srv.server_close()
        except Exception:
            pass
        if cf is not None:
            try:
                cf.terminate()
            except Exception:
                pass
