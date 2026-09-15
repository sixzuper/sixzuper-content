#!/usr/bin/env python3
"""Deliver IG content drafts to Telegram forum topic #3."""
import json, urllib.request, urllib.error
from pathlib import Path
from datetime import datetime, timezone

ENV_PATH = Path.home() / ".hermes" / ".env"
DRAFTS_DIR = Path("/home/aisixzuperlabs/sixzuper-content/drafts")
QUEUE_FILE = Path("/home/aisixzuperlabs/sixzuper-content/queue.json")
LOG_FILE = Path("/home/aisixzuperlabs/sixzuper-content/logs/automation.log")

def load_env():
    env = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text().splitlines():
            line = line.strip()
            if line and "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env

def tg_api(bot_token, method, data):
    url = f"https://api.telegram.org/bot{bot_token}/{method}"
    req = urllib.request.Request(url, data=json.dumps(data).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return {"ok": False, "error_code": e.code, "description": e.read().decode()}

def log_msg(msg):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    entry = f"{ts} [INFO] {msg}"
    print(entry)
    if LOG_FILE.parent.exists():
        with open(LOG_FILE, "a") as f:
            f.write(entry + "\n")

def main():
    env = load_env()
    bot_token = env.get("TELEGRAM_BOT_TOKEN", "")
    if not bot_token:
        log_msg("ERROR: TELEGRAM_BOT_TOKEN not found")
        return

    # Target chat — bot is a member of IG SIXZUPER group (-1003934372713)
    # Forum topic #3 corresponds to message_thread_id=3
    CHAT_ID = -1003934372713
    THREAD_ID = 3

    # Find latest draft file
    drafts = sorted(DRAFTS_DIR.glob("ig_draft_*.json"), key=lambda p: p.name, reverse=True)
    if not drafts:
        log_msg("ERROR: No draft files found")
        return

    draft_file = drafts[0]
    with open(draft_file) as f:
        draft_data = json.load(f)

    posts = draft_data.get("posts", [])
    generated_at = draft_data.get("generated_at", "")

    log_msg(f"Loading drafts from {draft_file.name} ({len(posts)} posts)")

    # --- Message 1: Summary header ---
    header_lines = [
        "📱 <b>SixZuper IG Daily Content Draft</b>",
        f"<b>🗓️ {generated_at}</b>",
        f"<b>📤 Forum Topic #3 — Review for Pa Ricky</b>",
        "",
        f"<b>Total Posts: {len(posts)}</b>",
        "",
    ]
    for p in posts:
        header_lines.append(f"━━━━━━━━━━━━━━")
        header_lines.append(f"<b>⏰ {p['wib_time']} WIB</b>")
        header_lines.append(f"<b>📍 Theme: {p['theme']}</b>")
        header_lines.append(f"<b>💡 Tip #{p['tip_id']} | {p['category'].upper()} | {p['title']}</b>")
        header_lines.append("")

    header_text = "\n".join(header_lines)
    r1 = tg_api(bot_token, "sendMessage", {
        "chat_id": CHAT_ID,
        "message_thread_id": THREAD_ID,
        "text": header_text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    })

    if not r1.get("ok"):
        log_msg(f"ERROR: Header delivery failed: {r1}")
        # Try without thread_id (maybe topic doesn't exist)
        r1 = tg_api(bot_token, "sendMessage", {
            "chat_id": CHAT_ID,
            "text": header_text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        })
        if not r1.get("ok"):
            log_msg(f"ERROR: Fallback delivery also failed: {r1}")
            return
        log_msg("Header delivered (without thread_id)")
    else:
        log_msg(f"Header delivered to topic #3 (msg_id={r1['result']['message_id']})")

    # --- Messages 2-4: Individual post details ---
    msg_ids = []
    for p in posts:
        lines = []
        lines.append(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append(f"<b>⏰ {p['wib_time']} WIB</b>")
        lines.append(f"<b>📍 Theme: {p['theme']}</b>")
        lines.append(f"<b>💡 Tip #{p['tip_id']} | {p['category'].upper()} | {p['title']}</b>")
        lines.append("")
        lines.append(f"<b>🎨 DALL·E Prompt:</b>")
        lines.append(f"<code>{p['dalle_prompt']}</code>")
        lines.append("")
        lines.append(f"<b>📝 Caption [LONG]:</b>")
        lines.append(f"<pre>{p['captions']['long'][:1500]}</pre>")
        lines.append("")
        lines.append(f"<b>📝 Caption [SHORT]:</b>")
        lines.append(f"<pre>{p['captions']['short'][:1500]}</pre>")
        lines.append("")
        lines.append(f"<b>📝 Caption [CTA-ONLY]:</b>")
        lines.append(f"<pre>{p['captions']['cta_only']}</pre>")
        lines.append("")
        lines.append(f"<b>📄 Body (full):</b>")
        lines.append(f"<pre>{p['body'][:1500]}</pre>")

        msg_text = "\n".join(lines)
        r = tg_api(bot_token, "sendMessage", {
            "chat_id": CHAT_ID,
            "message_thread_id": THREAD_ID,
            "text": msg_text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        })

        if not r.get("ok"):
            # Fallback without thread_id
            r = tg_api(bot_token, "sendMessage", {
                "chat_id": CHAT_ID,
                "text": msg_text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            })

        if r.get("ok"):
            msg_id = r["result"]["message_id"]
            msg_ids.append(msg_id)
            log_msg(f"Delivered post {p['wib_time']} WIB (msg_id={msg_id})")
        else:
            log_msg(f"ERROR: Failed to deliver {p['wib_time']} WIB: {r}")
            msg_ids.append(None)

    # --- Message 5: Footer ---
    footer = "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n✅ <b>3 IG drafts ready.</b>\nReply /publish to approve, /edit to modify, /skip to discard."
    rf = tg_api(bot_token, "sendMessage", {
        "chat_id": CHAT_ID,
        "message_thread_id": THREAD_ID,
        "text": footer,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    })
    if not rf.get("ok"):
        rf = tg_api(bot_token, "sendMessage", {"chat_id": CHAT_ID, "text": footer, "parse_mode": "HTML"})
    log_msg(f"Footer delivered (msg_id={rf.get('result',{}).get('message_id','?')})")

    # --- Update queue.json ---
    if QUEUE_FILE.exists():
        queue = json.loads(QUEUE_FILE.read_text())
    else:
        queue = {"posts": [], "last_updated": ""}

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for i, p in enumerate(posts):
        entry = {
            "id": len(queue["posts"]) + 1,
            "type": "ig_draft",
            "tip_id": p["tip_id"],
            "category": p["category"],
            "title": p["title"],
            "body": p["body"],
            "dalle_prompt": p["dalle_prompt"],
            "captions": p["captions"],
            "slot": p["wib_time"],
            "theme": p["theme"],
            "draft_file": draft_file.name,
            "created_at": now,
            "status": "draft_ready",
            "posted_msg_id": msg_ids[i] if i < len(msg_ids) else None,
            "posted_thread_id": THREAD_ID,
            "posted_chat_id": CHAT_ID,
        }
        queue["posts"].append(entry)

    queue["last_updated"] = now
    QUEUE_FILE.write_text(json.dumps(queue, indent=2, ensure_ascii=False))
    log_msg(f"Queue updated: {len(queue['posts'])} total entries")

if __name__ == "__main__":
    main()
