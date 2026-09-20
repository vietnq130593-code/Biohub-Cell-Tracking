#!/usr/bin/env python3
"""submit-v11.py — Nộp kernel ver-11 vào competition biohub (notebooks-only).

Cuộc thi chỉ nhận code submission từ kernel version (CLI file submit bị 400 —
đã kiểm chứng 15/9). Dùng kagglesdk CompetitionApiClient.create_code_submission:

  python3 submit-v11.py [--version N] [--message "..."]

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
KERNEL_SLUG = "biohub-ver11"

DEFAULT_MESSAGE = (
    "ver-11 = ver-10 (LB 0.947) + v11-lab v3 grid (kernel biohub-v11-lab v4, 20/9): "
    "SAFE_DIV_REQUIRE_MUTUAL_NN=0 + SAFE_DIV_MIN_PDIV floor (B-7 van FP) — funnel B-6: "
    "2/9 FN mutual_nn recoverable, pool 319 -> ~46/39 theo floor; grid D-gates PASS. "
    "Base ver-10: HOCT veto mode 1 + density guard, no RLF, no gate replay"
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
    res = client.competitions.competition_api_client.create_code_submission(req)
    print(f"\nĐÃ NỘP {KERNEL_OWNER}/{KERNEL_SLUG} version {version}: {res}")
    print("Xem điểm: python3 ktool.py score")
    return 0


if __name__ == "__main__":
    sys.exit(main())
