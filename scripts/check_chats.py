#!/usr/bin/env python3
"""Check which Telegram chats the bot can access."""
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

# Bot info
url = f"https://api.telegram.org/bot{bot_token}/getMe"
resp = urllib.request.urlopen(urllib.request.Request(url), timeout=30)
r = json.loads(resp.read())
bot = r["result"]
print(f"Bot: {bot['first_name']} (@{bot['username']}) id={bot['id']}")
print()

# Try getting chat info for all relevant chat IDs
for chat_id in [-1001415438516, -1003934372713, -1003924559518, 974026313]:
    url3 = f"https://api.telegram.org/bot{bot_token}/getChat?chat_id={chat_id}"
    try:
        resp3 = urllib.request.urlopen(urllib.request.Request(url3), timeout=30)
        r3 = json.loads(resp3.read())
        if r3["ok"]:
            c = r3["result"]
            print(f"Chat {chat_id}: type={c.get('type')} title={c.get('title','N/A')} username={c.get('username','N/A')}")
        else:
            print(f"Chat {chat_id}: ERROR - {r3.get('description','?')}")
    except urllib.error.HTTPError as e:
        print(f"Chat {chat_id}: HTTP {e.code} - {e.read().decode()[:200]}")
