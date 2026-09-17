#!/usr/bin/env python3
"""submit-v10.py — Nộp kernel ver-10 vào competition biohub (notebooks-only).

Cuộc thi chỉ nhận code submission từ kernel version (CLI file submit bị 400 —
đã kiểm chứng 15/9). Dùng kagglesdk CompetitionApiClient.create_code_submission:

  python3 submit-v10.py [--version N] [--message "..."]

Nếu --version bỏ qua: tự đọc state.json của lần push --ver 10 gần nhất.
"""
import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STATE = ROOT / "state.json"
COMPETITION = "biohub-cell-tracking-during-development"
KERNEL_OWNER = "vietnguyen130593"
KERNEL_SLUG = "biohub-ver10"

DEFAULT_MESSAGE = (
    "ver-10 v3-fast + HOCT consensus veto MODE 1 (division-safe) + density-aware TLE guard: "
    "cap 300s/video, deadline 7.5h, est k*n*d_max x3 above 550/frame, mid-video chunk abort; "
    "no RLF (dead), no gate replay. V10-LAB: adjEJ +0.001828, proxy +0.001828, div 4/1/8 intact"
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", type=int, help="kernel version (mặc định: state.json)")
    parser.add_argument("--message", default=DEFAULT_MESSAGE)
    args = parser.parse_args()

    version = args.version
    if version is None:
        state = json.loads(STATE.read_text()) if STATE.is_file() else {}
        version = state.get("version")
        if version is None or state.get("ref") != f"{KERNEL_OWNER}/{KERNEL_SLUG}":
            sys.exit("Không biết version — chạy `python3 ktool.py push --ver 10` trước hoặc dùng --version N.")

    token_file = Path.home() / ".kaggle" / "access_token"
    if token_file.is_file():
        os.environ.setdefault("KAGGLE_API_TOKEN", token_file.read_text().strip())
        os.environ.setdefault("KAGGLE_CONFIG_DIR", str(token_file.parent))

    from kagglesdk import KaggleClient
    from kagglesdk.competitions.types.competition_api_service import ApiCreateCodeSubmissionRequest

    client = KaggleClient(verbose=True)
    req = ApiCreateCodeSubmissionRequest()
    req.competition_name = COMPETITION
    req.kernel_owner = KERNEL_OWNER
    req.kernel_slug = KERNEL_SLUG
    req.kernel_version = version
    req.file_name = "submission.csv"
    req.submission_description = args.message
    res = client.competitions.create_code_submission(req)
    print(f"\nĐÃ NỘP {KERNEL_OWNER}/{KERNEL_SLUG} version {version}: {res}")
    print("Xem điểm: python3 ktool.py score")
    return 0


if __name__ == "__main__":
    sys.exit(main())
