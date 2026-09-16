#!/usr/bin/env python3
"""ktool.py — Điều khiển Kaggle API cho pipeline Biohub ver-6/7/7b (chạy trong sandbox).

(Ghi chú 13/9: sandbox bị rollback về 12/9 tối — file này được tái tạo nguyên trạng
bản cuối cùng có hỗ trợ --ver 6/7/7b; ver-7 đã push trước rollback nên an toàn trên Kaggle.)

Chuẩn bị 1 lần (token lấy ở kaggle.com → Settings → API → Generate New Token):
  python3 ktool.py token '<token-mới>'          # token dạng chuỗi
  python3 ktool.py token '{"username":"...","key":"..."}'   # kaggle.json cũ

Sau đó chạy lần lượt (hoặc `pipeline` để chạy một mạch):
  python3 ktool.py verify --ver 7    # auth + competition + 6 dataset ver-7 + quota GPU
  python3 ktool.py push   --ver 7    # đẩy ver-7 (port 0.947 + Phase B) → Save & Run All (T4×2, OFF)
  python3 ktool.py watch  --ver 7    # theo dõi ~40-50 phút, xong tự tải output
  python3 ktool.py submit             # nộp notebook version vào competition
  python3 ktool.py score              # xem bảng submissions + điểm public LB
  python3 ktool.py pipeline --ver 7   # push → watch → submit → score

--ver: 6 = ver-6 (3 dataset); 7 = ver-7 port 0.947 + Phase B (6 dataset);
       7b = + Phase C divnet ranker (7 dataset, kernel biohub-ver7b).

Các lệnh phụ: status, output, kernels (liệt kê kernel của mình).
Token được lưu tại ~/.kaggle (chmod 600). Xong việc nên bấm "Expire" trên trang API.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent          # <project>/kaggle/api/
PROJECT = ROOT.parents[1]                        # <project>/
NOTEBOOK = PROJECT / "download" / "ver6-cell-tracking.ipynb"
STAGING = ROOT / "push-staging"
OUTDIR = ROOT / "output"
STATE = ROOT / "state.json"
KAGGLE_HOME = Path.home() / ".kaggle"

COMPETITION = "biohub-cell-tracking-during-development"
DATASETS = [
    "pilkwang/biohub-tracking-support-pack-50ep-v1",
    "pilkwang/biohub-deepcenter-unet3d-center-prior-v1",
    "pilkwang/biohub-temporal-unet3d-seed314159-v1",
]
# ver-7: 3 dataset pilkwang + 3 dataset hạ tầng Phase B (official scorer + CV pack + baseline v6)
VER7_NOTEBOOK = PROJECT / "download" / "ver7-cell-tracking.ipynb"
VER7_DATASETS = DATASETS + [
    "dalloliogm/biohub-official-scorer-patched",
    "dariushafshar/biohub-local-cv-pack",
    "vietnguyen130593/biohub-v6-heldout-preds",
]
VER7_SLUG = "biohub-ver7"
# ver-7b: Phase C — ver-7 + divnet RANK-ONLY + nới gate (thêm dataset giorgosi/biohub-divnet-v2)
VER7B_NOTEBOOK = PROJECT / "download" / "ver7b-cell-tracking.ipynb"
VER7B_DATASETS = VER7_DATASETS + ["giorgosi/biohub-divnet-v2"]
VER7B_SLUG = "biohub-ver7b"
# ver-8 wave1: mini-kernel CPU (E0 gate-audit + E1 system-view + E2 ppsweep-2 + E3) — 0 GPU
VER8W1_NOTEBOOK = PROJECT / "download" / "ver8-wave1.ipynb"
VER8W1_DATASETS = [
    "pilkwang/biohub-tracking-support-pack-50ep-v1",
    "dalloliogm/biohub-official-scorer-patched",
    "vietnguyen130593/biohub-v7-heldout-preds",
    "pilkwang/biohub-deepcenter-unet3d-center-prior-v1",
    "giorgosi/biohub-divnet-v2",
    "vietnguyen130593/biohub-wave1-features",
]
VER8W1_SLUG = "biohub-ver8-wave1"
# ver-8: Phase D — re-parenting division recovery + DivNet RANK-ONLY (gate gốc)
VER8_NOTEBOOK = PROJECT / "download" / "ver8-cell-tracking.ipynb"
VER8_DATASETS = VER7_DATASETS + ["giorgosi/biohub-divnet-v2"]
VER8_SLUG = "biohub-ver8"
# ver-9: Phase E — v3-fast (bỏ sweep, hardcode tight 5.5/6.5) + HOCT consensus veto
# mode 2 (port sjlee101 cell 6/12) + repeat-lineage filter (port pawanmali cell 10.5)
# + [ver9-gate] cổng §6 rev-2 trong kernel. 9 input = 7 của ver-8 + 2 dataset HOCT.
VER9_NOTEBOOK = PROJECT / "download" / "ver9-cell-tracking.ipynb"
VER9_DATASETS = VER8_DATASETS + [
    "sjlee101/biohub-hoct-020-wheels",
    "musculer/biohub-hoct-general-v0-official",
]
VER9_SLUG = "biohub-ver9"
ACCELERATOR = "NvidiaTeslaT4"   # GPU T4 × 2 (giống notebook gốc 0.945) — enum theo kagglesdk
DEFAULT_SLUG = "biohub-ver6"
POLL_SECONDS = 60
WATCH_TIMEOUT_MIN = 300   # ver-9 (~2,5-3h: core + HOCT test + gate 8 stems) — dự phòng 5h
WATCH_TIMEOUT_MIN_CPU = 700   # wave1 CPU chạy 2,5-4h (deadline nội bộ 8,5h)


def version_config(ver) -> tuple[Path, list[str], str]:
    """(notebook, datasets, slug) — '6': ver-6; '7': ver-7 port 0.947 + Phase B;
    '7b': + Phase C divnet; '8w1': wave1 mini-kernel CPU (E0-E3)."""
    ver = str(ver)
    if ver == "7":
        return VER7_NOTEBOOK, VER7_DATASETS, VER7_SLUG
    if ver == "7b":
        return VER7B_NOTEBOOK, VER7B_DATASETS, VER7B_SLUG
    if ver == "8w1":
        return VER8W1_NOTEBOOK, VER8W1_DATASETS, VER8W1_SLUG
    if ver == "8":
        return VER8_NOTEBOOK, VER8_DATASETS, VER8_SLUG
    if ver == "9":
        return VER9_NOTEBOOK, VER9_DATASETS, VER9_SLUG
    return NOTEBOOK, DATASETS, DEFAULT_SLUG


def run_kaggle(args: list[str]) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    token_file = KAGGLE_HOME / "access_token"
    if token_file.is_file():
        env.setdefault("KAGGLE_API_TOKEN", token_file.read_text().strip())
    env.setdefault("KAGGLE_CONFIG_DIR", str(KAGGLE_HOME))
    return subprocess.run(
        [sys.executable, "-m", "kaggle", *args],
        text=True,
        capture_output=True,
        env=env,
    )


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def fail(proc: subprocess.CompletedProcess, action: str) -> None:
    print(proc.stdout or "", end="")
    print(proc.stderr or "", end="", file=sys.stderr)
    raise SystemExit(f"THẤT BẠI khi {action} (exit {proc.returncode}). "
                     f"Kiểm tra token/luồng ở trên.")


# ---------------------------------------------------------------------------
# token
# ---------------------------------------------------------------------------

def cmd_token(args: argparse.Namespace) -> None:
    import json as _json
    content = args.value
    if args.file:
        content = Path(args.file).read_text().strip()
    if not content:
        raise SystemExit("Cần token (chuỗi hoặc JSON kaggle.json) — xem `ktool.py token -h`.")
    KAGGLE_HOME.mkdir(parents=True, exist_ok=True)
    shown = ""
    target = KAGGLE_HOME / "access_token"
    if content.strip().startswith("{"):
        data = _json.loads(content)
        username = data.get("username", "")
        (KAGGLE_HOME / "kaggle.json").write_text(_json.dumps(data) + "\n")
        (KAGGLE_HOME / "kaggle.json").chmod(0o600)
        token = data.get("key", "")
        if token:
            target.write_text(token + "\n")
            shown = f"username={username} key={token[:6]}…"
    else:
        target.write_text(content + "\n")
        shown = f"token={content[:6]}…"
    target.chmod(0o600)
    print(f"Đã lưu {target} (chmod 600) — {shown}")
    print("Bước tiếp theo: python3 ktool.py verify")


# ---------------------------------------------------------------------------
# username / ref
# ---------------------------------------------------------------------------

def detect_username() -> str:
    classic = KAGGLE_HOME / "kaggle.json"
    if classic.is_file():
        try:
            return json.loads(classic.read_text())["username"]
        except Exception:
            pass
    proc = run_kaggle(["kernels", "list", "--mine", "--page-size", "5", "--format", "json"])
    if proc.returncode == 0 and proc.stdout.strip():
        try:
            items = json.loads(proc.stdout)
            for item in items:
                ref = str(item.get("ref") or item.get("slug") or "")
                if "/" in ref:
                    return ref.split("/", 1)[0]
        except Exception:
            pass
    raise SystemExit("Không tự xác định được username. Dùng `push --username <tên-tài-khoản>`.")


def resolve_ref(args_slug: str | None, args_username: str | None, default_slug: str = DEFAULT_SLUG) -> str:
    if args_slug and "/" in args_slug:
        return args_slug
    username = args_username or detect_username()
    return f"{username}/{args_slug or default_slug}"


def load_state() -> dict:
    if STATE.is_file():
        try:
            return json.loads(STATE.read_text())
        except Exception:
            return {}
    return {}


# ---------------------------------------------------------------------------
# verify
# ---------------------------------------------------------------------------

def check(label: str, args: list[str], show_lines: int = 4) -> bool:
    proc = run_kaggle(args)
    ok = proc.returncode == 0
    print(f"[{'ĐẠT' if ok else 'LỖI'}] {label}")
    lines = (proc.stdout or proc.stderr or "").strip().splitlines()
    for line in lines[:show_lines]:
        print("      " + line)
    return ok


def cmd_verify(args: argparse.Namespace) -> None:
    _, ver_datasets, _ = version_config(args.ver)
    print("== 1) Xác thực token ==")
    ok = check("Token hợp lệ (GPU quota)", ["quota"])
    print("\n== 2) Competition ==")
    ok &= check(f"Truy cập competition {COMPETITION}",
                ["competitions", "files", "-v", COMPETITION], show_lines=3)
    print(f"\n== 3) Dataset gắn kernel ver-{args.ver} ({len(ver_datasets)}) ==")
    for ds in ver_datasets:
        ok &= check(f"Dataset {ds}", ["datasets", "files", "-v", ds], show_lines=3)
    print("\n== 4) Submissions đã nộp ==")
    check("Submissions", ["competitions", "submissions", "-v", COMPETITION], show_lines=6)
    try:
        print(f"\nUsername phát hiện: {detect_username()}")
    except SystemExit as exc:
        print(f"\nUsername: {exc}")
    print("\nKẾT LUẬN:", f"SẴN SÀNG push ver-{args.ver}." if ok else "Còn lỗi ở trên — sửa trước khi push.")


# ---------------------------------------------------------------------------
# push
# ---------------------------------------------------------------------------

def cmd_push(args: argparse.Namespace) -> dict:
    notebook, ver_datasets, ver_slug = version_config(args.ver)
    if not notebook.is_file():
        raise SystemExit(f"Không tìm thấy notebook: {notebook}")
    username = args.username or detect_username()
    slug = args.slug or ver_slug
    ref = f"{username}/{slug}"

    if STAGING.exists():
        shutil.rmtree(STAGING)
    STAGING.mkdir(parents=True)
    shutil.copy2(notebook, STAGING / notebook.name)

    metadata = {
        "id": ref,
        "title": slug,
        "code_file": notebook.name,
        "language": "python",
        "kernel_type": "notebook",
        "is_private": not args.public,
        "enable_gpu": str(args.ver) not in ("8w1",),   # wave1 là kernel CPU thuần
        "enable_tpu": False,
        "enable_internet": False,
        "machine_shape": ACCELERATOR if str(args.ver) != "8w1" else None,
        "dataset_sources": ver_datasets,
        "competition_sources": [COMPETITION],
        "kernel_sources": [],
        "model_sources": [],
    }
    if metadata["machine_shape"] is None:
        del metadata["machine_shape"]  # kernel CPU: không đặt machine_shape
    gpu_note = "CPU (0 GPU quota)" if str(args.ver) == "8w1" else f"GPU {ACCELERATOR}"
    (STAGING / "kernel-metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(f"Push {ref} (ver-{args.ver}) — {gpu_note}, Internet OFF, "
          f"{len(ver_datasets)} dataset + competition")
    proc = run_kaggle(["kernels", "push", "-p", str(STAGING)])
    print(proc.stdout or "", end="")
    if proc.returncode != 0:
        fail(proc, f"push {ref}")

    match = re.search(r"version\s+(\d+)", proc.stdout or "", re.IGNORECASE)
    version = int(match.group(1)) if match else None
    state = {"ref": ref, "version": version, "pushed_at": datetime.now().isoformat(timespec="seconds")}
    STATE.write_text(json.dumps(state, indent=2) + "\n")
    print(f"\nĐã push: {ref} (version {version}) — lưu state.json")
    print("Theo dõi: python3 ktool.py watch --ver " + str(args.ver))
    return state


# ---------------------------------------------------------------------------
# status / watch / output
# ---------------------------------------------------------------------------

def kernel_status_text(ref: str) -> str:
    proc = run_kaggle(["kernels", "status", ref])
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return text or "(không có output)"


def classify(text: str) -> str:
    low = text.lower()
    if "complete" in low:
        return "complete"
    if "error" in low:
        return "error"
    if "cancel" in low:
        return "cancel"
    if "running" in low:
        return "running"
    if "queued" in low:
        return "queued"
    return "unknown"


def _default_slug_for(args: argparse.Namespace) -> str:
    return version_config(getattr(args, "ver", "6"))[2]


def cmd_status(args: argparse.Namespace) -> None:
    ref = resolve_ref(args.slug, args.username, _default_slug_for(args))
    print(f"{ref} → {kernel_status_text(ref)}")


def download_output(ref: str) -> Path | None:
    target = OUTDIR / "latest"
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    proc = run_kaggle(["kernels", "output", ref, "-p", str(target)])
    print(proc.stdout or "", end="")
    if proc.returncode != 0:
        print(proc.stderr or "", end="", file=sys.stderr)
        return None
    return target


def report_submission(outdir: Path) -> None:
    matches = sorted(outdir.rglob("submission*.csv"))
    if not matches:
        print("CHÚ Ý: không thấy submission*.csv trong output — kiểm tra log để biết lý do.")
        return
    sub = matches[0]
    lines = sub.read_text().splitlines()
    print(f"submission: {sub} — {len(lines) - 1} dòng dữ liệu (+1 header)")
    print("  header:", lines[0][:160])
    if len(lines) > 1:
        print("  dòng 1:", lines[1][:160])


def cmd_watch(args: argparse.Namespace) -> str:
    ref = resolve_ref(args.slug, args.username, _default_slug_for(args))
    timeout_min = WATCH_TIMEOUT_MIN_CPU if str(getattr(args, "ver", "6")) == "8w1" else WATCH_TIMEOUT_MIN
    deadline = time.time() + timeout_min * 60
    status = "unknown"
    while time.time() < deadline:
        text = kernel_status_text(ref)
        status = classify(text)
        log(f"{ref}: {status} — {text.splitlines()[-1][:100]}")
        if status in ("complete", "error", "cancel"):
            break
        time.sleep(args.poll)
    else:
        raise SystemExit(f"Vượt quá {timeout_min} phút mà chưa xong — xem lại bằng `status`.")

    outdir = download_output(ref)
    if outdir:
        report_submission(outdir)
    if status != "complete":
        raise SystemExit(f"Kernel kết thúc với trạng thái: {status}. Xem output/log ở {OUTDIR}.")
    print("Chạy xong thành công — sẵn sàng submit.")
    return status


def cmd_output(args: argparse.Namespace) -> None:
    ref = resolve_ref(args.slug, args.username, _default_slug_for(args))
    outdir = download_output(ref)
    if outdir:
        report_submission(outdir)


# ---------------------------------------------------------------------------
# submit / score
# ---------------------------------------------------------------------------

def cmd_submit(args: argparse.Namespace) -> None:
    state = load_state()
    # Ưu tiên slug/explicit; nếu không có thì theo state của lần push gần nhất, cuối cùng mới theo --ver
    if args.slug:
        ref = resolve_ref(args.slug, args.username)
    elif state.get("ref"):
        ref = state["ref"]
    else:
        ref = resolve_ref(None, args.username, _default_slug_for(args))
    version = args.version or state.get("version")
    if not version:
        raise SystemExit("Không biết version — chạy `push` trước hoặc chỉ định `submit --version N`.")
    ver = "7b" if "ver7b" in ref else ("7" if "ver7" in ref else "6")
    message = args.message or f"ver-{ver} T4x2 (API push) v{version}"
    proc = run_kaggle([
        "competitions", "submit",
        "-c", COMPETITION,
        "-k", ref,
        "-v", str(version),
        "-f", "submission.csv",
        "-m", message,
    ])
    print(proc.stdout or "", end="")
    if proc.returncode != 0:
        fail(proc, f"submit {ref} v{version}")
    print(f"\nĐã nộp {ref} version {version}. Xem điểm: python3 ktool.py score")


def cmd_score(_: argparse.Namespace) -> None:
    proc = run_kaggle(["competitions", "submissions", "-v", COMPETITION])
    print(proc.stdout or "", end="")
    if proc.returncode != 0:
        fail(proc, "lấy submissions")


def cmd_kernels(_: argparse.Namespace) -> None:
    proc = run_kaggle(["kernels", "list", "--mine", "--page-size", "20"])
    print(proc.stdout or "", end="")


# ---------------------------------------------------------------------------
# pipeline
# ---------------------------------------------------------------------------

def cmd_pipeline(args: argparse.Namespace) -> None:
    print("========== 1/4 PUSH ==========")
    cmd_push(args)
    print("\n========== 2/4 WATCH ==========")
    cmd_watch(args)
    print("\n========== 3/4 SUBMIT ==========")
    cmd_submit(args)
    print("\n========== 4/4 SCORE ==========")
    cmd_score(args)
    print("\nPipeline hoàn tất.")


# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("token", help="cài token (chuỗi mới hoặc kaggle.json cũ)")
    p.add_argument("value", nargs="?", help="nội dung token hoặc JSON kaggle.json")
    p.add_argument("--file", help="đường dẫn tới file token/kaggle.json")
    p.set_defaults(func=cmd_token)

    p = sub.add_parser("verify", help="kiểm tra token + input + quota")
    p.add_argument("--ver", choices=["6", "7", "7b", "8w1", "8", "9"], default="6",
                   help="6: 3 dataset; 7: 6 dataset; 7b: 7 dataset; 8w1: 5 dataset CPU mini-kernel")
    p.set_defaults(func=cmd_verify)

    p = sub.add_parser("push", help="đẩy notebook lên Kaggle và chạy Save & Run All")
    p.add_argument("--username", help="username Kaggle (tự phát hiện nếu có thể)")
    p.add_argument("--slug")
    p.add_argument("--public", action="store_true", help="để public (mặc định private)")
    p.add_argument("--ver", choices=["6", "7", "7b", "8w1", "8", "9"], default="6",
                   help="6: ver-6; 7: ver-7 port 0.947; 7b: + divnet; 8w1: wave1 CPU (E0-E3)")
    p.set_defaults(func=cmd_push)

    p = sub.add_parser("status", help="xem trạng thái run hiện tại")
    p.add_argument("--username")
    p.add_argument("--slug")
    p.add_argument("--ver", choices=["6", "7", "7b", "8w1", "8", "9"], default="6")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("watch", help="đợi chạy xong rồi tải output")
    p.add_argument("--username")
    p.add_argument("--slug")
    p.add_argument("--ver", choices=["6", "7", "7b", "8w1", "8", "9"], default="6")
    p.add_argument("--poll", type=int, default=POLL_SECONDS)
    p.set_defaults(func=cmd_watch)

    p = sub.add_parser("output", help="tải output của run gần nhất")
    p.add_argument("--username")
    p.add_argument("--slug")
    p.add_argument("--ver", choices=["6", "7", "7b", "8w1", "8", "9"], default="6")
    p.set_defaults(func=cmd_output)

    p = sub.add_parser("submit", help="nộp notebook version vào competition")
    p.add_argument("--username")
    p.add_argument("--slug")
    p.add_argument("--version", type=int)
    p.add_argument("--message")
    p.add_argument("--ver", choices=["6", "7", "7b", "8w1", "8", "9"], default="6",
                   help="dùng khi không có --slug và chưa có state push")
    p.set_defaults(func=cmd_submit)

    p = sub.add_parser("score", help="xem submissions + điểm public LB")
    p.set_defaults(func=cmd_score)

    p = sub.add_parser("kernels", help="liệt kê kernel của mình")
    p.set_defaults(func=cmd_kernels)

    p = sub.add_parser("pipeline", help="push → watch → submit → score")
    p.add_argument("--username")
    p.add_argument("--slug")
    p.add_argument("--public", action="store_true")
    p.add_argument("--ver", choices=["6", "7", "7b", "8w1", "8", "9"], default="6")
    p.add_argument("--poll", type=int, default=POLL_SECONDS)
    p.add_argument("--version", type=int)
    p.add_argument("--message")
    p.set_defaults(func=cmd_pipeline)

    args = parser.parse_args()
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
