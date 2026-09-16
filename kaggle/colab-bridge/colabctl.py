#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""colabctl — CLI điều khiển Colab Bridge từ phía Z.ai (orchestrator).

Thuần stdlib. URL/TOKEN lấy từ user (cell 0 trong notebook Colab in ra),
đưa vào bằng --url/--token hoặc env COLAB_BRIDGE_URL / COLAB_BRIDGE_TOKEN.

Ví dụ:
  export COLAB_BRIDGE_URL=https://abc-xyz.trycloudflare.com
  export COLAB_BRIDGE_TOKEN=<token user gửi>
  colabctl.py health
  colabctl.py exec "print(6*7)"
  colabctl.py execfile job.py
  colabctl.py put job.py /content/job.py
  colabctl.py get /content/job.log --out job.log

Exit codes: 0 = ok; 1 = lỗi health/usage; 2 = exec thất bại; 3 = put/get thất bại.
"""

import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.request

EXIT_OK = 0
EXIT_HEALTH = 1  # lỗi usage / health
EXIT_EXEC = 2
EXIT_XFER = 3


class _Parser(argparse.ArgumentParser):
    """argparse mặc định exit 2 khi sai tham số — đổi thành 1 (usage failure)."""

    def error(self, message):
        self.print_usage(sys.stderr)
        print("[colabctl] lỗi tham số: %s" % message, file=sys.stderr)
        sys.exit(EXIT_HEALTH)


def _die(msg, code=EXIT_HEALTH):
    print("[colabctl] %s" % msg, file=sys.stderr)
    sys.exit(code)


def _request(url, token, path, payload=None, timeout=900):
    """Gọi bridge; trả về (http_status, dict). HTTPError được đọc + parse JSON."""
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url.rstrip("/") + path, data=data)
    if token:
        req.add_header("X-Bridge-Token", token)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            try:
                return resp.status, json.loads(raw)
            except ValueError:
                return resp.status, {"ok": False, "error": "bad json từ bridge: %r" % raw[:200]}
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8"))
        except Exception:
            return e.code, {"ok": False, "error": "HTTP %s: %s" % (e.code, e.reason)}
    except urllib.error.URLError as e:
        return None, {"ok": False, "error": "không kết nối được bridge (%s)" % (e.reason,)}
    except TimeoutError:
        return None, {"ok": False, "error": "timeout khi gọi bridge"}


def cmd_health(ns):
    status, obj = _request(ns.url, ns.token, "/health", None, timeout=60)
    if status == 200 and obj.get("ok"):
        print(json.dumps(obj, ensure_ascii=False, indent=2))
        return EXIT_OK
    print(json.dumps(obj, ensure_ascii=False), file=sys.stderr)
    return EXIT_HEALTH


def _run_code(ns, code):
    status, obj = _request(ns.url, ns.token, "/exec", {"code": code}, timeout=ns.timeout)
    out = obj.get("stdout") or ""
    err = obj.get("stderr") or ""
    if out:
        sys.stdout.write(out if out.endswith("\n") else out + "\n")
    if err:
        sys.stderr.write(err if err.endswith("\n") else err + "\n")
    if status == 200 and obj.get("ok"):
        return EXIT_OK
    if not err and obj.get("error"):
        sys.stderr.write("[colabctl] bridge error: %s\n" % obj["error"])
    return EXIT_EXEC


def cmd_exec(ns):
    return _run_code(ns, ns.code)


def cmd_execfile(ns):
    try:
        with open(ns.path, "r", encoding="utf-8") as fh:
            code = fh.read()
    except (OSError, UnicodeDecodeError) as exc:
        _die("không đọc được file %r: %s" % (ns.path, exc), EXIT_HEALTH)
    return _run_code(ns, code)


def cmd_put(ns):
    try:
        with open(ns.local, "rb") as fh:
            data = fh.read()
    except OSError as exc:
        _die("không đọc được file local %r: %s" % (ns.local, exc), EXIT_XFER)
    status, obj = _request(
        ns.url,
        ns.token,
        "/put",
        {"path": ns.remote, "content_b64": base64.b64encode(data).decode("ascii")},
        timeout=600,
    )
    if status == 200 and obj.get("ok"):
        print("[put] %s bytes -> %s" % (obj.get("bytes"), obj.get("path")))
        return EXIT_OK
    print("[put] LỖI: %s" % obj.get("error", obj), file=sys.stderr)
    return EXIT_XFER


def cmd_get(ns):
    status, obj = _request(ns.url, ns.token, "/get", {"path": ns.remote}, timeout=600)
    if status == 200 and obj.get("ok"):
        try:
            data = base64.b64decode(obj.get("content_b64") or "")
        except Exception as exc:
            print("[get] LỖI: base64 hỏng: %s" % exc, file=sys.stderr)
            return EXIT_XFER
        if ns.out:
            try:
                with open(ns.out, "wb") as fh:
                    fh.write(data)
            except OSError as exc:
                _die("không ghi được file %r: %s" % (ns.out, exc), EXIT_XFER)
            print("[get] %s bytes -> %s" % (len(data), ns.out))
        else:
            sys.stdout.buffer.write(data)
        return EXIT_OK
    print("[get] LỖI: %s" % obj.get("error", obj), file=sys.stderr)
    return EXIT_XFER


def main():
    p = _Parser(
        prog="colabctl",
        description="Điều khiển Colab Bridge (cell 0 chạy trong notebook Colab của user) từ xa.",
    )
    p.add_argument(
        "--url",
        default=os.environ.get("COLAB_BRIDGE_URL"),
        help="URL bridge, vd https://abc-xyz.trycloudflare.com (env COLAB_BRIDGE_URL)",
    )
    p.add_argument(
        "--token",
        default=os.environ.get("COLAB_BRIDGE_TOKEN"),
        help="token bridge do user gửi (env COLAB_BRIDGE_TOKEN)",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("health", help="kiểm tra bridge đang sống (không cần token)")

    pe = sub.add_parser("exec", help="chạy một đoạn code Python trên runtime Colab")
    pe.add_argument("code", help="đoạn code Python (chú ý dấu nháy của shell)")
    pe.add_argument("--timeout", type=int, default=900, help="timeout giây (mặc định 900)")

    pf = sub.add_parser("execfile", help="lấy nội dung file .py local làm code rồi exec")
    pf.add_argument("path", help="đường dẫn file .py phía local")
    pf.add_argument("--timeout", type=int, default=900, help="timeout giây (mặc định 900)")

    pp = sub.add_parser("put", help="đẩy file local lên runtime Colab")
    pp.add_argument("local", help="file phía local")
    pp.add_argument("remote", help="đường dẫn đích trên runtime Colab")

    pg = sub.add_parser("get", help="lấy file từ runtime Colab về máy")
    pg.add_argument("remote", help="đường dẫn file trên runtime Colab")
    pg.add_argument("--out", default=None, help="file đích local (mặc định: ghi binary ra stdout)")

    ns = p.parse_args()

    if not ns.url:
        _die(
            "thiếu URL bridge — dùng --url hoặc set env COLAB_BRIDGE_URL "
            "(URL https://...trycloudflare.com do user gửi sau khi chạy cell 0)."
        )
    if ns.cmd in ("exec", "execfile", "put", "get") and not ns.token:
        _die(
            "thiếu TOKEN bridge — dùng --token hoặc set env COLAB_BRIDGE_TOKEN "
            "(TOKEN do user gửi sau khi chạy cell 0)."
        )

    if ns.cmd == "health":
        rc = cmd_health(ns)
    elif ns.cmd == "exec":
        rc = cmd_exec(ns)
    elif ns.cmd == "execfile":
        rc = cmd_execfile(ns)
    elif ns.cmd == "put":
        rc = cmd_put(ns)
    else:
        rc = cmd_get(ns)
    sys.exit(rc)


if __name__ == "__main__":
    main()
