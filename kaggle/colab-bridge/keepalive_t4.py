#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""keepalive_t4.py — refresh proxy token (hạn ~1h) + ping keep-alive assignment t4live.
Gọi mỗi vòng poll (daemon không sống nổi trên sandbox do reaper)."""
import sys

sys.path.insert(0, "/home/z/.venv/lib/python3.12/site-packages")

from colab_cli.common import state  # noqa: E402
from colab_cli.state import SessionState  # noqa: E402

assignments = state.client.list_assignments()
t4 = [a for a in assignments if a.accelerator.value == "T4" and a.variant.name == "GPU"]
if not t4:
    print("KHONG CON ASSIGNMENT T4 — session chet, can re-register khi user browser reconnect")
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
print("token refreshed: endpoint=%s exp=%ss kernel_id=%s" % (
    a.endpoint, a.runtime_proxy_info.token_expires_in_seconds, s.kernel_id))

try:
    state.client.keep_alive_assignment(a.endpoint)
    print("keep-alive ping OK")
except Exception as e:
    print("keep-alive ping failed (khong chan): %r" % e)
