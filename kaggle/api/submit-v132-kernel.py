#!/usr/bin/env python3
"""submit-v132-kernel.py — Nộp v13.2 qua create_code_submission (route ĐÃ CHỨNG MINH).

Bối cảnh (V132-ACKFIX-RESUBMIT 23/9): submit-v132.py gọi `kaggle competitions submit
-f submission.csv` (upload CSV trực tiếp) → upload xong 100% nhưng Kaggle API
CreateSubmission trả **400 Bad Request**. Đây KHÔNG phải lỗi mới: submit-v12.py
docstring đã ghi từ 15/9 — "Cuộc thi chỉ nhận code submission từ kernel version
(CLI file submit bị 400 — kiểm chứng 15/9)". Mọi submission THÀNH CÔNG trước đây đều
qua kagglesdk CompetitionApiClient.create_code_submission:
  v12.1 ref 56442903 (22/9 "kagglesdk create_code_submission biohub-ver12 v2 → HTTP 200")
  v13.1 ref 56473159 (19:59 UTC 22/9, cùng route qua submit-v131.py — mất theo sandbox
  reset, pattern lưu trong submit-v12.py/submit-v13.py: KaggleClient +
  ApiCreateCodeSubmissionRequest).

Script này CHỈ là TRANSPORT LAYER — không chạy lại cổng nào: machinery-audit đã PASS
trong luồng submit-v132.py lúc 11:57 UTC 23/9 (PASS=20 ACKED=2 WARN=0 FAIL=0 sau
ack-fix commit b5f131e — worklog V132-ACKFIX-RESUBMIT). Kết quả cổng ĐỨNG NGUYÊN.

Chuỗi integrity của kernel version được nộp (version 1):
  - state.json: ref vietnguyen130593/biohub-ver132 version 1 (push 10:08:28 UTC 23/9)
  - kernel status: KernelWorkerStatus.COMPLETE (ktool.py status --ver 132)
  - output đã pull + md5-verify 2 nơi: submission.csv md5 a8f71aa13b3006aaf77529d3eababa60
    (240.194 rows) + run_stats.csv receipts audited PASS (safe_div Σ85 · reparent Σ71 ·
    HOCT 141 = forks 141).

  python3 submit-v132-kernel.py [--version 1] [--message "..."] [--dry-run]

Chính sách lỗi (L13b — không override):
  - 4xx → in NGUYÊN VĂN response body → DỪNG (không retry).
  - 5xx/network transient → đúng 1 lần retry, rồi dừng.
  - lỗi nhắc "kernel version phải re-run / phải latest" → DỪNG ngay, KHÔNG push version mới.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STATE = ROOT / "state.json"
OUTPUT_DIR = ROOT / "output" / "ver132"
COMPETITION = "biohub-cell-tracking-during-development"
KERNEL_OWNER = "vietnguyen130593"
KERNEL_SLUG = "biohub-ver132"

EXPECTED_MD5 = "a8f71aa13b3006aaf77529d3eababa60"
EXPECTED_ROWS = 240194

DEFAULT_MESSAGE = (
    "ver-13.2 = v13.1 SR0GC3 + RESTORE division v11-exact (L13c fix: "
    "OUTPUT_SAFE_DIVISIONS=1 + REPARENT_ENABLE=1 + EP=0.25), keep GC3 gap 3.0 + leaf 0.3. "
    "Receipts: safe_div 27/10/7/41=85 (v11 82), reparent 12/15/3/41=71 (v11 77), "
    "HOCT 141=forks 141 (law zone 144-188), leaf_prune 81. Replica adjEJ 0.9012 "
    "(+0.0002 vs v11 0.9010, divJ 0.0000 flat), census 122372n/117822e/141f. "
    "Gate: machinery-audit PASS (20 PASS/2 ACKED/0 FAIL) post ack-fix b5f131e. "
    "Target: restore banked 0.947-class. Base ver-10/ver-11: LB 0.947."
)

# Lỗi kiểu này → DỪNG tuyệt đối, KHÔNG push version mới (theo đề bài)
STOP_VERSION_PATTERNS = ("re-run", "rerun", "must be the latest", "latest version",
                         "not the latest", "version is not", "re-run the kernel")

# Exceptions requests coi là transient network (retry đúng 1 lần)
TRANSIENT_EXC_NAMES = {"ConnectionError", "ConnectTimeout", "ReadTimeout", "Timeout",
                       "ChunkedEncodingError", "ProtocolError", "RetryError"}


def print_integrity_chain(version: int) -> None:
    print("== CHUỖI INTEGRITY (read-only, không chạy lại cổng — gate PASS 11:57 UTC đã đứng) ==")
    state = json.loads(STATE.read_text()) if STATE.is_file() else {}
    print(f"  state.json : ref={state.get('ref')} version={state.get('version')} "
          f"pushed_at={state.get('pushed_at')}")
    sub = OUTPUT_DIR / "submission.csv"
    if sub.is_file():
        md5 = hashlib.md5(sub.read_bytes()).hexdigest()
        rows = sum(1 for _ in open(sub)) - 1
        ok_md5 = md5 == EXPECTED_MD5
        print(f"  output     : {sub.name} {rows:,} rows · md5 {md5[:12]} "
              f"({'MATCH' if ok_md5 else 'MISMATCH vs ' + EXPECTED_MD5[:12]})")
    else:
        print(f"  output     : {sub} KHÔNG TỒN TẠI (thông tin thôi — submit theo kernel, "
              f"không theo file local)")
    print(f"  đích       : {COMPETITION} · kernel {KERNEL_OWNER}/{KERNEL_SLUG} version {version}")


def dump_http_error(exc: BaseException) -> None:
    """In ĐẦY ĐỦ mọi thứ có được từ lỗi — KHÔNG nuốt body (bài học 400 lần 11:57)."""
    print("\n" + "=" * 70)
    print("❌ HTTP ERROR — FULL RESPONSE (không cắt gọn):")
    print("=" * 70)
    resp = getattr(exc, "response", None)
    if resp is not None:
        print(f"status_code : {getattr(resp, 'status_code', '?')}")
        try:
            print(f"reason      : {resp.reason}")
        except Exception:
            pass
        try:
            print(f"url         : {resp.url}")
        except Exception:
            pass
        try:
            print(f"headers     : {dict(resp.headers)}")
        except Exception:
            pass
        body = ""
        try:
            body = resp.text or ""
        except Exception:
            try:
                body = (resp.content or b"").decode("utf-8", "replace")
            except Exception:
                body = "<undecodable>"
        print(f"body        : {body!r}")
    else:
        print("(exception không kèm response object)")
    print(f"exception   : {type(exc).__name__}: {exc}")
    if exc.__cause__ is not None:
        print(f"cause       : {type(exc.__cause__).__name__}: {exc.__cause__}")
    print("=" * 70)


def is_transient(exc: BaseException) -> bool:
    resp = getattr(exc, "response", None)
    code = getattr(resp, "status_code", None) if resp is not None else None
    if isinstance(code, int) and 500 <= code < 600:
        return True
    return type(exc).__name__ in TRANSIENT_EXC_NAMES or (
        exc.__cause__ is not None and type(exc.__cause__).__name__ in TRANSIENT_EXC_NAMES
    )


def mentions_version_stop(exc: BaseException) -> bool:
    resp = getattr(exc, "response", None)
    texts = [str(exc)]
    try:
        texts.append(resp.text or "")
    except Exception:
        pass
    blob = " ".join(texts).lower()
    return any(p in blob for p in STOP_VERSION_PATTERNS)


def do_submit(version: int, message: str):
    """Trả về response object nếu thành công; raise nếu lỗi (caller xử lý dump)."""
    from kagglesdk import KaggleClient
    from kagglesdk.competitions.types.competition_api_service import ApiCreateCodeSubmissionRequest

    client = KaggleClient(verbose=True)
    req = ApiCreateCodeSubmissionRequest()
    req.competition_name = COMPETITION
    req.kernel_owner = KERNEL_OWNER
    req.kernel_slug = KERNEL_SLUG
    req.kernel_version = version
    req.file_name = "submission.csv"
    req.submission_description = message
    return client.competitions.competition_api_client.create_code_submission(req)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--version", type=int, help="kernel version (mặc định: state.json → 1)")
    parser.add_argument("--message", default=DEFAULT_MESSAGE)
    parser.add_argument("--dry-run", action="store_true",
                        help="chỉ in integrity + thông tin submit, không gọi API")
    args = parser.parse_args()

    version = args.version
    if version is None:
        state = json.loads(STATE.read_text()) if STATE.is_file() else {}
        version = state.get("version") if state.get("ref") == f"{KERNEL_OWNER}/{KERNEL_SLUG}" else None
    if version is None:
        version = 1
    print(f"[transport] create_code_submission · {KERNEL_OWNER}/{KERNEL_SLUG} v{version}")
    print_integrity_chain(version)

    if args.dry_run:
        print(f"\n[DRY-RUN] sẽ nộp {KERNEL_OWNER}/{KERNEL_SLUG} version {version} — "
              f"chạy lại không --dry-run để nộp thật.")
        return 0

    token_file = Path.home() / ".kaggle" / "access_token"
    if token_file.is_file():
        os.environ.setdefault("KAGGLE_API_TOKEN", token_file.read_text().strip())
        os.environ.setdefault("KAGGLE_CONFIG_DIR", str(token_file.parent))

    try:
        res = do_submit(version, args.message)
    except Exception as exc:  # HTTPError hoặc bất kỳ lỗi nào
        dump_http_error(exc)
        if mentions_version_stop(exc):
            print("\n⛔ Lỗi nhắc kernel version phải re-run/latest → DỪNG tuyệt đối "
                  "(KHÔNG push version mới — ngoài phạm vi nhiệm vụ).")
            return 1
        if is_transient(exc):
            print("\n⚠ Lỗi 5xx/network transient → retry ĐÚNG 1 lần sau 15s...")
            time.sleep(15)
            try:
                res = do_submit(version, args.message)
            except Exception as exc2:
                dump_http_error(exc2)
                if mentions_version_stop(exc2):
                    print("\n⛔ Lỗi nhắc kernel version phải re-run/latest → DỪNG tuyệt đối.")
                print("\n⛔ Submit THẤT BẠI sau 1 retry — DỪNG (L13b: không override).")
                return 1
        else:
            print("\n⛔ Submit THẤT BẠI (4xx) — DỪNG, KHÔNG retry (L13b). "
                  "Body lỗi nguyên văn ở trên.")
            return 1
    except BaseException:
        traceback.print_exc()
        print("\n⛔ Lỗi ngoài dự kiến — DỪNG.")
        return 1

    print(f"\n✅ ĐÃ NỘP {KERNEL_OWNER}/{KERNEL_SLUG} version {version}: {res}")
    print("Xem điểm: python3 ktool.py score  ·  (code submission có thể tạo shadow entry ~10s sau)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
