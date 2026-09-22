#!/usr/bin/env python3
"""submit-v13.py — Nộp kernel ver-13 vào competition biohub (notebooks-only).

Tạo theo submit-v12.py (battle-tested ref 56442903): làm TRỌN BỘ cổng PRE-SUBMIT
(GPU-WASTE-PREVENTION.md §4) TRƯỚC khi gọi API:

  python3 submit-v13.py [--version N] [--message "..."] [--no-verify] [--dry-run]

Nếu --version bỏ qua: tự đọc state.json của lần push --ver 13 gần nhất.
File kiểm tra: kaggle/api/output/latest/submission.csv (tải về bởi
`python3 ktool.py watch --ver 13` hoặc `output --ver 13`).

Cổng kiểm (chạy trước submit, bỏ qua bằng --no-verify):
  [INT]  mọi cột số là số nguyên (bài học L5: variant A fail format "24.0")
  [DAG]  cạnh chỉ đi t→t+1, không cycle, node_id tham chiếu tồn tại (L3)
  [CENS] census per-dataset (L12): node/edge/fork — đối chiếu v11 (0.947) và
         v12.1 (0.946): v13 kỳ vọng ~122.760n/~118.450e/160-175f (P4 divwide
         thêm fork phim thưa + P3 leaf-prune bớt ~70 cạnh + P1 bỏ 23 fork 05db)
  [TAG]  run_stats.csv (nếu có): EXPERIMENT_TAG v13 + counters P1-P4
         (leaf_prune_nodes/edges — receipt port amanatar)

Luật ĐỨNG (V11-POSTDEPLOY-REVIEW): KHÔNG tự nộp khi chưa có lệnh trực tiếp user.
Cuộc thi chỉ nhận code submission từ kernel version — kagglesdk
CompetitionApiClient.create_code_submission.
LƯU Ý: sandbox mới cần `pip install kagglesdk` + token tại ~/.kaggle/access_token.
"""
import argparse
import csv
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STATE = ROOT / "state.json"
OUTDIR = ROOT / "output" / "latest"
COMPETITION = "biohub-cell-tracking-during-development"
KERNEL_OWNER = "vietnguyen130593"
KERNEL_SLUG = "biohub-ver13"
EXPECTED_TAG_PREFIX = "secondary_deepcenter_tta_0947_reparent_hoct_v13_"

DEFAULT_MESSAGE = (
    "ver-13 = v12.1-knockout (ref 56442903, LB 0.946) + adjEJ focus P1-P4 "
    "(V13-ADJEJ-RESEARCH): P1 revert SAFE_DIV_DIVERGE_UM -2.0->0.5 (dung grid v11 "
    "mn_p85_div05) + SAFE_DIV_ORPHAN_ADOPT 0 (tat nguon +23 fork 05db) -> safe-div "
    "gate tro ve hanh xu v11 (baseline 0.947); P2 MOTION_RELINK_VELOCITY_WEIGHT "
    "0.5->0.25 (sweep amanatar +0.0014 adj — lever lon nhat chua dung); P3 "
    "LEAF_PRUNE_MIN_EDGE_PROB 0.30 (port nguyen van amanatar v4 ~60 dong: cat node "
    "la cuoi track canh vao yeu, mien tru con division); P4 divwide SAFE_DIV_MAX "
    "9->11 SISTER 14->16 EXISTING_CHILD 10->12 + DC 0.2->0.15 (recall division "
    "khong ton adj, giu divergence nghiem ngat). Fork policy: KHONG purge (L6). "
    "Base ver-10/ver-11: LB 0.947."
)

# Census đối chiếu — L12: theo dataset, không gộp
V11_CENSUS = {"nodes": 122787, "edges": 118332, "forks": 144}     # ref 56403231 LB 0.947
V121_CENSUS = {"nodes": 122808, "edges": 118393, "forks": 184}    # ref 56442903 LB 0.946


def fail_verify(msg: str) -> None:
    print(f"  [FAIL] {msg}")
    print("→ CHẶN submit. Sửa nguyên nhân rồi chạy lại (hoặc --dry-run để chỉ xem).")
    raise SystemExit(1)


def verify_submission() -> dict:
    sub = OUTDIR / "submission.csv"
    if not sub.is_file():
        fail_verify(f"không tìm thấy {sub} — chạy `python3 ktool.py output --ver 13` trước")
    print(f"== PRE-SUBMIT VERIFY: {sub} ==")

    nodes: dict[str, dict[int, int]] = defaultdict(dict)      # dataset -> node_id -> t
    edges: list[tuple[str, int, int]] = []
    bad_int = 0
    bad_ref = 0
    bad_step = 0
    n_rows = 0
    with sub.open(newline="") as fh:
        reader = csv.DictReader(fh)
        cols = set(reader.fieldnames or [])
        need = {"dataset", "row_type", "node_id", "t", "z", "y", "x", "source_id", "target_id"}
        if not need.issubset(cols):
            fail_verify(f"thiếu cột: {sorted(need - cols)} (có: {sorted(cols)})")
        for row in reader:
            n_rows += 1
            try:
                node_id = int(row["node_id"]); t = int(row["t"])
                z = int(row["z"]); y = int(row["y"]); x = int(row["x"])
                src = int(row["source_id"]); tgt = int(row["target_id"])
                if any(str(v) != str(int(v)) for v in (row["node_id"], row["t"], row["z"], row["y"], row["x"])):
                    raise ValueError
            except (TypeError, ValueError):
                bad_int += 1
                continue
            ds = row["dataset"]
            if row["row_type"] == "node":
                nodes[ds][node_id] = t
            elif row["row_type"] == "edge":
                edges.append((ds, src, tgt))
    if bad_int:
        fail_verify(f"{bad_int}/{n_rows} dòng không phải số nguyên (L5 — sẽ bị fail format)")

    # DAG: cạnh nối node tồn tại + t tăng đúng 1
    for ds, src, tgt in edges:
        tn = nodes[ds].get(src); tt = nodes[ds].get(tgt)
        if tn is None or tt is None:
            bad_ref += 1
        elif tt != tn + 1:
            bad_step += 1
    if bad_ref or bad_step:
        fail_verify(f"DAG vi phạm: {bad_ref} cạnh tham chiếu node không tồn tại, {bad_step} cạnh không t→t+1")

    # Census per dataset (L12)
    out_by_ds: dict[str, defaultdict] = defaultdict(lambda: defaultdict(int))
    for ds, src, _tgt in edges:
        out_by_ds[ds][src] += 1
    total_nodes = sum(len(v) for v in nodes.values())
    total_edges = len(edges)
    total_forks = sum(1 for ds in out_by_ds for src, deg in out_by_ds[ds].items() if deg == 2)
    print(f"  [INT ] PASS — {n_rows} dòng toàn số nguyên")
    print(f"  [DAG ] PASS — {total_edges} cạnh đều t→t+1, node tham chiếu đủ")
    print(f"  [CENS] theo dataset (L12):")
    for ds in sorted(nodes):
        forks = sum(1 for src, deg in out_by_ds[ds].items() if deg == 2)
        print(f"         {ds}: {len(nodes[ds])} nodes, {sum(out_by_ds[ds].values())} edges, {forks} forks")
    print(f"  [CENS] TỔNG: {total_nodes} nodes / {total_edges} edges / {total_forks} forks "
          f"(v11: {V11_CENSUS['nodes']}n/{V11_CENSUS['edges']}e/{V11_CENSUS['forks']}f · "
          f"v12.1: {V121_CENSUS['nodes']}n/{V121_CENSUS['edges']}e/{V121_CENSUS['forks']}f)")
    if total_nodes < V11_CENSUS["nodes"] * 0.98:
        fail_verify(f"node tụt {total_nodes} < 98% ver-11 ({V11_CENSUS['nodes']}) — nghi purge/rò rỉ, KIỂM TRA thủ công")
    if total_forks < V11_CENSUS["forks"]:
        print(f"  [CENS] ⚠ forks {total_forks} < ver-11 {V11_CENSUS['forks']} — chấp nhận nếu do leaf-prune/gate, đối chiếu replica trước nộp")
    if total_forks > V121_CENSUS["forks"] + 40:
        print(f"  [CENS] ⚠ forks {total_forks} > v12.1+40 ({V121_CENSUS['forks'] + 40}) — P4 divwide nới quá tay? đối chiếu replica-gate")

    # run_stats tag + counters P1-P4 (nếu có)
    stats_csv = OUTDIR / "run_stats.csv"
    if stats_csv.is_file():
        try:
            rows = list(csv.DictReader(stats_csv.open(newline="")))
            tag = rows[-1].get("experiment_tag") or rows[-1].get("EXPERIMENT_TAG") or "" if rows else ""
            if tag and not tag.startswith(EXPECTED_TAG_PREFIX):
                fail_verify(f"run_stats tag {tag!r} không phải v13 (cần tiền tố {EXPECTED_TAG_PREFIX!r})")
            if tag:
                print(f"  [TAG ] PASS — {tag}")
            for key in ("leaf_prune_nodes", "leaf_prune_edges",
                        "safe_divisions_added", "safe_division_divergence_rejected",
                        "safe_division_orphan_exempted", "safe_division_orphan_adopted",
                        "deepcenter_safe_div_rejected", "readmitted_nodes", "gapfill_added_nodes"):
                val = rows[-1].get(key) if rows else None
                if val is not None:
                    print(f"         {key} = {val}")
        except Exception as exc:
            print(f"  [TAG ] ⚠ đọc run_stats lỗi ({exc}) — bỏ qua (không chặn)")
    else:
        print("  [TAG ] run_stats.csv không có trong output — bỏ qua (không chặn)")
    return {"rows": n_rows, "nodes": total_nodes, "edges": total_edges, "forks": total_forks}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--version", type=int, help="kernel version (mặc định: state.json)")
    parser.add_argument("--message", default=DEFAULT_MESSAGE)
    parser.add_argument("--no-verify", action="store_true", help="bỏ cổng PRE-SUBMIT (không khuyến khích)")
    parser.add_argument("--dry-run", action="store_true", help="chỉ chạy verify + in thông tin submit, không nộp")
    args = parser.parse_args()

    version = args.version
    if version is None:
        state = json.loads(STATE.read_text()) if STATE.is_file() else {}
        version = state.get("version")
        if version is None or state.get("ref") != f"{KERNEL_OWNER}/{KERNEL_SLUG}":
            sys.exit("Không biết version — chạy `python3 ktool.py push --ver 13` trước hoặc dùng --version N.")

    if not args.no_verify:
        verify_submission()
    else:
        print("== PRE-SUBMIT VERIFY BỎ QUA (--no-verify) ==")

    if args.dry_run:
        print(f"\n[DRY-RUN] sẽ nộp {KERNEL_OWNER}/{KERNEL_SLUG} version {version} "
              f"— chạy lại không --dry-run để nộp thật (cần lệnh trực tiếp của user).")
        return 0

    token_file = Path.home() / ".kaggle" / "access_token"
    if token_file.is_file():
        os.environ.setdefault("KAGGLE_API_TOKEN", token_file.read_text().strip())
        os.environ.setdefault("KAGGLE_CONFIG_DIR", str(token_file.parent))

    try:
        from kagglesdk import KaggleClient
        from kagglesdk.competitions.types.competition_api_service import ApiCreateCodeSubmissionRequest
    except ImportError:
        sys.exit("THIẾU kagglesdk — cài lại: pip install kagglesdk (sandbox mới mất package), "
                 "hoặc nộp qua `python3 ktool.py submit --ver 13`.")

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
