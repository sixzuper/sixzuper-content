#!/usr/bin/env python3
"""Quick test: send a simple message to Telegram forum topic #3."""
import json, urllib.request
from pathlib import Path

ENV_PATH = Path.home() / ".hermes" / ".env"
env = {}
if ENV_PATH.exists():
    for line in ENV_PATH.read_text().splitlines():
        line = line.strip()
        if line and "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()

bot_token = env.get("TELEGRAM_BOT_TOKEN", "")
chat_id = -1003934372713
thread_id = 3

url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
data = json.dumps({
    "chat_id": chat_id,
    "message_thread_id": thread_id,
    "text": "🧪 Test message from Agent Six — connection OK"
}).encode()

req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
try:
    resp = urllib.request.urlopen(req, timeout=30)
    r = json.loads(resp.read())
    print(f"ok={r['ok']}")
    if r["ok"]:
        print(f"message_id={r['result']['message_id']}")
        print(f"chat_title={r['result']['chat'].get('title', 'N/A')}")
    else:
        print(f"error={r}")
except urllib.error.HTTPError as e:
    print(f"HTTP {e.code}: {e.read().decode()}")
