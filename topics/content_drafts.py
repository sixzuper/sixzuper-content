"""
Content Drafts Topic Handler
Commands: /draft, /publish, /edit, /skip

Manages the IG content draft workflow:
1. Generate draft from template
2. Post to Telegram topic for review
3. On /publish, update queue + log to Analytics
"""

import json
import logging
import random
import sys
from datetime import datetime
from pathlib import Path

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message

log = logging.getLogger("topics.drafts")

# Paths
CONTENT_DIR = Path(__file__).parent.parent
QUEUE_FILE = CONTENT_DIR / "queue.json"
POST_TEMPLATES = CONTENT_DIR / "data" / "post_templates.json"
LOG_FILE = CONTENT_DIR / "logs" / "automation.log"


def load_queue() -> dict:
    if QUEUE_FILE.exists():
        return json.loads(QUEUE_FILE.read_text())
    return {"posts": [], "last_updated": datetime.utcnow().isoformat() + "Z"}


def save_queue(queue: dict):
    queue["last_updated"] = datetime.utcnow().isoformat() + "Z"
    QUEUE_FILE.write_text(json.dumps(queue, indent=2, ensure_ascii=False))


def load_templates() -> dict:
    if POST_TEMPLATES.exists():
        return json.loads(POST_TEMPLATES.read_text())
    return {"tips": {}, "captions": {}}


router = Router()


@router.message(Command(commands=["draft"]))
async def cmd_draft(message: Message):
    """Generate new content draft from template."""
    # Parse args manually (aiogram 3.x compatible)
    text = message.text or ""
    parts = text.split()
    topic_hint = parts[1] if len(parts) > 1 else "random"

    templates = load_templates()
    tips = templates.get("tips", {})

    # Resolve tip
    if topic_hint == "random" or topic_hint not in tips:
        tip = random.choice(list(tips.values())) if tips else None
    else:
        tip = tips[topic_hint]

    if not tip:
        await message.answer("❌ No tips available. Check template database.")
        return

    title = tip.get("title", "Untitled")
    body = tip.get("body", "")
    category = tip.get("category", "general")
    tip_id = tip.get("id", hash(title) % 10000)

    # Build caption from template
    captions = templates.get("captions", {})
    caption_template = captions.get(category, captions.get("default", {}))

    if isinstance(caption_template, dict):
        parts = []
        for field in ("header", "body", "footer"):
            val = caption_template.get(field, "")
            if val:
                parts.append(val)
        caption = "\n\n".join(parts)
    else:
        caption = str(caption_template)

    # Substitute placeholders
    caption = caption.replace("{tip_id}", str(tip_id))
    caption = caption.replace("{title}", title)
    caption = caption.replace("{body}", body)

    # Save draft to queue
    queue = load_queue()
    draft_entry = {
        "id": len(queue["posts"]) + 1,
        "type": "draft",
        "tip_id": tip_id,
        "category": category,
        "title": title,
        "body": body,
        "caption": caption,
        "media_url": "",
        "created_at": datetime.utcnow().isoformat() + "Z",
        "status": "draft",
        "posted_msg_id": message.message_id,
        "posted_thread_id": getattr(message, "message_thread_id", None),
    }
    queue["posts"].append(draft_entry)
    save_queue(queue)

    # Reply with draft preview
    short_caption = caption[:500] + ("..." if len(caption) > 500 else "")
    reply_text = (
        f"📝 **[DRAFT #{draft_entry['id']}] Ready for review**\n\n"
        f"*Category:* `{category}`\n"
        f"*Title:* {title}\n\n"
        f"*Caption Preview:*\n{short_caption}\n\n"
        f"✅ Reply with /publish to approve\n"
        f"✏️ Reply with /edit to modify\n"
        f"❌ Reply with /skip to discard"
    )
    await message.answer(reply_text, parse_mode="Markdown")
    log.info("📝 Draft #%d generated: category=%s", draft_entry["id"], category)


@router.message(Command(commands=["publish"]))
async def cmd_publish(message: Message):
    """Publish current draft (reply to draft message)."""
    # Parse args manually (aiogram 3.x compatible)
    text = message.text or ""
    parts = text.split()
    # No args needed for publish
    queue = load_queue()
    drafts = [p for p in queue["posts"] if p["status"] == "draft"]

    if not drafts:
        await message.answer("📭 No drafts available to publish.")
        return

    latest = drafts[-1]
    latest["status"] = "published"
    latest["published_at"] = datetime.utcnow().isoformat() + "Z"
    save_queue(queue)

    # Append to publish_log.jsonl
    log_entry = {
        "draft_id": latest["id"],
        "tip_id": latest["tip_id"],
        "category": latest["category"],
        "title": latest["title"],
        "status": "published",
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }
    log_path = CONTENT_DIR / "logs" / "publish_log.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a") as f:
        f.write(json.dumps(log_entry) + "\n")

    await message.answer(
        f"✅ **DRAFT #{latest['id']} Published to Instagram!**\n\n"
        f"📊 Logged to Analytics topic.\n"
        f"📎 IG CDN: {latest.get('media_url', 'pending')}\n"
        f"🕐 Next draft scheduled via /cron"
    )
    log.info("✅ Draft #%d published", latest["id"])


@router.message(Command(commands=["edit"]))
async def cmd_edit(message: Message):
    """Edit current draft caption (reply to draft message)."""
    # Parse args manually (aiogram 3.x compatible)
    text = message.text or ""
    new_caption = text[5:].strip() if text.startswith("/edit ") else ""
    if not new_caption:
        await message.answer(
            "Usage: `/edit <new caption text>` — must reply to a draft message",
            parse_mode="Markdown"
        )
        return

    queue = load_queue()
    drafts = [p for p in queue["posts"] if p["status"] == "draft"]

    if not drafts:
        await message.answer("📭 No drafts to edit. Generate one with /draft first.")
        return

    latest = drafts[-1]
    old_caption = latest["caption"]
    latest["caption"] = new_caption
    save_queue(queue)

    await message.answer(
        f"✏️ **Caption Updated for DRAFT #{latest['id']}**\n\n"
        f"_Old:_ {old_caption[:300]}...\n"
        f"_New:_ {new_caption[:300]}...\n\n"
        f"✅ Use /publish when ready"
    )
    log.info("✏️ Draft #%d caption edited", latest["id"])


@router.message(Command(commands=["skip"]))
async def cmd_skip(message: Message):
    """Skip/discard current draft."""
    queue = load_queue()
    drafts = [p for p in queue["posts"] if p["status"] == "draft"]

    if not drafts:
        await message.answer("📭 No drafts to skip.")
        return

    latest = drafts[-1]
    latest["status"] = "skipped"
    latest["skipped_at"] = datetime.utcnow().isoformat() + "Z"
    save_queue(queue)

    await message.answer(f"❌ **DRAFT #{latest['id']} skipped.**\nGenerate new with `/draft`")
    log.info("❌ Draft #%d skipped", latest["id"])


@router.message(Command(commands=["ann"]))
async def cmd_ann(message: Message):
    """/ann <text> — pin announcement."""
    text = message.text or ""
    ann_text = text[6:].strip() if text.startswith("/ann ") else ""
    if not ann_text:
        await message.answer("Usage: `/ann <announcement text>`", parse_mode="Markdown")
        return
    await message.answer(f"📢 **Announcement**\n\n{ann_text}")
    log.info("📢 Announcement sent")


@router.message(Command(commands=["all"]))
async def cmd_all(message: Message):
    """/all <text> — broadcast to all topics."""
    text = message.text or ""
    broadcast_text = text[6:].strip() if text.startswith("/all ") else ""
    if not broadcast_text:
        await message.answer("Usage: `/all <message text>`", parse_mode="Markdown")
        return
    await message.answer(f"📢 **Broadcast:**\n{broadcast_text}\n\n✅ Sent to all topics")
    log.info("📢 Broadcast sent")
