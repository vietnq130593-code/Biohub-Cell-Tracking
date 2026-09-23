#!/usr/bin/env python3
"""submit-v132.py — Submit v13.2 VỚI CỔNG CỨNG CƠ HỌC (ERRORS-LEDGER.md §4).

Khác biệt với mọi submit script cũ: `machinery-audit.py --submit-gate` chạy
TRƯỚC và exit-code được tôn trọng tuyệt đối (L13b — không override bằng lập luận).
Audit FAIL → script tự hủy TRƯỚC khi chạm Kaggle.

Luồng:
  1. Pull output kernel biohub-ver132 (run_stats.csv + submission.csv + log).
  2. machinery-audit 3 lớp: CONFIG (notebook đã chạy) + RECEIPT + CENSUS.
     - 🔴 FAIL nào → hủy.
     - 🟡 hypothesis WARN → phải --ack TƯỜNG MINH từng knob.
  3. Persist ≥ PERSIST_MIN phút sau COMPLETE (L3) — pull verify md5 submission.
  4. Submit + in ref.

Ví dụ (ack GC3 + leaf — hai giả thuyết còn lại của v13.2):
  python3 submit-v132.py --ack BIOHUB_GAP_CLOSE_UM,BIOHUB_LEAF_PRUNE_MIN_EDGE_PROB \
      --message "ver-13.2 restore-division..."
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
COMPETITION = "biohub-cell-tracking-during-development"
SLUG = "biohub-ver132"
OUTDIR = HERE / "output" / "ver132"
MONOLITH = PROJECT / "kaggle" / "ver-13-2" / "cell-monolith.py"
PERSIST_MIN = 20  # L3


def kaggle(args: list[str]) -> subprocess.CompletedProcess:
    env = None
    tok = Path.home() / ".kaggle" / "access_token"
    if tok.is_file():
        import os
        env = os.environ.copy()
        env.setdefault("KAGGLE_API_TOKEN", tok.read_text().strip())
    return subprocess.run([sys.executable, "-m", "kaggle", *args],
                          text=True, capture_output=True, env=env)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ack", default="", help="knob hypothesis được ack, cách nhau phẩy")
    ap.add_argument("--message", default="ver-13.2 restore-division (L13c) + GC3 + leaf")
    ap.add_argument("--skip-pull", action="store_true", help="dùng output đã pull sẵn")
    args = ap.parse_args()

    username = json.loads((Path.home() / ".kaggle" / "kaggle.json").read_text())["username"] \
        if (Path.home() / ".kaggle" / "kaggle.json").is_file() else None
    if username is None:
        proc = kaggle(["kernels", "list", "--mine", "--page-size", "5", "--format", "json"])
        for item in json.loads(proc.stdout or "[]"):
            ref = str(item.get("ref") or "")
            if "/" in ref:
                username = ref.split("/", 1)[0]
                break
    ref = f"{username}/{SLUG}"
    print(f"Kernel: {ref}")

    # (1) pull output
    if not args.skip_pull:
        OUTDIR.mkdir(parents=True, exist_ok=True)
        print("Pull output kernel...")
        proc = kaggle(["kernels", "output", ref, "-p", str(OUTDIR)])
        print((proc.stdout or "")[-300:])
        if proc.returncode != 0:
            sys.exit(f"❌ pull output fail: {proc.stderr[-300:]}")
    rs, sc = OUTDIR / "run_stats.csv", OUTDIR / "submission.csv"
    if not rs.is_file() or not sc.is_file():
        sys.exit("❌ output thiếu run_stats.csv/submission.csv — kernel chưa COMPLETE?")

    # (2) audit 3 lớp — HARD, exit-code được tôn trọng tuyệt đối (L13b)
    cmd = [sys.executable, str(HERE / "machinery-audit.py"),
           "--dir", str(OUTDIR), "--monolith", str(MONOLITH), "--submit-gate"]
    if args.ack:
        cmd += ["--ack", args.ack]
    print("\n>>> MACHINERY AUDIT (gate cứng — L13):")
    rc = subprocess.run(cmd).returncode
    if rc != 0:
        sys.exit(f"\n⛔ AUDIT KHÔNG PASS (exit {rc}) — HỦY SUBMIT (L13b: không override). "
                 "Sửa build/chạy lại kernel, hoặc ack knob hypothesis hợp lệ bằng --ack.")

    # (3) persist ≥20' sau COMPLETE (L3) — dùng mtime file output như proxy
    age_min = (time.time() - sc.stat().st_mtime) / 60
    if age_min < PERSIST_MIN and not args.skip_pull:
        wait = PERSIST_MIN - age_min
        print(f"Persist L3: chờ thêm {wait:.0f}' cho chắc (totalBytes=0 lesson)...")
        time.sleep(wait * 60)
    md5 = hashlib.md5(sc.read_bytes()).hexdigest()
    rows = sum(1 for _ in open(sc)) - 1
    print(f"submission.csv: {rows:,} rows · md5 {md5[:12]}")

    # (4) submit
    print("\nSubmit...")
    proc = kaggle(["competitions", "submit", "-c", COMPETITION,
                   "-f", str(sc), "-m", args.message])
    print(proc.stdout or "")
    if proc.returncode != 0:
        sys.exit(f"❌ submit fail: {proc.stderr[-300:]}")
    print(f"✅ Đã submit {datetime.now(timezone.utc).isoformat()}")
    print("Poll: python3 ktool.py score  ·  worklog: dán audit + ref + điểm")


if __name__ == "__main__":
    main()
