#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v10_trial.py — quản lý TÀI KHOẢN KAGGLE THỬ NGHIỆM cho v10-lab (multi-account T4x2).

Mỗi tài khoản thử nghiệm (secondary) có quota GPU riêng 30h/tuần — chạy trial các
version v10 để so sánh với baseline, KHÔNG đụng quota của tài khoản chính
(vietnguyen130593 = Mr. Architect — chỉ dùng để submit bài thi).

Kiến trúc (mọi thứ nằm dưới namespace tài khoản phụ, private):
  <acct>/biohub-v10-lab-runners      — 4 runner đã PATCH token+slug cho acct
  <acct>/biohub-v10-lab-filelist     — copy từ chính (271KB, cho nếp C)
  <acct>/biohub-v6-heldout-preds     — copy từ chính (1.2MB, dataset support riêng tư duy nhất)
  [<acct>/biohub-v10-stems8]         — copy 3.4GB (tuỳ chọn --with-stems8)
  <acct>/biohub-v10-checkpoints      — watchdog đẩy checkpoint khi trial chạy
  <acct>/biohub-v10-rawgraphs        — watchdog đẩy raw graphs cache
  kernel <acct>/v10-lab-trial        — T4x2, internet ON, gắn competition + runners

Lệnh:
  register <name> <username> (--token KGAT_... | --token-file F)
  init     <name> [--with-stems8]     # tạo/copy các dataset ở trên
  launch   <name> [--runners-dir DIR] [--slug v10-lab-trial]
  status   <name> [--slug v10-lab-trial]
  collect  <name> [--out DIR] [--slug v10-lab-trial]
  compare  [PATH ...] [--baseline F]  # so validator/grid với ver8-baseline
  list
"""
import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent
MAIN = "vietnguyen130593"
COMP = "biohub-cell-tracking-during-development"
DEFAULT_SLUG = "v10-lab-trial"
TOKENS = BASE / "tokens"
ACCOUNTS = BASE / "accounts.json"
RESULTS = BASE / "results"
KERNELS = BASE / "trial-kernels"
TEMPLATE = BASE / "kernel_trial_template.py"
RUNNER_FILES = ["v10_cell2_run.py", "v10_cell3_run.py", "repair_deps.py", "v10_ckpt_watchdog.py"]
COPY_Small = ["biohub-v10-lab-runners", "biohub-v10-lab-filelist", "biohub-v6-heldout-preds"]
DS_EMPTY = ["biohub-v10-checkpoints", "biohub-v10-rawgraphs"]
VER8_BASELINE = Path("/home/z/my-project/kaggle/api/output/ver8-v1/validator_results.csv")


def kaggle_bin():
    for c in [shutil.which("kaggle"), str(Path.home() / ".venv/bin/kaggle")]:
        if c and Path(c).exists():
            return [c]
    return [sys.executable, "-m", "kaggle"]


KB = kaggle_bin()


def kaggle(args, token=None, timeout=7200):
    env = os.environ.copy()
    env["PATH"] = str(Path.home() / ".venv/bin") + ":" + env.get("PATH", "")
    if token:
        env["KAGGLE_API_TOKEN"] = token
    return subprocess.run(KB + args, capture_output=True, text=True, timeout=timeout, env=env)


def main_token():
    return (Path.home() / ".kaggle/access_token").read_text().strip()


def load_accounts():
    data = json.loads(ACCOUNTS.read_text()) if ACCOUNTS.exists() else {"accounts": {}}
    return data["accounts"]


def save_accounts(accts):
    ACCOUNTS.write_text(json.dumps({"accounts": accts}, indent=2, ensure_ascii=False) + "\n")


def acct_info(name):
    accts = load_accounts()
    if name not in accts:
        sys.exit("Không có account '%s' trong accounts.json. Chạy: register %s <username> --token KGAT_..." % (name, name))
    a = accts[name]
    tok_file = Path(a["token_file"])
    if not tok_file.exists():
        sys.exit("Thiếu file token %s — register lại." % tok_file)
    return a["username"], tok_file.read_text().strip()


def sh(args, **kw):
    return subprocess.run(args, capture_output=True, text=True, **kw)


def ds_meta(stage: Path, owner: str, slug: str, private=True):
    stage.mkdir(parents=True, exist_ok=True)
    (stage / "dataset-metadata.json").write_text(json.dumps({
        "title": slug, "id": "%s/%s" % (owner, slug), "private": private,
        "licenses": [{"name": "CC0-1.0"}],
    }, indent=1))


def ds_exists(owner, slug, token):
    return kaggle(["datasets", "status", "%s/%s" % (owner, slug)], token, timeout=300).returncode == 0


def copy_dataset(slug, owner_b, token_b, patch=None):
    """Copy dataset MAIN/slug → owner_b/slug (giải zip, patch text nếu cần, tạo)."""
    if ds_exists(owner_b, slug, token_b):
        print("  [skip] %s/%s đã tồn tại" % (owner_b, slug))
        return True
    tmp = Path(tempfile.mkdtemp(prefix="v10copy_%s_" % slug))
    r = kaggle(["datasets", "download", "%s/%s" % (MAIN, slug), "-p", str(tmp), "--unzip", "-q"])
    if r.returncode != 0:
        print("  [LỖI] tải %s/%s: %s" % (MAIN, slug, ((r.stdout or "") + (r.stderr or ""))[-300:]))
        return False
    for z in tmp.glob("*.zip"):
        sh(["unzip", "-o", "-q", str(z), "-d", str(tmp)])
        z.unlink()
    stage = tmp / "stage"
    ds_meta(stage, owner_b, slug)
    n = 0
    for p in tmp.iterdir():
        if p.name in ("stage", "dataset-metadata.json") or p.name.endswith(".zip"):
            continue
        if patch and p.is_file():
            p.write_text(patch(p.read_text(errors="replace")))
        dest = stage / p.name
        if p.is_dir():
            shutil.copytree(p, dest)
        else:
            shutil.copy2(p, dest)
        n += 1
    r2 = kaggle(["datasets", "create", "-p", str(stage)], token_b, timeout=3600)
    ok = r2.returncode == 0
    print("  [%s] create %s/%s (%d mục) :: %s" % ("OK" if ok else "LỖI", owner_b, slug, n,
          ((r2.stdout or "") + (r2.stderr or "")).strip()[:200]))
    shutil.rmtree(tmp, ignore_errors=True)
    return ok


def cmd_register(args):
    name, username = args[0], args[1]
    tok = None
    if "--token" in args:
        tok = args[args.index("--token") + 1]
    elif "--token-file" in args:
        tok = Path(args[args.index("--token-file") + 1]).read_text().strip()
    if not tok:
        tok = input("Dán token KGAT_... của %s: ").strip()
    if not tok.startswith("KGAT_"):
        sys.exit("Token phải bắt đầu bằng KGAT_...")
    TOKENS.mkdir(parents=True, exist_ok=True)
    tf = TOKENS / ("%s.kgat" % name)
    tf.write_text(tok + "\n")
    tf.chmod(0o600)
    r = kaggle(["datasets", "list", "--mine"], token, timeout=120)
    if r.returncode != 0:
        print("CẢNH BÁO: token chưa verify được :: %s" % ((r.stdout or "") + (r.stderr or ""))[-300:])
    else:
        print("Token OK — kaggle phản hồi (đã xác thực).")
    accts = load_accounts()
    accts[name] = {"username": username, "token_file": str(tf), "registered": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    save_accounts(accts)
    print("Đã register account '%s' → @%s" % (name, username))


def cmd_init(args):
    name = args[0]
    user, token = acct_info(name)
    print("== INIT %s (@%s) ==" % (name, user))
    for slug in COPY_Small:
        print("· copy %s/%s → %s/%s" % (MAIN, slug, user, slug))
        copy_dataset(slug, user, token)
    if "--with-stems8" in args:
        print("· copy %s/biohub-v10-stems8 (3.4GB — vài phút)..." % MAIN)
        copy_dataset("biohub-v10-stems8", user, token)
    for slug in DS_EMPTY:
        if ds_exists(user, slug, token):
            print("  [skip] %s/%s đã có" % (user, slug))
            continue
        tmp = Path(tempfile.mkdtemp(prefix="v10empty_"))
        ds_meta(tmp, user, slug)
        (tmp / "README.txt").write_text("bootstrap %s\n" % time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
        r = kaggle(["datasets", "create", "-p", str(tmp)], token, timeout=600)
        print("  [%s] create %s/%s (placeholder)" % ("OK" if r.returncode == 0 else "LỖI", user, slug))
        shutil.rmtree(tmp, ignore_errors=True)
    print("""
CHECKLIST trước khi launch (mỗi tài khoản, làm 1 LẦN trên web):
  1) ĐãAccept competition rules: kaggle.com/competitions/%s/rules
  2) Tài khoản đã phone-verified (điều kiện bật GPU)
  3) GPU quota còn (mỗi trial ~3-5h trên 30h/tuần)
""" % COMP)


def patch_runners(text, user, token):
    """Rewrite token + owner-namespace cho runner copy của tài khoản phụ."""
    return text.replace(main_token(), token).replace("%s/" % MAIN, "%s/" % user)


def fetch_runners(runners_dir=None):
    """Nguồn runners: --runners-dir HOẶC tải bản mới nhất của tài khoản chính."""
    if runners_dir:
        d = Path(runners_dir)
        assert (d / "v10_cell2_run.py").is_file(), "runners-dir thiếu v10_cell2_run.py"
        return d
    tmp = Path(tempfile.mkdtemp(prefix="v10runners_"))
    r = kaggle(["datasets", "download", "%s/biohub-v10-lab-runners" % MAIN, "-p", str(tmp), "--unzip", "-q"])
    if r.returncode != 0:
        sys.exit("Không tải được runners từ tài khoản chính: %s" % ((r.stdout or "") + (r.stderr or ""))[-300:])
    for z in tmp.glob("*.zip"):
        sh(["unzip", "-o", "-q", str(z), "-d", str(tmp)])
        z.unlink()
    return tmp


def cmd_launch(args):
    name = args[0]
    slug = DEFAULT_SLUG
    if "--slug" in args:
        slug = args[args.index("--slug") + 1]
    user, token = acct_info(name)
    runners_dir = None
    if "--runners-dir" in args:
        runners_dir = args[args.index("--runners-dir") + 1]

    src = fetch_runners(runners_dir)
    # 1) đẩy runners ĐÃ PATCH lên dataset của tài khoản phụ (phiên bản mới)
    stage = Path(tempfile.mkdtemp(prefix="v10pushrunners_"))
    ds_meta(stage, user, "biohub-v10-lab-runners")
    for f in RUNNER_FILES:
        (stage / f).write_text(patch_runners((src / f).read_text(errors="replace"), user, token))
    if not ds_exists(user, "biohub-v10-lab-runners", token):
        r = kaggle(["datasets", "create", "-p", str(stage)], token, timeout=600)
    else:
        r = kaggle(["datasets", "version", "-p", str(stage), "-m",
                    "trial %s" % time.strftime("%Y%m%d-%H%M")], token, timeout=3600)
    if r.returncode != 0:
        sys.exit("Đẩy runners lên %s thất bại: %s" % (user, ((r.stdout or "") + (r.stderr or ""))[-300:]))
    print("[OK] runners (patched) → %s/biohub-v10-lab-runners" % user)

    # 2) render kernel dir
    kdir = KERNELS / name
    kdir.mkdir(parents=True, exist_ok=True)
    tpl = TEMPLATE.read_text()
    (kdir / "kernel.py").write_text(tpl.replace("{{B_USER}}", user).replace("{{B_TOKEN}}", token))
    (kdir / "kernel-metadata.json").write_text(json.dumps({
        "id": "%s/%s" % (user, slug),
        "title": slug,
        "code_file": "kernel.py",
        "language": "python",
        "kernel_type": "script",
        "is_private": True,
        "enable_gpu": True,
        "enable_internet": True,
        "dataset_sources": ["%s/biohub-v10-lab-runners" % user],
        "competition_sources": [COMP],
    }, indent=2) + "\n")

    # 3) push kernel
    r = kaggle(["kernels", "push", "-p", str(kdir)], token, timeout=600)
    print(((r.stdout or "") + (r.stderr or "")).strip()[:500])
    if r.returncode == 0:
        print("[OK] kernel %s/%s đã push — theo dõi: https://www.kaggle.com/code/%s/%s" % (user, slug, user, slug))
        print("     Trong sandbox:  python3 v10_trial.py status %s" % name)


def cmd_status(args):
    name = args[0]
    slug = args[args.index("--slug") + 1] if "--slug" in args else DEFAULT_SLUG
    user, token = acct_info(name)
    print("== STATUS %s (@%s) ==" % (name, user))
    r = kaggle(["kernels", "status", "%s/%s" % (user, slug)], token, timeout=120)
    print("kernel:", ((r.stdout or "") + (r.stderr or "")).strip())
    for ds in ["biohub-v10-checkpoints", "biohub-v10-rawgraphs"]:
        r = kaggle(["datasets", "files", "%s/%s" % (user, ds)], token, timeout=120)
        print("--- %s ---" % ds)
        print(((r.stdout or "") + (r.stderr or "")).strip()[:800])


def cmd_collect(args):
    name = args[0]
    slug = args[args.index("--slug") + 1] if "--slug" in args else DEFAULT_SLUG
    user, token = acct_info(name)
    out = RESULTS / name / time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    if "--out" in args:
        out = Path(args[args.index("--out") + 1])
    out.mkdir(parents=True, exist_ok=True)
    print("== COLLECT %s → %s ==" % (name, out))
    r = kaggle(["kernels", "output", "%s/%s" % (user, slug), "-p", str(out / "kernel_output")], token, timeout=3600)
    print("kernel output:", "OK" if r.returncode == 0 else ((r.stdout or "") + (r.stderr or ""))[-200:])
    for ds in ["biohub-v10-checkpoints", "biohub-v10-rawgraphs"]:
        r = kaggle(["datasets", "download", "%s/%s" % (user, ds), "-p", str(out / ds), "--unzip", "-q"], token, timeout=3600)
        print("dataset %s:" % ds, "OK" if r.returncode == 0 else ((r.stdout or "") + (r.stderr or ""))[-200:])
    print("\nSo sánh:\n  python3 %s compare %s" % (Path(__file__).name, out))


def load_validator(path):
    """→ ({stem: adjEJ}, {stem: weight}) cho config=base."""
    adj, w = {}, {}
    with open(path) as f:
        for row in csv.DictReader(f):
            if (row.get("config") or "base") != "base":
                continue
            adj[row["stem"]] = float(row["adjusted_edge_jaccard"])
            w[row["stem"]] = float(row["weight"])
    return adj, w


def weighted(adj, w):
    stems = [s for s in adj if s in w]
    tw = sum(w[s] for s in stems)
    return (sum(adj[s] * w[s] for s in stems) / tw) if tw else 0.0


def cmd_compare(args):
    paths = [Path(a) for a in args if not a.startswith("--")]
    baseline = VER8_BASELINE
    if "--baseline" in args:
        baseline = Path(args[args.index("--baseline") + 1])
    if not paths:
        cands = sorted(RESULTS.glob("*/*")) + [Path("/tmp/ckpt")]
        paths = [p for p in cands if (p / "validator_results.csv").exists()][-3:]
    if not paths:
        sys.exit("Không tìm thấy kết quả nào. Chạy collect trước, hoặc chỉ định đường dẫn.")
    badj, bw = load_validator(baseline)
    bwt = weighted(badj, bw)
    print("BASELINE  ver8-v1 (base): adjEJ trọng số = %.6f  (%d stems)\n" % (bwt, len(badj)))
    for p in paths:
        vp = p / "validator_results.csv"
        if not vp.exists():
            for sub in ["kernel_output", "ckpt"]:
                if (p / sub / "validator_results.csv").exists():
                    vp = p / sub / "validator_results.csv"
                    break
        if not vp.exists():
            print("== %s: không có validator_results.csv — bỏ qua" % p)
            continue
        adj, w = load_validator(vp)
        wt = weighted(adj, w)
        print("== %s ==" % p)
        print("  %-20s %10s %10s %10s" % ("stem", "ver8-base", "trial-base", "delta"))
        for s in sorted(badj):
            if s in adj:
                print("  %-20s %10.6f %10.6f %+10.6f%s" % (s, badj[s], adj[s], adj[s] - badj[s],
                      "  ◀" if adj[s] - badj[s] >= 0.0005 else ""))
        print("  %-20s %10.6f %10.6f %+10.6f   (weighted)" % ("TỔNG", bwt, wt, wt - bwt))
        # grid report nếu có
        rp = p / "v10_lab_report.json"
        for sub in ["kernel_output", "ckpt"]:
            if (p / sub / "v10_lab_report.json").exists():
                rp = p / sub / "v10_lab_report.json"
        if rp.exists():
            rep = json.loads(rp.read_text())
            rows = []
            for label, c in rep.get("configs", {}).items():
                if c.get("summary"):
                    rows.append((label, c["summary"].get("adjusted_edge_jaccard", 0.0),
                                 (c.get("deltas_vs_ref") or {}).get("adjusted_edge_jaccard", 0.0),
                                 c["summary"].get("proxy_score", 0.0)))
            rows.sort(key=lambda x: -x[1])
            print("  --- grid %d configs (xếp theo adjEJ) ---" % len(rows))
            for label, ej, d, proxy in rows:
                print("  %-10s adjEJ=%.6f  Δref=%+.6f  proxy=%.6f" % (label, ej, d, proxy))
        print()


def cmd_list(_):
    accts = load_accounts()
    if not accts:
        print("(chưa có account nào — chạy: register <name> <username> --token KGAT_...)")
    for n, a in accts.items():
        print("%-12s @%s" % (n, a["username"]))
    print("\nKernel chính (tài khoản chính, KHÔNG phải trial): %s/v10-lab-gpu-t4" % MAIN)


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return
    cmd, rest = args[0], args[1:]
    {"register": cmd_register, "init": cmd_init, "launch": cmd_launch,
     "status": cmd_status, "collect": cmd_collect, "compare": cmd_compare,
     "list": cmd_list}.get(cmd, lambda a: print(__doc__))(rest)


if __name__ == "__main__":
    main()
