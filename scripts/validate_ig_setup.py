#!/usr/bin/env python3
"""Validate SixZuper Instagram Graph API setup without printing secrets."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from urllib import parse, request, error

ENV_PATH = Path.home() / ".hermes" / ".env"
GRAPH = "https://graph.facebook.com/v18.0"


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    # File .env is authoritative; OS env is fallback only to avoid stale exported tokens.
    for k, v in os.environ.items():
        if k.startswith(("IG_", "FB_", "META_")) and k not in env:
            env[k] = v
    return env


def graph_get(path: str, params: dict[str, str]) -> tuple[int, dict]:
    url = f"{GRAPH}/{path.lstrip('/')}?" + parse.urlencode(params)
    try:
        with request.urlopen(url, timeout=25) as resp:
            return resp.status, json.loads(resp.read().decode())
    except error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        try:
            data = json.loads(body)
        except Exception:
            data = {"raw": body}
        return exc.code, data


def main() -> int:
    env = load_env()
    token = env.get("IG_ACCESS_TOKEN", "")
    ig_user_id = env.get("IG_USER_ID", "")
    fb_page_id = env.get("FB_PAGE_ID", "")

    print("SixZuper IG Setup Validation")
    print("=" * 36)
    print(f"ENV file: {ENV_PATH} exists={ENV_PATH.exists()}")
    print(f"IG_ACCESS_TOKEN: {'present' if token else 'missing'} prefix={(token[:4] + '***') if token else '-'}")
    print(f"IG_USER_ID: {ig_user_id or 'missing'}")
    print(f"FB_PAGE_ID: {fb_page_id or 'missing'}")

    if not token or not ig_user_id:
        print("❌ Missing IG_ACCESS_TOKEN or IG_USER_ID")
        return 2

    status, data = graph_get(ig_user_id, {
        "fields": "id,username,media_count",
        "access_token": token,
    })
    if status != 200 or "id" not in data:
        print("❌ IG user validation failed")
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 3
    print(f"✅ IG user OK: @{data.get('username')} media_count={data.get('media_count')}")

    if fb_page_id:
        status, pdata = graph_get(fb_page_id, {
            "fields": "id,name,instagram_business_account{id,username}",
            "access_token": token,
        })
        if status == 200 and pdata.get("instagram_business_account", {}).get("id") == ig_user_id:
            iba = pdata["instagram_business_account"]
            print(f"✅ Page link OK: {pdata.get('name')} → @{iba.get('username')} ({iba.get('id')})")
        else:
            print("⚠️ Page link check failed or IG mismatch")
            print(json.dumps(pdata, ensure_ascii=False, indent=2))

    print("✅ Meta read validation complete. Publishing still requires public HTTPS media_url.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
