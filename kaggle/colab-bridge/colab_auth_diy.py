#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""colab_auth_diy.py — tự điều khiển OAuth copy-paste flow của colab CLI.

Vấn đề: process `colab sessions` giữ PKCE code_verifier trong RAM — bị sandbox
reaper giết sau ~2 phút, trước khi user kịp trả code.

Giải pháp: 2 pha, không cần process sống lâu:
  Phase A (auth-diy.py url)  : sinh code_verifier (lưu /home/z/.v10_colab_verifier
                               + copy /tmp) + in auth URL cho user.
  Phase B (auth-diy.py swap <code>) : POST token endpoint đổi code (kèm verifier)
                               → ghép token.json đúng format google-auth → chạy
                               verify `colab sessions`.

Token format = Credentials.to_json() của google-auth (from_authorized_user_file).
"""
import base64
import hashlib
import json
import os
import secrets
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

CLIENT_ID = "764086051850-6qr4p6gpi6hn506pt8ejuq83di341hur.apps.googleusercontent.com"
CLIENT_SECRET = "d-FL95Q19q7MQmFpd7hHD0Ty"
REDIRECT_URI = "https://sdk.cloud.google.com/applicationdefaultauthcode.html"
SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/cloud-platform",
    "https://www.googleapis.com/auth/colaboratory",
    "https://www.googleapis.com/auth/drive.file",
]
TOKEN_URI = "https://oauth2.googleapis.com/token"
VERIFIER_PATHS = [Path("/home/z/.v10_colab_verifier"), Path("/tmp/v10_colab_verifier")]


def save_verifier(v: str) -> None:
    for p in VERIFIER_PATHS:
        try:
            p.write_text(v)
            os.chmod(p, 0o600)
        except OSError:
            pass


def load_verifier() -> str:
    for p in VERIFIER_PATHS:
        if p.is_file() and p.read_text().strip():
            return p.read_text().strip()
    raise SystemExit("Không tìm thấy code_verifier — chạy lại phase A (url)")


def phase_url() -> None:
    verifier = secrets.token_urlsafe(64)[:128]  # 43-128 chars base64url
    save_verifier(verifier)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    state = secrets.token_urlsafe(24)
    params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": "+".join(SCOPES),
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "prompt": "consent",
        "token_usage": "remote",
        "access_type": "offline",
    }
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(params)
    print("AUTH_URL:")
    print(url)
    print()
    print("Verifer đã lưu — mở URL bằng browser bất kỳ (máy anh/điện thoại),")
    print("approve, Google hiện authorization code → gửi code về đây.")


def phase_swap(code: str) -> None:
    verifier = load_verifier()
    data = urllib.parse.urlencode({
        "code": code.strip(),
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
        "code_verifier": verifier,
    }).encode()
    req = urllib.request.Request(TOKEN_URI, data=data,
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        tok = json.loads(resp.read().decode())
    if "refresh_token" not in tok:
        raise SystemExit("Token response không có refresh_token: " + json.dumps(tok)[:400])
    expiry = datetime.now(timezone.utc) + timedelta(seconds=int(tok.get("expires_in", 3600)))
    token_json = {
        "refresh_token": tok["refresh_token"],
        "token": tok["access_token"],
        "token_uri": TOKEN_URI,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scopes": SCOPES,
        "universe_domain": "googleapis.com",
        "account": "",
        "expiry": expiry.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-4] + "Z",
    }
    out = Path(os.path.expanduser("~/.config/colab-cli/token.json"))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(token_json, indent=2))
    os.chmod(out, 0o600)
    print("★ TOKEN SAVED → %s (scope: %d)" % (out, len(tok.get("scope", "").split())))
    # dọn verifier (single-use)
    for p in VERIFIER_PATHS:
        try:
            p.unlink()
        except OSError:
            pass


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "url":
        phase_url()
    elif len(sys.argv) >= 3 and sys.argv[1] == "swap":
        phase_swap(sys.argv[2])
    else:
        raise SystemExit("Dùng: colab_auth_diy.py url  |  colab_auth_diy.py swap <CODE>")
