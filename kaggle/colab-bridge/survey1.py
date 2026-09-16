# -*- coding: utf-8 -*-
# Survey nhanh runtime Colab qua bridge
import os, subprocess, sys, json

print("=== CWD:", os.getcwd())
print("=== PYTHON:", sys.version.split()[0])

# Disk
try:
    print("=== DISK:")
    print(subprocess.run(["df", "-h", "/content"], capture_output=True, text=True).stdout.strip())
except Exception as e:
    print("disk err:", e)

# GPU
try:
    import torch
    print("=== GPU avail:", torch.cuda.is_available())
    if torch.cuda.is_available():
        print("    name:", torch.cuda.get_device_name(0), "| mem:", round(torch.cuda.get_device_properties(0).total_memory / 1e9, 1), "GB")
except Exception as e:
    print("torch err:", e)

# Env quan trọng
envs = {k: v for k, v in os.environ.items() if k.startswith("V10") or k.startswith("KAGGLE") or k.startswith("BIOHUB")}
print("=== ENV:", json.dumps(envs, indent=1) if envs else "(khong co)")

# Cac thu muc kaggle
for p in ["/content", "/content/kaggle", "/content/kaggle/input", "/content/kaggle/working",
          "/kaggle", "/kaggle/input", "/kaggle/working"]:
    if os.path.isdir(p):
        try:
            items = os.listdir(p)
            w = os.access(p, os.W_OK)
            print("=== DIR %s (writable=%s, %d items): %s" % (p, w, len(items), items[:25]))
        except Exception as e:
            print("=== DIR %s err: %s" % (p, e))
    else:
        print("=== DIR %s: KHONG TON TAI" % p)

# kaggle CLI
for cmd in ([sys.executable, "-m", "kaggle", "--version"], ["kaggle", "--version"]):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        print("=== KAGGLE CMD %r -> rc=%d out=%r err=%r" % (cmd[:2], r.returncode, r.stdout.strip()[:60], r.stderr.strip()[:80]))
        if r.returncode == 0:
            break
    except Exception as e:
        print("=== KAGGLE CMD %r err: %s" % (cmd[:2], e))

# file da tai (dung luong tung dataset)
root = "/content/kaggle/input"
if os.path.isdir(root):
    for ds in sorted(os.listdir(root)):
        dsp = os.path.join(root, ds)
        if os.path.isdir(dsp):
            total = 0
            nfile = 0
            for dirpath, dirnames, filenames in os.walk(dsp):
                for f in filenames:
                    try:
                        total += os.path.getsize(os.path.join(dirpath, f))
                        nfile += 1
                    except OSError:
                        pass
            print("=== DS %-55s %6d files %10.2f MB" % (ds, nfile, total / 1e6))

# working dir neu co
wd = "/content/kaggle/working"
if os.path.isdir(wd):
    print("=== WORKING items:", os.listdir(wd)[:30])
