#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""register_browser_t4.py — bắt runtime T4 do user kết nối trong BROWSER thành session CLI.

Cách dùng: user mở Colab trong browser → Runtime → T4 GPU → Connect → tab giữ mở.
Chạy script này: nó tìm assignment T4 trong list_assignments (runtime browser) và
đưa vào store sessions.json của CLI (session name = t4live) để exec/upload điều khiển.

Sau khi register, keep-alive qua CLI cũng giữ được runtime (không phụ thuộc user
tương tác) + kernel exec keep-busy chống idle-reaper.
"""
import sys

sys.path.insert(0, "/home/z/.venv/lib/python3.12/site-packages")
from colab_cli.common import state  # noqa: E402
from colab_cli.state import SessionState  # noqa: E402

assignments = state.client.list_assignments()
t4 = [a for a in assignments if a.accelerator.value == "T4" and a.variant.name == "GPU"]
if not t4:
    print("KHÔNG THẤY ASSIGNMENT T4 — user chưa connect runtime T4 trong browser (hoặc đã chết)")
    print("Hiện có:", [(a.endpoint, a.variant.name, a.accelerator.value) for a in assignments])
    sys.exit(2)
a = t4[0]

cur = state.store.get("t4live")
s = SessionState(
    name="t4live",
    token=a.runtime_proxy_info.token,
    url=a.runtime_proxy_info.url,
    endpoint=a.endpoint,
    variant="GPU",
    accelerator="T4",
    kernel_id=(cur.kernel_id if cur else None),
    session_id=(cur.session_id if cur else None),
)
state.store.add(s)
print("★ REGISTERED t4live: endpoint=%s url=%s" % (a.endpoint, a.runtime_proxy_info.url))
print("  token exp=%ss kernel=%s" % (a.runtime_proxy_info.token_expires_in_seconds, s.kernel_id))
