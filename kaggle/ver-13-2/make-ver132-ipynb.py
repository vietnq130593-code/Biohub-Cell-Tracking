#!/usr/bin/env python3
"""make-ver132-ipynb.py — Gói monolith v13.2 thành notebook kernel.

Lấy notebook biohub-ver131 (pull từ Kaggle 23/9, cell == monolith md5 c21e82f2),
thay cell monolith bằng v13.2 → download/ver132-cell-tracking.ipynb.

Verify sau khi chạy: cell-extract md5 == md5(cell-monolith.py) — byte-exact.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]                     # Biohub-Cell-Tracking/
BASE_NB = PROJECT / "kaggle" / "ver-13-1" / "kernel-pull" / "biohub-ver131.ipynb"
MONO = HERE / "cell-monolith.py"
OUT = PROJECT / "download" / "ver132-cell-tracking.ipynb"


def main() -> None:
    mono = MONO.read_text()
    mono_md5 = hashlib.md5(mono.encode()).hexdigest()
    nb = json.loads(BASE_NB.read_text())
    cells = [c for c in nb["cells"] if c.get("cell_type") == "code"]
    big = max(cells, key=lambda c: len("".join(c.get("source", []))))
    before = hashlib.md5("".join(big["source"]).encode()).hexdigest()
    # source dạng list-of-lines giống Kaggle format
    lines = mono.splitlines(keepends=True)
    big["source"] = lines
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(nb, indent=1))
    # verify tròn: extract lại từ file mới
    nb2 = json.loads(OUT.read_text())
    cells2 = [c for c in nb2["cells"] if c.get("cell_type") == "code"]
    big2 = max(cells2, key=lambda c: len("".join(c.get("source", []))))
    after = hashlib.md5("".join(big2["source"]).encode()).hexdigest()
    print(f"base cell md5 (v131) : {before}")
    print(f"monolith md5 (v132)  : {mono_md5}")
    print(f"notebook cell md5    : {after}")
    if after != mono_md5:
        sys.exit("❌ notebook cell != monolith — HỦY")
    print(f"✅ {OUT} ({OUT.stat().st_size // 1024} KB) — cell == monolith BYTE-EXACT")


if __name__ == "__main__":
    main()
