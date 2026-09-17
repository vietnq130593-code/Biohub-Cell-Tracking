# [v10-lab-colab S2] SETUP — token Kaggle + 9 dataset + 8 stems train competition
import os
import sys
import io
import csv
import json
import time
import shutil
import zipfile
import tempfile
import subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# [bridge-adapt] headless: khong doi popup Drive auth (V10_DRIVE=off); moi lan chay deu qua channel agent
import os as _os_ba
_os_ba.environ.setdefault("V10_DRIVE", "off")
_os_ba.environ.setdefault("V10_HEADLESS", "1")

# --- token Kaggle KGAT_... — đã nhúng sẵn; nếu có Colab Secret KAGGLE_API_TOKEN thì ưu tiên secret ---
KAGGLE_API_TOKEN = "KGAT_14164511bf6b0ba6b14ed9050ffdea66"
try:
    from google.colab import userdata  # noqa: E402
    _sec = (userdata.get("KAGGLE_API_TOKEN") or "").strip()
    if _sec.startswith("KGAT_"):
        KAGGLE_API_TOKEN = _sec
        print("[v10-lab-setup] token lấy từ Colab Secrets (ưu tiên secret)")
    else:
        print("[v10-lab-setup] dùng token nhúng sẵn trong cell")
except Exception:
    print("[v10-lab-setup] dùng token nhúng sẵn trong cell (không dùng Colab Secrets)")
assert KAGGLE_API_TOKEN and KAGGLE_API_TOKEN.startswith("KGAT_"), (
    "Chưa có token Kaggle hợp lệ! Dán token KGAT_... vào biến KAGGLE_API_TOKEN "
    "ở đầu cell này, hoặc tạo Colab Secret tên KAGGLE_API_TOKEN rồi chạy lại.")
os.environ["KAGGLE_API_TOKEN"] = KAGGLE_API_TOKEN
# [v10-lab-setup] Colab preinstall kaggle 2.0.x THIẾU __main__.py (lỗi "No module named kaggle.__main__")
# → phải --upgrade lên >=2.2 (pip thường thì thấy 2.0.2 "đã thoả" và bỏ qua — KHÔNG nâng cấp).
# [bridge-adapt] %pip -> subprocess (chay ngoai kernel notebook)
_r = subprocess.run([sys.executable, "-m", "pip", "install", "-q", "--upgrade", "kaggle>=2.2"],
                     capture_output=True, text=True, timeout=600)
print("[v10-lab-setup] pip upgrade kaggle rc=%d %s" % (_r.returncode, (_r.stdout or _r.stderr).strip()[:200]))
if _r.returncode != 0:
    raise RuntimeError("pip upgrade kaggle that bai: " + (_r.stderr or _r.stdout)[-500:])

V10_COMPETITION = "biohub-cell-tracking-during-development"
V10_DATASETS = [
    "pilkwang/biohub-tracking-support-pack-50ep-v1",
    "pilkwang/biohub-deepcenter-unet3d-center-prior-v1",
    "pilkwang/biohub-temporal-unet3d-seed314159-v1",
    "dalloliogm/biohub-official-scorer-patched",
    "dariushafshar/biohub-local-cv-pack",
    "vietnguyen130593/biohub-v6-heldout-preds",
    "giorgosi/biohub-divnet-v2",
    "sjlee101/biohub-hoct-020-wheels",
    "musculer/biohub-hoct-general-v0-official"
]
V10_STEMS = ["44b6_12dfb391", "44b6_267148e4", "44b6_2a2eff9f", "44b6_341df25f", "6bba_062c8d37", "6bba_07e24132", "6bba_085bf656", "6bba_09961292"]


# --- chọn root GHI ĐƯỢC: image Colab mới mount /kaggle/input (đôi khi cả working) READ-ONLY --------
def _v10_writable(p):
    try:
        _probe = p / ".v10_write_probe"
        _probe.write_text("ok")
        _probe.unlink()
        return True
    except OSError:
        return False


def _v10_pick_roots():
    # [kaggle-kernel] env override — kernel driver chỉ định sẵn writable roots
    _env_in = os.environ.get("V10_INPUT_ROOT")
    _env_wrk = os.environ.get("V10_WORKING_ROOT")
    if _env_in and _env_wrk:
        _input_root = Path(_env_in)
        _input_root.mkdir(parents=True, exist_ok=True)
        _working_root = Path(_env_wrk)
        _working_root.mkdir(parents=True, exist_ok=True)
        return _input_root, _working_root, "env override V10_INPUT_ROOT/V10_WORKING_ROOT"
    _inp = Path("/kaggle/input")
    try:
        _inp.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    if _v10_writable(_inp) or any((_inp / _full.split("/", 1)[1]).exists() for _full in V10_DATASETS):
        _input_root, _note = _inp, "/kaggle/input ghi được hoặc đã có dataset gắn sẵn"
    else:
        _input_root = Path("/content/kaggle/input")
        _input_root.mkdir(parents=True, exist_ok=True)
        _note = "Colab: /kaggle/input là mount READ-ONLY → chuyển sang /content"
    _wrk = Path("/kaggle/working")
    try:
        _wrk.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    if _v10_writable(_wrk):
        _working_root = _wrk
    else:
        _working_root = Path("/content/kaggle/working")
        _working_root.mkdir(parents=True, exist_ok=True)
    return _input_root, _working_root, _note


INPUT_ROOT, WORKING_DIR, _root_note = _v10_pick_roots()
os.environ["V10_INPUT_ROOT"] = str(INPUT_ROOT)
os.environ["V10_WORKING_ROOT"] = str(WORKING_DIR)
print(f"[v10-lab-setup] INPUT_ROOT   = {INPUT_ROOT} ({_root_note})")
print(f"[v10-lab-setup] WORKING_ROOT = {WORKING_DIR}")
TRAIN_DEST = INPUT_ROOT / V10_COMPETITION / "train"


def _v10_kaggle_base_cmd():
    # [v10-lab-setup] preflight: `python -m kaggle` cần bản >=2.2 (có __main__.py); Colab 2.0.x thiếu →
    # fallback console script `kaggle` (which). Nếu cả hai không chạy được thì báo lỗi rõ ràng.
    try:
        _r = subprocess.run([sys.executable, "-m", "kaggle", "--version"], capture_output=True, text=True, timeout=180)
    except Exception as _e:
        _r = None
        print(f"[v10-lab-setup] preflight python -m kaggle lỗi ({type(_e).__name__}: {_e})")
    if _r is not None and _r.returncode == 0:
        _v = [ln for ln in (_r.stdout or "").splitlines() if ln.strip().startswith("Kaggle CLI")]
        print(f"[v10-lab-setup] kaggle CLI OK qua python -m kaggle ({_v[-1] if _v else 'version ?'})")
        return [sys.executable, "-m", "kaggle"]
    _bin = shutil.which("kaggle")
    if _bin:
        try:
            _r2 = subprocess.run([_bin, "--version"], capture_output=True, text=True, timeout=180)
        except Exception as _e:
            _r2 = None
        if _r2 is not None and _r2.returncode == 0:
            print(f"[v10-lab-setup] python -m kaggle không chạy được — dùng console script: {_bin}")
            return [_bin]
    raise RuntimeError(
        "Không tìm thấy kaggle CLI chạy được (python -m kaggle lỗi + console script thiếu). "
        "Restart runtime rồi chạy lại Cell 2 (cell tự %pip install --upgrade kaggle>=2.2), "
        "hoặc chạy thủ công: !pip install --upgrade 'kaggle>=2.2' rồi chạy lại Cell 2.")


V10_KAGGLE_CMD = _v10_kaggle_base_cmd()


import threading  # [v10-lab-setup] 429: backoff phối hợp giữa các luồng tải

_V10_429_LOCK = threading.Lock()
_V10_PAUSE_UNTIL = 0.0


def v10_run_kaggle(args, check=True, timeout=3600, tries=6):
    # [v10-lab-setup] 429 Too Many Requests → backoff luỹ tiến 30→60→120→240→300s, MỌI luồng cùng
    # tôn trọng khoảng pause chung (tránh dồn API Kaggle khi tải hàng nghìn file nhỏ).
    global _V10_PAUSE_UNTIL
    cmd = [*V10_KAGGLE_CMD, *args]
    last = None
    for attempt in range(tries):
        with _V10_429_LOCK:
            _wait = _V10_PAUSE_UNTIL - time.time()
        if _wait > 0:
            time.sleep(_wait)
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if r.returncode == 0:
            return r
        _blob = (r.stdout or "") + (r.stderr or "")
        if "429" in _blob or "Too Many Requests" in _blob:
            _backoff = min(30 * (2 ** attempt), 300)
            with _V10_429_LOCK:
                _V10_PAUSE_UNTIL = max(_V10_PAUSE_UNTIL, time.time() + _backoff)
            print(f"[v10-lab-setup] 429 rate-limit — mọi luồng pause {_backoff}s (lần {attempt + 1}/{tries})")
            last = r
            continue
        last = r
        break
    if check:
        print((last.stdout or "")[-2000:])
        print((last.stderr or "")[-2000:], file=sys.stderr)
        raise RuntimeError(f"kaggle {' '.join(args[:3])} thất bại (exit {last.returncode})")
    return last


for _p in (INPUT_ROOT, WORKING_DIR):
    try:
        _p.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
print(f"[v10-lab-setup] roots sẵn sàng: input={INPUT_ROOT} · working={WORKING_DIR} (Colab)")

# --- [v10-drive] Google Drive cache (tuỳ chọn): zip stems8 + 9 dataset zip lưu trên Drive -------
# Mục tiêu: sau lần đầu thành công, các session Colab sau KHÔNG cần API Kaggle cho dữ liệu nữa
# (copy Drive→local qua mạng nội bộ Google nhanh); VM chết (VM#1 đã mất 2.2GB) không mất dữ liệu.
# V10_DRIVE: auto = mount khi chạy tương tác trong browser notebook (1 lần auth);
#            on = luôn thử mount; off = không dùng Drive (chạy headless qua bridge/CLI).
V10_DRIVE = os.environ.get("V10_DRIVE", "auto").strip().lower()
V10_DRIVE_CACHE = Path(os.environ.get("V10_DRIVE_CACHE_DIR", "/content/drive/MyDrive/biohub-v10-cache"))
V10_DRIVE_MOUNTED = False


def _v10_drive_try_mount(timeout_s=240):
    global V10_DRIVE_MOUNTED
    if V10_DRIVE == "off":
        print("[v10-drive] V10_DRIVE=off — không dùng Google Drive cache")
        return False
    _my = Path("/content/drive/MyDrive")
    if _my.is_dir():
        V10_DRIVE_MOUNTED = True
        print("[v10-drive] Drive đã mount sẵn — cache bền vững qua reset VM")
        return True
    if V10_DRIVE == "auto" and os.environ.get("V10_HEADLESS", "") == "1":
        print("[v10-drive] auto + V10_HEADLESS=1 — bỏ qua mount (không chờ popup auth)")
        return False
    try:
        from google.colab import drive  # noqa: E402
    except Exception as _e:
        print(f"[v10-drive] không import được google.colab ({type(_e).__name__}) — chạy không Drive")
        return False
    _box = {}

    def _m():
        try:
            drive.mount("/content/drive")
            _box["ok"] = True
        except Exception as _e:
            _box["err"] = f"{type(_e).__name__}: {_e}"

    _t = threading.Thread(target=_m, daemon=True)
    _t.start()
    _t.join(timeout_s)
    if _box.get("ok") and _my.is_dir():
        V10_DRIVE_MOUNTED = True
        print("[v10-drive] Drive mount OK — dữ liệu sống sót qua các lần reset VM")
        return True
    print(f"[v10-drive] mount chưa xong sau {timeout_s}s (hoặc lỗi {_box.get('err')}) — chạy không Drive")
    return False


_v10_drive_try_mount()


def _v10_drive_dir():
    if not V10_DRIVE_MOUNTED:
        return None
    try:
        (V10_DRIVE_CACHE / "zips").mkdir(parents=True, exist_ok=True)
        return V10_DRIVE_CACHE
    except OSError as _e:
        print(f"[v10-drive] không tạo được cache dir trên Drive ({_e}) — bỏ qua Drive")
        return None


def _v10_drive_load_manifest():
    _d = _v10_drive_dir()
    if _d is None:
        return None
    _f = _d / "drive_manifest.json"
    try:
        if _f.is_file():
            _m = json.loads(_f.read_text())
            if isinstance(_m.get("zips"), dict):
                return _m
    except Exception as _e:
        print(f"[v10-drive] drive_manifest.json lỗi ({_e}) — coi như chưa có cache")
    return {"zips": {}}


def _v10_drive_save_manifest(m):
    _d = _v10_drive_dir()
    if _d is None:
        return
    try:
        (_d / "drive_manifest.json").write_text(json.dumps(m, indent=1))
    except OSError as _e:
        print(f"[v10-drive] ghi drive_manifest.json lỗi ({_e}) — bỏ qua")


def _v10_drive_save_zip(local_zip, name):
    # lưu 1 zip lớn lên Drive: ghi .part xong mới rename (rename = marker "ghi xong")
    _d = _v10_drive_dir()
    if _d is None:
        return False
    _target = _d / "zips" / f"{name}.zip"
    try:
        _part = _d / "zips" / f"{name}.zip.part"
        _t0 = time.time()
        shutil.copyfile(local_zip, _part)
        _part.replace(_target)
        _m = _v10_drive_load_manifest()
        if _m is not None:
            _m["zips"][name] = {"size": _target.stat().st_size}
            _v10_drive_save_manifest(_m)
        print(f"[v10-drive] ĐÃ LƯU {name}.zip lên Drive ({_target.stat().st_size / 1e9:.2f} GB · {time.time() - _t0:.0f}s)")
        return True
    except OSError as _e:
        print(f"[v10-drive] lưu {name}.zip lên Drive LỖI ({_e}) — tiếp tục không cache")
        return False


def _v10_drive_load_zip(name, manifest):
    # trả Path zip LOCAL (copy từ Drive) nếu cache hợp lệ (size khớp manifest), ngược lại None
    if manifest is None:
        return None
    _d = _v10_drive_dir()
    if _d is None:
        return None
    _src = _d / "zips" / f"{name}.zip"
    _meta = (manifest.get("zips") or {}).get(name)
    if not (_src.is_file() and _meta):
        return None
    try:
        if _src.stat().st_size != int(_meta.get("size") or -1):
            print(f"[v10-drive] cache {name}.zip sai size ({_src.stat().st_size} ≠ manifest {_meta.get('size')}) — bỏ cache")
            return None
        _local = Path(tempfile.mkdtemp(prefix="v10drv_")) / f"{name}.zip"
        _t0 = time.time()
        shutil.copyfile(_src, _local)
        print(f"[v10-drive] copy {name}.zip từ Drive: {_local.stat().st_size / 1e9:.2f} GB · {time.time() - _t0:.0f}s")
        return _local
    except OSError as _e:
        print(f"[v10-drive] đọc cache {name}.zip lỗi ({_e})")
        return None


def _v10_drive_has_zip(name, manifest):
    # kiểm tra NHANH cache Drive có zip hợp lệ (không copy) — dùng cho backfill/skip
    if manifest is None:
        return False
    _d = _v10_drive_dir()
    if _d is None:
        return False
    _meta = (manifest.get("zips") or {}).get(name)
    _src = _d / "zips" / f"{name}.zip"
    try:
        return bool(_meta and _src.is_file() and _src.stat().st_size == int(_meta.get("size") or -1))
    except OSError:
        return False


def _v10_extract_dataset_zip(zip_path, dest):
    # 9 dataset ver-9: zip download chứa path trực tiếp (kiểm chứng VM#2: 0 zip lồng),
    # vẫn phòng hờ 1 tầng zip lồng (dataset tạo bằng --dir-mode zip).
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(dest)
    for _z in list(dest.rglob("*.zip")):
        if _z.relative_to(dest).as_posix().count("/") > 2:
            continue  # zip nằm sâu trong cây — artifact thật của dataset, không đụng
        try:
            with zipfile.ZipFile(_z) as _zin:
                _zin.extractall(_z.parent)
            _z.unlink()
            print(f"[v10-lab-setup] (đã tự giải zip lồng {_z.relative_to(dest)})")
        except zipfile.BadZipFile:
            pass


# --- 1) tải 9 dataset ver-9 (Drive cache ưu tiên — 0 API call khi có cache) ----------------------
_t0 = time.time()
_V10_DRIVE_MANIFEST = _v10_drive_load_manifest()
for _full in V10_DATASETS:
    _slug = _full.split("/", 1)[1]
    _dest = INPUT_ROOT / _slug
    if (_dest / ".v10_ok").exists() or (not _v10_writable(INPUT_ROOT) and _dest.exists()):
        print(f"[v10-lab-setup] dataset {_slug} đã có — bỏ qua")
        # [v10-drive] backfill: đã có trên đĩa nhưng Drive chưa có cache → đóng gói lưu lên (1 lần)
        if V10_DRIVE_MOUNTED and not _v10_drive_has_zip("ds_" + _slug, _V10_DRIVE_MANIFEST):
            _bakd = Path(tempfile.mkdtemp(prefix="v10bf_"))
            _bakz = _bakd / f"ds_{_slug}.zip"
            with zipfile.ZipFile(_bakz, "w", zipfile.ZIP_STORED) as _zbf:
                for _fp in _dest.rglob("*"):
                    if _fp.is_file():
                        _zbf.write(_fp, _fp.relative_to(_dest).as_posix())
            _v10_drive_save_zip(_bakz, "ds_" + _slug)
            shutil.rmtree(_bakd, ignore_errors=True)
        continue
    _dest.mkdir(parents=True, exist_ok=True)
    _dz = _v10_drive_load_zip("ds_" + _slug, _V10_DRIVE_MANIFEST)
    if _dz is not None:
        _v10_extract_dataset_zip(_dz, _dest)
        (_dest / ".v10_ok").write_text("ok")
        shutil.rmtree(_dz.parent, ignore_errors=True)
        _mb = sum(f.stat().st_size for f in _dest.rglob("*") if f.is_file()) / 1e6
        print(f"[v10-lab-setup] dataset {_slug} từ GOOGLE DRIVE ({_mb:.0f} MB · 0 API call)")
        continue
    _tmpds = Path(tempfile.mkdtemp(prefix="v10ds_"))
    v10_run_kaggle(["datasets", "download", _full, "-p", str(_tmpds), "-q"])
    _dzs = sorted(_tmpds.glob("*.zip"))
    if not _dzs:
        raise RuntimeError(f"datasets download {_full} không trả file zip nào trong {_tmpds}")
    _v10_extract_dataset_zip(_dzs[0], _dest)
    (_dest / ".v10_ok").write_text("ok")
    _v10_drive_save_zip(_dzs[0], "ds_" + _slug)
    shutil.rmtree(_tmpds, ignore_errors=True)
    _mb = sum(f.stat().st_size for f in _dest.rglob("*") if f.is_file()) / 1e6
    print(f"[v10-lab-setup] dataset {_slug} OK ({_mb:.0f} MB)")
print(f"[v10-lab-setup] 9 dataset xong trong {time.time() - _t0:.0f}s")

# --- 2) dependency install command từ support pack --------------------------------------------
_dep_file = INPUT_ROOT / "biohub-tracking-support-pack-50ep-v1" / "kaggle_dependency_install_command.txt"
if _dep_file.is_file():
    _cmd_txt = _dep_file.read_text().strip()
    for _full in V10_DATASETS:  # path mount Kaggle dạng datasets/<owner>/<slug> → /kaggle/input/<slug>
        _owner, _slug = _full.split("/", 1)
        _cmd_txt = _cmd_txt.replace(f"/kaggle/input/datasets/{_owner}/{_slug}", str(INPUT_ROOT / _slug))
        _cmd_txt = _cmd_txt.replace(f"/kaggle/input/{_slug}", str(INPUT_ROOT / _slug))
    print("[v10-lab-setup] kaggle_dependency_install_command.txt:", _cmd_txt[:300])
    _r = subprocess.run(_cmd_txt, shell=True, capture_output=True, text=True)
    print(f"[v10-lab-setup] dependency install exit={_r.returncode} ({(_r.stdout or '')[-400:]})")
    if _r.returncode != 0:
        print("[v10-lab-setup] CẢNH BÁO: lệnh cài deps trả exit != 0 — monolith sẽ tự cài từ wheels (Cell 3)")
else:
    print("[v10-lab-setup] (không có kaggle_dependency_install_command.txt — monolith sẽ tự cài từ wheels)")

# --- 3) HOCT wheels (dataset sjlee101) ---------------------------------------------------------
_hoct_wheels = sorted((INPUT_ROOT / "biohub-hoct-020-wheels").rglob("*.whl"))
if _hoct_wheels:
    _r = subprocess.run([sys.executable, "-m", "pip", "install", "-q", "--no-index", "--no-deps",
                         *[str(w) for w in _hoct_wheels]], capture_output=True, text=True)
    print(f"[v10-lab-setup] HOCT wheels {[w.name for w in _hoct_wheels]} → exit {_r.returncode}")
else:
    print("[v10-lab-setup] CẢNH BÁO: không tìm thấy .whl HOCT trong biohub-hoct-020-wheels")


# --- 4) 8 stems validator — 3 NẾP: (A) Drive cache → (B) dataset stems8 (1 call) → (C) per-file ---
# [v10-lab-setup] 429 gốc rễ: 984 file = 984 API call DownloadDataFile ≈ ngưỡng ~1000 req/ngày.
# Nếp B tải cả 3.4GB bằng đúng 1 call (dataset do kernel CPU Kaggle đóng gói từ input gắn sẵn);
# nếp A sau lần đầu thành công không cần Kaggle nữa (zip nằm trên Google Drive của anh).
# Nếp C (fallback cuối) dùng filelist 3 bậc: (a) cache local → (a2) Drive → (b) dataset filelist
# dựng sẵn (0 listing call) → (c) listing trực tiếp (sleep 2s/page + 429-backoff) + ghi cache.
V10_FILELIST_DATASET = "vietnguyen130593/biohub-v10-lab-filelist"


def _v10_list_comp_files():
    rows = []
    token = None
    while True:
        args = ["competitions", "files", V10_COMPETITION, "-v", "--page-size", "500"]
        if token:
            args += ["--page-token", token]
        r = v10_run_kaggle(args, timeout=300)
        next_token = None
        body = []
        for ln in r.stdout.splitlines():
            if ln.startswith("Next Page Token ="):
                next_token = ln.split("=", 1)[1].strip()
            else:
                body.append(ln)
        rows.extend(list(csv.DictReader(io.StringIO("\n".join(body)))))
        print(f"[v10-lab-setup] competitions files: tổng {len(rows):,} dòng{' · next page...' if next_token else ' · HẾT'}")
        if not next_token:
            return rows
        token = next_token
        time.sleep(2.0)  # [v10-lab-setup] giảm tốc phân trang — tránh 429


def _v10_load_comp_rows():
    _cache = WORKING_DIR / "v10_comp_files_cache.csv"
    if _cache.is_file():
        with _cache.open() as _f:
            _rows = list(csv.DictReader(_f))
        if _rows:
            print(f"[v10-lab-setup] filelist từ CACHE LOCAL: {len(_rows):,} dòng (0 API call)")
            return _rows
    _dd = _v10_drive_dir()
    if _dd is not None and (_dd / "comp_files.csv").is_file():
        with (_dd / "comp_files.csv").open() as _f:
            _rows = list(csv.DictReader(_f))
        if _rows:
            shutil.copyfile(_dd / "comp_files.csv", _cache)
            print(f"[v10-lab-setup] filelist từ GOOGLE DRIVE: {len(_rows):,} dòng (0 API call)")
            return _rows
    _dest = INPUT_ROOT / "biohub-v10-lab-filelist"
    if not (_dest / ".v10_ok").exists():
        _dest.mkdir(parents=True, exist_ok=True)
        _r = v10_run_kaggle(["datasets", "download", V10_FILELIST_DATASET, "-p", str(_dest), "--unzip", "-q"], check=False)
        if _r.returncode == 0:
            (_dest / ".v10_ok").write_text("ok")
            print(f"[v10-lab-setup] filelist từ DATASET {V10_FILELIST_DATASET} (0 listing call)")
        else:
            print(f"[v10-lab-setup] dataset filelist chưa có (hoặc lỗi) — sẽ listing trực tiếp (chậm hơn)")
    if (_dest / ".v10_ok").exists():
        _csvs = sorted(_dest.rglob("comp_files.csv"))
        if _csvs:
            with _csvs[0].open() as _f:
                _rows = list(csv.DictReader(_f))
            if _rows:
                shutil.copyfile(_csvs[0], _cache)
                print(f"[v10-lab-setup] filelist dataset: {len(_rows):,} dòng → đã lưu cache local")
                return _rows
    _rows = _v10_list_comp_files()
    with _cache.open("w", newline="") as _f:
        _w = csv.DictWriter(_f, fieldnames=["name", "size", "creationDate"])
        _w.writeheader()
        _w.writerows(_rows)
    _dd = _v10_drive_dir()
    if _dd is not None:
        try:
            shutil.copyfile(_cache, _dd / "comp_files.csv")
        except OSError:
            pass
    print(f"[v10-lab-setup] listing xong: {len(_rows):,} dòng → đã lưu cache local cho lần sau")
    return _rows


V10_STEMS8_DATASET = os.environ.get("V10_STEMS8_DATASET", "vietnguyen130593/biohub-v10-stems8")


def _v10_stems_complete():
    _bad = []
    for _s in V10_STEMS:
        _zarr = TRAIN_DEST / f"{_s}.zarr"
        _geff = TRAIN_DEST / f"{_s}.geff"
        _zarr_ok = _zarr.is_dir() and any(_zarr.rglob("zarr.json"))
        if not (_zarr_ok and _geff.exists()):
            _bad.append(_s)
    return _bad == [], _bad


def _v10_extract_stems_zip(zip_path, comp_dest):
    # Giải archive stems8 vào comp_dest (= INPUT_ROOT/<competition>). Chấp nhận 2 dạng:
    # (1) zip ngoài (datasets download không --unzip) chứa zip lồng ở GỐC (train.zip dir-mode
    #     hay stems8_payload.zip) + có thể MANIFEST.json ở gốc hoặc bên trong zip lồng;
    # (2) zip phẳng train/... + MANIFEST.json (dạng nếp C tự đóng gói). Trả manifest dict|None.
    _manifest = None
    _tmp = Path(tempfile.mkdtemp(prefix="v10stems_"))

    def _walk(zf):
        nonlocal _manifest
        for _m in zf.namelist():
            if _m.endswith("/"):
                continue
            _base = _m.split("/")[-1]
            if _base == "MANIFEST.json" and _manifest is None:
                _manifest = json.loads(zf.read(_m).decode("utf-8"))
            elif _base.endswith(".zip") and "/" not in _m:
                _inner = _tmp / f"inner{len(list(_tmp.iterdir()))}.zip"
                _inner.write_bytes(zf.read(_m))
                with zipfile.ZipFile(_inner) as _zin:
                    _walk(_zin)
            elif _m.startswith("train/"):
                zf.extract(_m, comp_dest)

    try:
        with zipfile.ZipFile(zip_path) as zf:
            _walk(zf)
        return _manifest
    finally:
        shutil.rmtree(_tmp, ignore_errors=True)


def _v10_verify_manifest(manifest, comp_dest):
    _files = (manifest or {}).get("files") or {}
    if not _files:
        return False, "manifest rỗng / thiếu danh sách file"
    _missing, _size_bad = [], []
    for _rel, _sz in _files.items():
        _fp = comp_dest / _rel
        if not _fp.is_file():
            _missing.append(_rel)
        elif _sz and _fp.stat().st_size != _sz:
            _size_bad.append(_rel)
    if _missing or _size_bad:
        return False, f"{len(_missing)} file thiếu · {len(_size_bad)} sai size (vd {(_missing + _size_bad)[:2]})"
    return True, f"{len(_files):,} file khớp tên+size hoàn toàn"


def _v10_pack_stems_zip():
    # Nếp C thành công → đóng gói train/8 stems + MANIFEST.json (STORED — zarr đã nén sẵn)
    _out = Path(tempfile.mkdtemp(prefix="v10pack_")) / "stems8.zip"
    _mani = {"stems": V10_STEMS, "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "files": {}}
    with zipfile.ZipFile(_out, "w", zipfile.ZIP_STORED) as zf:
        for _s in V10_STEMS:
            for _suf in (".zarr", ".geff"):
                _root = TRAIN_DEST / (_s + _suf)
                for _dp, _dn, _fn in os.walk(_root):
                    for _f in _fn:
                        _fp = Path(_dp) / _f
                        _rel = f"train/{_s}{_suf}/{_fp.relative_to(_root).as_posix()}"
                        zf.write(_fp, _rel)
                        _mani["files"][_rel] = _fp.stat().st_size
        _mani["n_files"] = len(_mani["files"])
        _mani["total_bytes"] = sum(_mani["files"].values())
        zf.writestr("MANIFEST.json", json.dumps(_mani, indent=1))
    print(f"[v10-lab-setup] đóng gói stems8.zip: {_mani['n_files']} file · {_mani['total_bytes'] / 1e9:.2f} GB (để lưu Drive)")
    return _out


def _v10_fetch_comp_file(name):
    dest = TRAIN_DEST / name
    if dest.exists() and dest.stat().st_size > 0:  # [v10-lab-setup] resume — đã tải ở lần chạy trước
        return name, dest.stat().st_size
    tmp = Path(tempfile.mkdtemp(prefix="v10dl_"))
    try:
        v10_run_kaggle(["competitions", "download", V10_COMPETITION, "-f", name, "-p", str(tmp), "-q"], timeout=1800)
        _arts = [p for p in tmp.rglob("*") if p.is_file()]
        if not _arts:
            raise RuntimeError(f"không tải được file nào cho {name}")
        _zips = [p for p in _arts if p.suffix == ".zip"]
        _art = _zips[0] if _zips else _arts[0]
        dest = TRAIN_DEST / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        if zipfile.is_zipfile(_art):
            with zipfile.ZipFile(_art) as zf:
                members = [m for m in zf.namelist() if not m.endswith("/")]
                target = None
                if name in members:
                    target = name
                elif len(members) == 1:
                    target = members[0]
                else:
                    _cand = [m for m in members if m.endswith("/" + name)]
                    if len(_cand) == 1:
                        target = _cand[0]
                if target is None:
                    raise RuntimeError(f"zip cho {name} không chứa file mong đợi: {members[:5]}")
                dest.write_bytes(zf.read(target))
        else:
            shutil.copyfile(_art, dest)
        return name, dest.stat().st_size
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


_t0 = time.time()
_stems_zip_local = None
_stems_ok, _stems_bad = _v10_stems_complete()
if _stems_ok:
    print(f"[v10-lab-setup] 8 stems đã có sẵn trên đĩa — bỏ qua toàn bộ tải ({time.time() - _t0:.0f}s dò)")
    # [v10-drive] backfill: đã có trên đĩa nhưng Drive chưa có cache → đóng gói lưu lên (1 lần)
    if V10_DRIVE_MOUNTED and not _v10_drive_has_zip("stems8", _V10_DRIVE_MANIFEST):
        _stems_zip_local = _v10_pack_stems_zip()
else:
    print(f"[v10-lab-setup] thiếu stems {_stems_bad} — nếp tải A(Drive) → B(dataset stems8) → C(per-file)")
    _got = False

    # --- nếp A: GOOGLE DRIVE cache (0 API call Kaggle) -------------------------------------------
    _dz = _v10_drive_load_zip("stems8", _V10_DRIVE_MANIFEST)
    if _dz is not None:
        _mani_a = _v10_extract_stems_zip(_dz, INPUT_ROOT / V10_COMPETITION)
        _ok_a, _why_a = _v10_verify_manifest(_mani_a, INPUT_ROOT / V10_COMPETITION)
        shutil.rmtree(_dz.parent, ignore_errors=True)
        if _ok_a:
            _got = True
            print(f"[v10-lab-setup] [A] stems8 từ GOOGLE DRIVE — {_why_a} · 0 API call Kaggle")
        else:
            print(f"[v10-lab-setup] [A] Drive cache verify LỖI ({_why_a}) — chuyển nếp B")

    # --- nếp B: dataset stems8 — 1 API call tải cả 3.4GB ------------------------------------------
    if not _got:
        _tmpb = Path(tempfile.mkdtemp(prefix="v10stems8_"))
        try:
            v10_run_kaggle(["datasets", "download", V10_STEMS8_DATASET, "-p", str(_tmpb), "-q"], timeout=7200)
            _zb = sorted(_tmpb.glob("*.zip"))
            if not _zb:
                raise RuntimeError(f"datasets download {V10_STEMS8_DATASET} không trả file zip nào")
            _mani_b = _v10_extract_stems_zip(_zb[0], INPUT_ROOT / V10_COMPETITION)
            _ok_b, _why_b = _v10_verify_manifest(_mani_b, INPUT_ROOT / V10_COMPETITION)
            if not _ok_b:
                raise RuntimeError(f"verify MANIFEST stems8 thất bại: {_why_b}")
            _got = True
            _stems_zip_local = _zb[0]
            print(f"[v10-lab-setup] [B] stems8 từ DATASET {V10_STEMS8_DATASET} — {_why_b} · 1 API call")
        except Exception as _e:
            print(f"[v10-lab-setup] [B] dataset stems8 LỖI ({type(_e).__name__}: {_e}) → fallback nếp C per-file")
            shutil.rmtree(_tmpb, ignore_errors=True)

    # --- nếp C: filelist 3 bậc + per-file 429-armor (v4 giữ nguyên) -------------------------------
    if not _got:
        _all_rows = _v10_load_comp_rows()
        _wanted = [r for r in _all_rows if any(r["name"].startswith(f"train/{s}.") for s in V10_STEMS)]
        _wanted_names = [r["name"] for r in _wanted]
        _total_bytes = sum(int(r.get("totalBytes") or r.get("size") or 0) for r in _wanted)
        print(f"[v10-lab-setup] [C] cần tải {len(_wanted_names):,} file cho {len(V10_STEMS)} stems — tổng {_total_bytes / 1e9:.2f} GB")


        _done = 0
        _done_bytes = 0
        _errors = []
        with ThreadPoolExecutor(max_workers=4) as _pool:
            _futures = {_pool.submit(_v10_fetch_comp_file, n): n for n in _wanted_names}
            for _fut in as_completed(_futures):
                _n = _futures[_fut]
                try:
                    _name, _sz = _fut.result()
                    _done += 1
                    _done_bytes += _sz
                except Exception as _e:
                    _errors.append((_n, f"{type(_e).__name__}: {_e}"))
                if _done % 200 == 0 or _done == len(_wanted_names):
                    print(f"[v10-lab-setup] [C] tiến độ {_done}/{len(_wanted_names)} file · {_done_bytes / 1e9:.2f} GB · {time.time() - _t0:.0f}s")
        if _errors:
            print(f"[v10-lab-setup] {len(_errors)} file LỖI:")
            for _n, _e in _errors[:10]:
                print("   ", _n, "→", _e)
            raise RuntimeError(f"tải competition files thất bại {len(_errors)}/{len(_wanted_names)} — xem log trên (chạy lại cell để retry)")
        _stems_zip_local = _v10_pack_stems_zip()

# lưu zip stems8 lên Drive (nếu Drive mounted) — các session sau đi thẳng nếp A (0 API call)
if _stems_zip_local is not None:
    _v10_drive_save_zip(_stems_zip_local, "stems8")
    shutil.rmtree(_stems_zip_local.parent, ignore_errors=True)

# --- 5) verify 8 stems mỗi stem có .zarr + .geff ------------------------------------------------
_bad = []
for _s in V10_STEMS:
    _zarr = TRAIN_DEST / f"{_s}.zarr"
    _geff = TRAIN_DEST / f"{_s}.geff"
    _zarr_ok = _zarr.is_dir() and ((_zarr / "0" / "zarr.json").is_file() or (_zarr / "zarr.json").is_file() or any(_zarr.rglob("zarr.json")))
    _geff_ok = _geff.exists()
    if not (_zarr_ok and _geff_ok):
        _bad.append((_s, f"zarr={_zarr_ok} geff={_geff_ok}"))
    else:
        print(f"[v10-lab-setup] stem {_s} OK (.zarr {sum(1 for _ in _zarr.rglob('*') if _.is_file()):,} file · .geff {'dir' if _geff.is_dir() else 'file'})")
if _bad:
    for _s, _why in _bad:
        print(f"[v10-lab-setup] LỖI stem {_s}: {_why}")
    raise RuntimeError(f"verify 8 stems thất bại: {[s for s, _ in _bad]} — chạy lại Cell 2 để retry")
print(f"[v10-lab-setup] SETUP HOÀN TẤT ({time.time() - _t0:.0f}s) — chuyển Cell 3")


# --- [bridge-adapt] footer: dump env V10*/KAGGLE*/BIOHUB* ra JSON cho cac buoc sau (subprocess rieng) ---
import json as _json
_envdump = {k: v for k, v in os.environ.items() if k.startswith("V10") or k.startswith("KAGGLE") or k.startswith("BIOHUB")}
with open("/content/v10_env.json", "w") as _fh:
    _json.dump(_envdump, _fh, indent=1)
with open("/content/v10_cell2.done", "w") as _fh:
    _fh.write("OK %d\n" % int(time.time()))
print("[v10-lab-setup] ENV_SAVED /content/v10_env.json (%d keys)" % len(_envdump))
print("[v10-lab-setup] BRIDGE_RUN_CELL2_DONE")
