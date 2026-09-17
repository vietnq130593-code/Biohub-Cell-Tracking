# repair_deps.py — vá môi trường Python 3.13 cho monolith v10lab (chạy trên Colab VM)
# (tái tạo từ phiên f37bae — test PROVEN: 13/13 import OK)
import subprocess
import sys

LOG = open("/content/repair.log", "w")

def log(msg):
    print(msg, flush=True)
    LOG.write(msg + "\n")
    LOG.flush()

def pip(*args):
    r = subprocess.run([sys.executable, "-m", "pip", "install", *args],
                       capture_output=True, text=True, timeout=900)
    log("PIP %s → rc=%d %s" % (" ".join(args), r.returncode, (r.stderr or r.stdout or "").strip()[-250:]))
    return r.returncode

log("=== PYTHON " + sys.version)

# 1) từng gói rời (lệnh nguyên khối chết atomically ở google-crc32c)
for pkg in ["msgspec", "pydantic-core==2.46.5", "tracksdata", "zarr>=3.0.10,<4",
            "pyscipopt", "geff", "polars", "blosc2", "imagecodecs", "pyarrow",
            "rustworkx", "ilpy", "dask", "google-crc32c"]:
    pip(pkg)

# 2) verify import
ok, bad = [], []
for m in ["pydantic", "zarr", "msgspec", "geff", "tracksdata", "pyscipopt", "ilpy",
          "polars", "blosc2", "dask", "imagecodecs", "pyarrow", "rustworkx"]:
    try:
        __import__(m)
        ok.append(m)
    except Exception as e:
        bad.append("%s: %s %s" % (m, type(e).__name__, str(e)[:100]))
log("IMPORT OK: " + ", ".join(ok))
log("IMPORT FAIL: " + ("; ".join(bad) if bad else "(khong con)"))
log("REPAIR_DONE")
