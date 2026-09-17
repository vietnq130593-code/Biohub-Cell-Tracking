#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""register_t4.py — đăng ký assignment T4 (browser session của user) vào sessions.json
của colab-cli để có thể `colab exec -s t4live` (kênh chính thức, không cần tunnel)."""
import sys

sys.path.insert(0, "/home/z/.venv/lib/python3.12/site-packages")

from colab_cli.common import state  # noqa: E402
from colab_cli.state import SessionState  # noqa: E402

assignments = state.client.list_assignments()
print("server-side assignments:")
for a in assignments:
    print("  endpoint=%s acc=%s variant=%s shape=%s" % (
        a.endpoint, a.accelerator.value, a.variant.name, a.machine_shape.name))

t4 = [a for a in assignments if a.accelerator.value == "T4" and a.variant.name == "GPU"]
if not t4:
    print("KHONG TIM THAY assignment T4 GPU")
    sys.exit(1)

a = t4[0]
s = SessionState(
    name="t4live",
    token=a.runtime_proxy_info.token,
    url=a.runtime_proxy_info.url,
    endpoint=a.endpoint,
    variant="GPU",
    accelerator="T4",
)
state.store.add(s)
print("REGISTERED t4live -> endpoint=%s url=%s token_exp=%ss" % (
    s.endpoint, s.url[:70], a.runtime_proxy_info.token_expires_in_seconds))
