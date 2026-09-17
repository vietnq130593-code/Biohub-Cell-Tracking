# -*- coding: utf-8 -*-
# v10_ckpt_watchdog.py — chạy TRÊN Colab VM (background) cạnh cell 3 (v10_cell3_run.py).
#
# MỤC TIÊU: session Colab T4 sống ~3.5h rồi bị giết (f37bae chết 01:42 UTC làm mất
# toàn bộ predict validator + grid). Watchdog này bảo vệ kết quả bằng cách upload lên
# 2 dataset Kaggle PRIVATE ngay khi artefact xuất hiện trên đĩa VM:
#   A) vietnguyen130593/biohub-v10-checkpoints — file NHỎ (log cell3 + csv/json kết quả)
#      · push khi file "now" đổi (rate-limit 4 phút) hoặc log đổi (rate-limit 15 phút)
#      · log cell 3 chứa dòng "[v10-lab] <config> adjEJ=... proxy=..." flush từng config
#        → mất session giữa chừng vẫn đọc được kết quả từng config đã xong
#   B) vietnguyen130593/biohub-v10-rawgraphs — raw_graphs.json + gt_bundle.json + meta.json
#      (cache đắt nhất: predict 1-2h GPU) → push ĐÚNG 1 LẦN khi dump ổn định 2 vòng poll
#      → có cache này thì grid sweep replay được trên CPU (kernel CPU / session CPU)
#
# Chạy:  python3 -u /content/v10_ckpt_watchdog.py   (start_new_session, tự thoát khi xong)
# Log:   /content/v10_ckpt.log

import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

# --- auth Kaggle (giống cell 2 — token nhúng; env được subprocess kế thừa) ---
KAGGLE_API_TOKEN = "KGAT_14164511bf6b0ba6b14ed9050ffdea66"
os.environ["KAGGLE_API_TOKEN"] = KAGGLE_API_TOKEN

WATCH_LOG = "/content/v10_ckpt.log"
CELL3_LOG = "/content/v10_cell3.log"
CELL2_LOG = "/content/v10_cell2.log"
ENV_JSON = "/content/v10_env.json"
DS_A = "vietnguyen130593/biohub-v10-checkpoints"
DS_B = "vietnguyen130593/biohub-v10-rawgraphs"
STAGE_A = Path("/content/v10_stage_ckpt")
STAGE_B = Path("/content/v10_stage_raw")

POLL_S = int(os.environ.get("V10_CKPT_POLL_S", "60"))           # quét artefact mỗi 60s
MIN_PUSH_GAP_S = int(os.environ.get("V10_CKPT_MIN_PUSH_GAP_S", "240"))  # giãn tối thiểu giữa 2 lần push A
LOG_PUSH_GAP_S = int(os.environ.get("V10_CKPT_LOG_PUSH_GAP_S", "900"))  # push vì log đổi: 1 lần / 15 phút
DEAD_EXIT_S = int(os.environ.get("V10_CKPT_DEAD_EXIT_S", "1800"))       # cell 3 chết + chưa có rows → thoát sau 30'


def wlog(msg: str) -> None:
    line = time.strftime("[%Y-%m-%d %H:%M:%S] ") + msg
    print(line, flush=True)
    try:
        with open(WATCH_LOG, "a") as f:
            f.write(line + "\n")
    except OSError:
        pass


# --- WORKING_ROOT: cell 2 ghi /content/v10_env.json; fallback như monolith ---
_wr = None
try:
    _wr = Path(json.loads(Path(ENV_JSON).read_text())["V10_WORKING_ROOT"])
except Exception:
    pass
if _wr is None or not _wr.is_dir():
    _wr = Path("/content/kaggle/working")
WORKING_DIR = _wr
wlog("watchdog start · WORKING_DIR=%s · pid=%d" % (WORKING_DIR, os.getpid()))


def kaggle_cmd():
    for cand in ([sys.executable, "-m", "kaggle"], ["kaggle"]):
        try:
            r = subprocess.run(cand + ["--version"], capture_output=True, text=True, timeout=180)
            if r.returncode == 0:
                return cand
        except Exception:
            pass
    raise SystemExit("kaggle CLI không chạy được (cần kaggle>=2.2 — cell 2 đã upgrade)")


KC = kaggle_cmd()
wlog("kaggle cmd: %s" % " ".join(KC))


def md5(p: Path) -> str:
    h = hashlib.md5()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def meta_json(stage: Path, ds: str, title: str) -> None:
    stage.mkdir(parents=True, exist_ok=True)
    (stage / "dataset-metadata.json").write_text(json.dumps({
        "title": title,
        "id": ds,
        "private": True,
        "licenses": [{"name": "CC0-1.0"}],
    }, indent=1))


def ensure_dataset(stage: Path, ds: str, title: str) -> bool:
    r = subprocess.run(KC + ["datasets", "status", ds], capture_output=True, text=True, timeout=300)
    if r.returncode == 0:
        return True
    meta_json(stage, ds, title)
    r2 = subprocess.run(KC + ["datasets", "create", "-p", str(stage)], capture_output=True, text=True, timeout=900)
    wlog("create %s rc=%d :: %s" % (ds, r2.returncode, ((r2.stdout or "") + (r2.stderr or "")).strip()[:250]))
    return r2.returncode == 0


def push(stage: Path, ds: str, title: str, msg: str) -> bool:
    meta_json(stage, ds, title)
    r = subprocess.run(KC + ["datasets", "version", "-p", str(stage), "-m", msg],
                       capture_output=True, text=True, timeout=3600)
    ok = r.returncode == 0
    wlog("push %s rc=%d :: %s" % (ds, r.returncode, ((r.stdout or "") + (r.stderr or "")).strip()[:250]))
    return ok


def cell3_alive() -> bool:
    r = subprocess.run(["pgrep", "-f", "v10_cell3_run.py"], capture_output=True, text=True)
    return bool(r.stdout.strip())


def final_push(reason: str) -> None:
    """Đồng bộ TOÀN BỘ artefact hiện có + manifest + push chốt dataset A."""
    for src, name, _tier in SOURCES_A:
        if src.exists():
            try:
                subprocess.run(["cp", "-f", str(src), str(STAGE_A / name)], check=True)
            except Exception as e:
                wlog("copy A fail %s: %r" % (src, e))
    (STAGE_A / "ckpt_manifest.json").write_text(json.dumps({
        "pushed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "reason": reason,
        "files": {name: state.get(str(src)) for src, name, _t in SOURCES_A if src.exists()},
        "b_pushed": b_pushed,
        "cell3_alive": cell3_alive(),
    }, indent=2, sort_keys=True) + "\n")
    push(STAGE_A, DS_A, "biohub-v10-checkpoints", "final %s %s" % (reason, time.strftime("%Y%m%d-%H%M")))


# --- artefact: (src Path, tên file stage, tier) — tier "now" = push ngay khi đổi ---
SOURCES_A = [
    (WORKING_DIR / "v10_lab_rows.csv", "v10_lab_rows.csv", "now"),
    (WORKING_DIR / "v10_lab_report.json", "v10_lab_report.json", "now"),
    (WORKING_DIR / "ppsweep_results.csv", "ppsweep_results.csv", "now"),
    (WORKING_DIR / "ppsweep_selected.json", "ppsweep_selected.json", "now"),
    (WORKING_DIR / "validator_results.csv", "validator_results.csv", "now"),
    (WORKING_DIR / "dual_seed_frame_retention_guard_report.json", "guard_report.json", "now"),
    (Path(ENV_JSON), "v10_env.json", "now"),
    (Path(CELL3_LOG), "v10_cell3.log", "log"),
    (Path(CELL2_LOG), "v10_cell2.log", "log"),
]
SOURCES_B = [
    (WORKING_DIR / "v10_lab_cache" / "raw_graphs.json", "raw_graphs.json"),
    (WORKING_DIR / "v10_lab_cache" / "gt_bundle.json", "gt_bundle.json"),
    (WORKING_DIR / "v10_lab_cache" / "meta.json", "meta.json"),
]

for _d in (STAGE_A, STAGE_B):
    _d.mkdir(parents=True, exist_ok=True)
ensure_dataset(STAGE_A, DS_A, "biohub-v10-checkpoints")
ensure_dataset(STAGE_B, DS_B, "biohub-v10-rawgraphs")

state = {}            # src str -> md5
b_hash_seen = None    # md5 raw_graphs.json vòng poll trước (chờ ổn định 2 vòng)
b_pushed = False
last_a_push = 0.0
last_log_push = 0.0
last_rows_push = 0.0
first_dead_seen = None

wlog("vào vòng poll (POLL_S=%d)" % POLL_S)

while True:
    now = time.time()

    # ---------- B: raw graphs cache — push đúng 1 lần khi dump xong ----------
    if not b_pushed:
        raw = SOURCES_B[0][0]
        if raw.exists():
            try:
                h = md5(raw)
            except OSError:
                h = None
            if h is not None and h == b_hash_seen:
                copied = []
                for src, name in SOURCES_B:
                    if src.exists():
                        try:
                            subprocess.run(["cp", "-f", str(src), str(STAGE_B / name)], check=True)
                            copied.append(name)
                        except Exception as e:
                            wlog("copy B fail %s: %r" % (src, e))
                if copied:
                    if push(STAGE_B, DS_B, "biohub-v10-rawgraphs",
                            "rawgraphs dump %s (%d files)" % (time.strftime("%H:%M"), len(copied))):
                        b_pushed = True
                        wlog("★ RAWGRAPHS CACHE ĐÃ AN TOÀN TRÊN KAGGLE (%d files)" % len(copied))
            else:
                b_hash_seen = h  # lần đầu thấy / vẫn đang đổi — vòng sau xác nhận
        else:
            b_hash_seen = None

    # ---------- A: file nhỏ ----------
    changed_now, changed_log = [], []
    for src, name, tier in SOURCES_A:
        if not src.exists():
            continue
        try:
            h = md5(src)
        except OSError:
            continue
        if state.get(str(src)) != h:
            state[str(src)] = h
            (changed_now if tier == "now" else changed_log).append(name)

    should_push = False
    if changed_now and (now - last_a_push) >= MIN_PUSH_GAP_S:
        should_push = True
    elif changed_log and (now - last_log_push) >= LOG_PUSH_GAP_S:
        should_push = True

    if should_push:
        for src, name, _tier in SOURCES_A:
            if src.exists():
                try:
                    subprocess.run(["cp", "-f", str(src), str(STAGE_A / name)], check=True)
                except Exception as e:
                    wlog("copy A fail %s: %r" % (src, e))
        (STAGE_A / "ckpt_manifest.json").write_text(json.dumps({
            "pushed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "files": {name: state.get(str(src)) for src, name, _t in SOURCES_A if src.exists()},
            "b_pushed": b_pushed,
            "cell3_alive": cell3_alive(),
        }, indent=2, sort_keys=True) + "\n")
        ok = push(STAGE_A, DS_A, "biohub-v10-checkpoints", "ckpt %s" % time.strftime("%Y%m%d-%H%M"))
        last_a_push = time.time()
        if changed_log:
            last_log_push = last_a_push
        if "v10_lab_rows.csv" in changed_now and ok:
            last_rows_push = last_a_push
            wlog("★ KẾT QUẢ GRID (v10_lab_rows.csv) ĐÃ LÊN KAGGLE")

    # ---------- điều kiện thoát ----------
    rows_path = WORKING_DIR / "v10_lab_rows.csv"
    if not cell3_alive():
        if first_dead_seen is None:
            first_dead_seen = now
            wlog("cell 3 process đã chết — chờ artefact cuối (tối đa %ds)" % DEAD_EXIT_S)
        rows_pushed = rows_path.exists() and last_rows_push > 0 and (now - last_rows_push) >= 30
        if rows_pushed or (now - first_dead_seen) >= DEAD_EXIT_S:
            reason = "complete" if rows_pushed else "partial-after-dead"
            final_push(reason)
            wlog("WATCHDOG %s — thoát" % reason.upper())
            break
    else:
        first_dead_seen = None

    time.sleep(POLL_S)
