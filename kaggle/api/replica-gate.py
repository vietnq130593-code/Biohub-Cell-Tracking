#!/usr/bin/env python3
"""replica-gate.py — Cổng PRE-SUBMIT replica (ý tưởng user 21/9: "chạy thử xong so
sánh với phiên bản trước — tốt hơn MỚI nộp, không tốt hơn thì nghiên cứu tiếp").

Nguyên tắc (V12-REPLICA-CALIB receipts):
  * Replica adjEJ SỤT so baseline v11 (0.9010) → HOLD — không nộp, nghiên cứu tiếp.
  * Replica TĂNG ≥ margin (+0.0005) → điều kiện CẦN để nộp (chưa đủ — replica mù
    ngoài cửa sổ GT thưa 1.6%: variant A replica +0.0008 nhưng LB −0.036).
  * Replica BẰNG ± margin nhưng division 05db cửa sổ cải thiện (v11: 0/3) →
    vẫn đáng nộp nếu census lành (không purge fork).
  * Census guard: forks phải ≥ 100 (purge fork = giết div TP — L6/variant A),
    nodes trong ±5% baseline (122,787n / 118,332e / 144 forks).

Luồng:
  1. (tuỳ chọn) kéo output kernel:  python -m kaggle kernels output <owner>/<slug> -p dir
  2. (một lần) khôi phục test-gt:   84 file GT zarr v3 của 4 stem test từ
     competition files API (manifest ~9.400 file, paging 200/page) — khôi phục vào
     /home/z/v11-recovery/test-gt/<stem>.geff/ (ngoài repo, không push GitHub).
  3. chấm replica:                 python3 kaggle/ver-12/v12lab.py replica <csv>
  4. verdict SUBMIT-ELIGIBLE / HOLD + bảng so baseline.

Token: cần ~/.kaggle/access_token (KGAT_…) hoặc ~/.kaggle/kaggle.json — lưu bằng:
  python3 kaggle/api/ktool.py token --value KGAT_xxx   (hoặc --file kaggle.json)

Dùng:
  python3 replica-gate.py --pull                    # kéo output biohub-ver12 + chấm
  python3 replica-gate.py --csv path/submission.csv # chấm CSV có sẵn
  python3 replica-gate.py --restore-gt              # chỉ khôi phục GT (một lần)
  python3 replica-gate.py --pull --baseline 0.9010 --margin 0.0005
"""
from __future__ import annotations

import argparse
import csv as _csv
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile
from collections import Counter
from pathlib import Path

# --------------------------------------------------------------------------
# hằng số (receipts v11 — worklog V12-REPLICA-CALIB + census ver11 20/9)
# --------------------------------------------------------------------------
PROJECT = Path(__file__).resolve().parents[2]
RECOVERY = Path("/home/z/v11-recovery")
GT_DIR = RECOVERY / "test-gt"
V12LAB = PROJECT / "kaggle" / "ver-12" / "v12lab.py"
KAGGLE_HOME = Path.home() / ".kaggle"
COMP = "biohub-cell-tracking-during-development"
OWNER_DEFAULT = "vietnguyen130593"
TEST_STEMS = ["44b6_0113de3b", "44b6_0b24845f", "6bba_05b6850b", "6bba_05db0fb1"]

BASELINE = {  # v11 ref 56403231 — LB 0.947 (bằng v10), replica 0.9010
    "replica_adj": 0.9010,
    "nodes": 122_787,
    "edges": 118_332,
    "forks": 144,
    "div_window": "0/0/3 (TP/FP/FN trên cửa sổ GT 05db — v11)",
}


def log(msg: str) -> None:
    print(f"[replica-gate] {msg}", flush=True)


def kaggle_env() -> dict:
    env = os.environ.copy()
    tok = KAGGLE_HOME / "access_token"
    if tok.is_file():
        env.setdefault("KAGGLE_API_TOKEN", tok.read_text().strip())
    env.setdefault("KAGGLE_CONFIG_DIR", str(KAGGLE_HOME))
    return env


def token_ready() -> bool:
    return (KAGGLE_HOME / "access_token").is_file() or (KAGGLE_HOME / "kaggle.json").is_file()


def run_kaggle(args: list[str], check: bool = True) -> subprocess.CompletedProcess:
    proc = subprocess.run(
        [sys.executable, "-m", "kaggle", *args],
        text=True, capture_output=True, env=kaggle_env(),
    )
    if check and proc.returncode != 0:
        print(proc.stdout or "", end="")
        print(proc.stderr or "", end="", file=sys.stderr)
        raise SystemExit(f"[replica-gate] kaggle CLI thất bại: kaggle {' '.join(args[:3])} … (exit {proc.returncode})")
    return proc


# --------------------------------------------------------------------------
# GT restore — 84 file zarr v3 của 4 stem test từ competition files API
# --------------------------------------------------------------------------
def _list_all_files() -> list[str]:
    """Paging toàn bộ manifest file competition (~9.400 file, 200/page)."""
    names: list[str] = []
    page_token: str | None = None
    while True:
        args = ["competitions", "files", COMP, "--page-size", "200", "--format", "json"]
        if page_token:
            args += ["--page-token", page_token]
        proc = run_kaggle(args)
        raw = (proc.stdout or "").strip()
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            # format khác — thử bọc mảng thô
            m = re.search(r"\[.*\]", raw, re.S)
            payload = json.loads(m.group(0)) if m else []
        items = payload.get("data", payload) if isinstance(payload, dict) else payload
        for it in items or []:
            if isinstance(it, dict):
                nm = it.get("name") or it.get("ref") or ""
            else:
                nm = str(it)
            if nm:
                names.append(nm)
        nxt = None
        if isinstance(payload, dict):
            for k in ("nextPageToken", "next_page_token", "nextPage", "page_token"):
                if payload.get(k):
                    nxt = payload[k]
                    break
        if not nxt or len(names) > 12_000:
            break
        page_token = str(nxt)
    return names


def _download_file(remote: str, dest_dir: Path) -> Path | None:
    """Tải 1 file từ competition (kaggle competitions download -f). Trả về path local."""
    proc = run_kaggle(["competitions", "download", COMP, "-f", remote, "-p", str(dest_dir)], check=False)
    if proc.returncode != 0:
        return None
    cand = dest_dir / Path(remote).name
    if not cand.is_file():
        # server có thể zip: <name>.zip
        z = dest_dir / (Path(remote).name + ".zip")
        if z.is_file() and zipfile.is_zipfile(z):
            with zipfile.ZipFile(z) as zf:
                zf.extractall(dest_dir)
            z.unlink()
        elif z.is_file():
            z.rename(cand)
    return cand if cand.is_file() else None


def restore_gt() -> int:
    if not token_ready():
        raise SystemExit(
            "[replica-gate] Thiếu token Kaggle. Lưu token rồi chạy lại:\n"
            "  python3 kaggle/api/ktool.py token --value KGAT_xxx\n"
            "(hoặc --file kaggle.json; token sống NGOÀI repo — không push GitHub)"
        )
    GT_DIR.mkdir(parents=True, exist_ok=True)
    missing = [s for s in TEST_STEMS if not (GT_DIR / f"{s}.geff").exists()]
    if not missing:
        log(f"test-gt đã đủ 4 stem tại {GT_DIR} — không cần khôi phục")
        return 0
    log(f"liệt kê manifest file competition (paging 200/page)…")
    all_files = _list_all_files()
    log(f"manifest: {len(all_files)} file")
    got = 0
    for stem in missing:
        prefix = f"train/{stem}.geff/"
        stem_files = [f for f in all_files if f.startswith(prefix)]
        if not stem_files:
            # .geff có thể là file đơn
            single = [f for f in all_files if f == f"train/{stem}.geff"]
            if single:
                p = _download_file(single[0], GT_DIR)
                if p:
                    got += 1
                    log(f"  {stem}.geff (file đơn) OK")
                    continue
            log(f"  ⚠ {stem}: không thấy file nào dạng train/{stem}.geff/* trong manifest — khôi phục THỦ CÔNG")
            continue
        target_dir = GT_DIR / f"{stem}.geff"
        n_ok = 0
        for rf in stem_files:
            rel = rf[len(prefix):]           # đường dẫn tương đối trong .geff
            local = target_dir / rel
            if local.is_file():
                n_ok += 1
                continue
            local.parent.mkdir(parents=True, exist_ok=True)
            p = _download_file(rf, local.parent)
            if p and p != local:
                shutil.move(str(p), local)
            if local.is_file():
                n_ok += 1
            else:
                log(f"    ✗ thiếu {rf}")
        log(f"  {stem}.geff: {n_ok}/{len(stem_files)} file")
        got += 1 if n_ok == len(stem_files) and stem_files else 0
    if got == len(missing):
        log(f"test-gt khôi phục XONG ({got} stem) → {GT_DIR}")
        return 0
    log("khôi phục một phần — xem ⚠ ở trên; có thể chạy lại (idempotent)")
    return 1


# --------------------------------------------------------------------------
# census từ submission.csv
# --------------------------------------------------------------------------
def census(csv_path: Path) -> dict:
    nodes = edges = 0
    out_deg: Counter = Counter()
    per_ds_nodes: Counter = Counter()
    with open(csv_path, newline="") as f:
        rd = _csv.DictReader(f)
        for row in rd:
            if row["row_type"] == "node":
                nodes += 1
                per_ds_nodes[row["dataset"]] += 1
            else:
                edges += 1
                out_deg[(row["dataset"], row["source_id"])] += 1
    forks = sum(1 for v in out_deg.values() if v >= 2)
    return {"nodes": nodes, "edges": edges, "forks": forks,
            "per_ds": dict(sorted(per_ds_nodes.items()))}


# --------------------------------------------------------------------------
# replica qua v12lab.py
# --------------------------------------------------------------------------
RE_TOTAL = re.compile(r"TOTAL adjEJ=([\d.]+) divJ=([\d.]+) REPLICA=([\d.]+)")
RE_DIVSTEM = re.compile(r"(\S+): adjEJ=[\d.]+ div=(\d+)/(\d+)/(\d+)")


def run_replica(csv_path: Path) -> dict:
    proc = subprocess.run(
        [sys.executable, str(V12LAB), "replica", str(csv_path)],
        text=True, capture_output=True, cwd=str(V12LAB.parent),
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    print(out)
    m = RE_TOTAL.search(out)
    if not m:
        raise SystemExit(f"[replica-gate] không parse được TOTAL từ v12lab replica (exit {proc.returncode})")
    div_by_stem = {}
    for mm in RE_DIVSTEM.finditer(out):
        div_by_stem[mm.group(1)] = (int(mm.group(2)), int(mm.group(3)), int(mm.group(4)))
    return {
        "adj": float(m.group(1)),
        "divJ": float(m.group(2)),
        "score": float(m.group(3)),
        "div_by_stem": div_by_stem,
    }


# --------------------------------------------------------------------------
# verdict
# --------------------------------------------------------------------------
def verdict(rep: dict, cen: dict, baseline_adj: float, margin: float) -> tuple[str, list[str]]:
    notes = []
    adj, divJ = rep["adj"], rep["divJ"]
    # division 05db cửa sổ (stem GT thật có 3 division)
    d05 = rep["div_by_stem"].get("6bba_05db0fb1", (0, 0, 0))
    tp, fp, fn = d05
    # census guards
    fork_ok = cen["forks"] >= 100
    node_ratio = cen["nodes"] / max(BASELINE["nodes"], 1)
    node_ok = 0.95 <= node_ratio <= 1.05
    if not fork_ok:
        notes.append(f"🔴 forks={cen['forks']} < 100 — nghi purge fork (L6: giết div TP) → HOLD")
    if not node_ok:
        notes.append(f"🔴 nodes {cen['nodes']} ngoài ±5% baseline {BASELINE['nodes']} → kiểm tra READMIT/GAPFILL trước khi nộp")
    if adj < baseline_adj - margin:
        verdict_ = "HOLD"
        notes.append(f"🔴 replica adjEJ {adj:.4f} < baseline {baseline_adj:.4f} − {margin} → KHÔNG nộp, nghiên cứu tiếp")
    elif adj > baseline_adj + margin:
        verdict_ = "SUBMIT-ELIGIBLE"
        notes.append(f"🟢 replica adjEJ {adj:.4f} > baseline {baseline_adj:.4f} + {margin}")
        if tp > 0:
            notes.append(f"🟢 division cửa sổ 05db: TP+{tp} (v11: 0/3)")
    else:
        if tp > 0 and fp <= tp + 2:
            verdict_ = "SUBMIT-ELIGIBLE"
            notes.append(f"🟡 replica adjEJ bẳng nhưng division 05db TP+{tp} (v11 0/3) — trục reparent/orphan có tín hiệu")
        else:
            verdict_ = "HOLD"
            notes.append(f"🟡 replica adjEJ bẳng ±{margin} và division không cải thiện (TP={tp}) — giống v11: dự kiến LB 0.947, NÊN GIỮ QUOTA, nghiên cứu tiếp")
    notes.append(
        "⚠ replica mù ngoài cửa sổ GT thưa 1.6% (receipt variant A: replica +0.0008, LB −0.036) — "
        "verdict là điều kiện CẦN, quyết định cuối vẫn là người chơi"
    )
    return verdict_, notes


# --------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pull", action="store_true", help="kéo output kernel rồi chấm")
    ap.add_argument("--kernel", default="biohub-ver12", help=f"slug kernel (mặc định biohub-ver12, owner {OWNER_DEFAULT})")
    ap.add_argument("--owner", default=OWNER_DEFAULT)
    ap.add_argument("--csv", type=Path, help="chấm CSV có sẵn (bỏ qua pull)")
    ap.add_argument("--restore-gt", action="store_true", help="chỉ khôi phục test-gt")
    ap.add_argument("--baseline", type=float, default=BASELINE["replica_adj"])
    ap.add_argument("--margin", type=float, default=0.0005)
    ap.add_argument("--out-dir", type=Path, default=RECOVERY / "gate-out")
    args = ap.parse_args()

    if args.restore_gt:
        return restore_gt()

    # GT phải có trước khi chấm
    missing_gt = [s for s in TEST_STEMS if not (GT_DIR / f"{s}.geff").exists()]
    if missing_gt:
        log(f"thiếu GT {missing_gt} → khôi phục tự động (cần token)")
        if not token_ready():
            raise SystemExit(
                "[replica-gate] thiếu test-gt VÀ thiếu token Kaggle.\n"
                "  1) lưu token:  python3 kaggle/api/ktool.py token --value KGAT_xxx\n"
                "  2) chạy lại:   python3 kaggle/api/replica-gate.py --restore-gt\n"
                "(sandbox reset 21/9 đã mất /home/z/v11-recovery/test-gt — khôi phục 1 lần)"
            )
        rc = restore_gt()
        if rc != 0:
            return rc

    csv_path = args.csv
    if csv_path is None:
        if not args.pull:
            ap.error("cần --pull hoặc --csv")
        if not token_ready():
            raise SystemExit("[replica-gate] --pull cần token Kaggle (ktool.py token --value …)")
        args.out_dir.mkdir(parents=True, exist_ok=True)
        log(f"kéo output kernel {args.owner}/{args.kernel} → {args.out_dir}")
        run_kaggle(["kernels", "output", f"{args.owner}/{args.kernel}", "-p", str(args.out_dir)])
        cand = args.out_dir / "submission.csv"
        if not cand.is_file():
            raise SystemExit(f"[replica-gate] không có submission.csv trong output — kernel chưa chạy xong?")
        csv_path = cand
    if not csv_path.is_file():
        raise SystemExit(f"[replica-gate] không tìm thấy {csv_path}")

    log(f"chấm replica: {csv_path}")
    rep = run_replica(csv_path)
    cen = census(csv_path)

    print("\n" + "=" * 70)
    print(f"CỔNG REPLICA PRE-SUBMIT — {csv_path.name}")
    print("=" * 70)
    print(f"  replica : adjEJ={rep['adj']:.4f}  divJ={rep['divJ']:.4f}  score={rep['score']:.4f}")
    print(f"  baseline: adjEJ={args.baseline:.4f}  (v11 ref 56403231 — LB 0.947)")
    print(f"  census  : nodes={cen['nodes']:,} edges={cen['edges']:,} forks={cen['forks']}"
          f"  (baseline {BASELINE['nodes']:,}/{BASELINE['edges']:,}/{BASELINE['forks']})")
    for ds, n in cen["per_ds"].items():
        print(f"    - {ds}: {n:,} nodes")
    d05 = rep["div_by_stem"].get("6bba_05db0fb1", (0, 0, 0))
    print(f"  division cửa sổ 05db: TP/FP/FN = {d05[0]}/{d05[1]}/{d05[2]}  ({BASELINE['div_window']})")
    v, notes = verdict(rep, cen, args.baseline, args.margin)
    print(f"\n  VERDICT: {v}")
    for n in notes:
        print(f"    {n}")
    print()
    if v == "SUBMIT-ELIGIBLE":
        print("  → tiếp theo (khi được lệnh submit): python3 kaggle/api/submit-v12.py …")
    else:
        print("  → giữ quota, nghiên cứu tiếp (đúng kỷ luật user 21/9: không tốt hơn = không nộp)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
