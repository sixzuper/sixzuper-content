#!/usr/bin/env python3
"""Prepare draft_ready SixZuper queue items into IG publisher scheduled posts.

This converts existing bot/draft queue entries into the schema expected by
scripts/ig_daily_publish.py and scripts/queue_manager.py:
  status=scheduled, image_url, caption, hashtags, post_time, media_type.

Default media hosting is temporary public placeholder URLs. Replace with GitHub
raw/CDN URLs once hosting is authenticated.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote_plus

CONTENT_DIR = Path(__file__).resolve().parents[1]
QUEUE_FILE = CONTENT_DIR / "queue.json"
TEMPLATE_FILE = CONTENT_DIR / "data" / "post_templates.json"
DEFAULT_SLOTS = ["08:00", "13:00", "19:00"]
WIB = timezone(timedelta(hours=7))


def load_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text())


def save_json(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def clean_instagram_caption(text: str) -> str:
    """Remove Markdown code fences/emphasis that look poor on IG captions."""
    text = text.replace("```php", "").replace("```json", "").replace("```bash", "").replace("```dockerfile", "").replace("```ini", "").replace("```", "")
    text = text.replace("**", "").replace("*", "")
    text = re.sub(r"`([^`]+)`", r"\1", text)
    return text.strip()


def build_caption(post: dict, templates: dict) -> tuple[str, list[str]]:
    title = post.get("title") or "SixZuper Tech Tip"
    body = post.get("body") or post.get("content") or "Daily practical tech tip from SixZuper."
    category = post.get("category") or "general"
    tip_id = post.get("tip_id") or post.get("id") or ""

    captions = templates.get("captions", {}) if isinstance(templates, dict) else {}
    tpl = captions.get(category) or captions.get("default") or {}
    if isinstance(tpl, dict):
        raw = "\n\n".join(x for x in [tpl.get("header", ""), tpl.get("body", "{body}"), tpl.get("footer", "")] if x)
    else:
        raw = str(tpl or "💡 {title}\n\n{body}\n\n#SixZuper #TechTips")

    caption = raw.replace("{tip_id}", str(tip_id)).replace("{title}", title).replace("{body}", body)
    caption = clean_instagram_caption(caption)

    hashtags = re.findall(r"#[A-Za-z0-9_]+", caption)
    if not hashtags:
        hashtags = ["#SixZuper", "#TechTips", "#Developer", "#WebDev"]
    return caption, hashtags


def placeholder_image_url(title: str) -> str:
    # Public HTTPS URL accepted by Graph API for initial testing.
    text = quote_plus((title or "SixZuper Tech Tip")[:80])
    return f"https://placehold.co/1080x1080/0a0a2e/00d4ff/png?text={text}"


def next_slots(count: int, start_date: datetime | None = None) -> list[str]:
    base = start_date or datetime.now(WIB)
    date = base.date()
    result: list[str] = []
    day_offset = 0
    while len(result) < count:
        for slot in DEFAULT_SLOTS:
            hh, mm = map(int, slot.split(":"))
            dt = datetime(date.year, date.month, date.day, hh, mm, tzinfo=WIB) + timedelta(days=day_offset)
            # If today's slot already passed, schedule for next day.
            if dt <= base:
                dt += timedelta(days=1)
            result.append(dt.isoformat())
            if len(result) >= count:
                break
        day_offset += 1
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=3, help="Number of draft_ready posts to schedule")
    parser.add_argument("--media-base", default="placeholder", help="placeholder or public URL prefix")
    parser.add_argument("--dry-run", action="store_true", help="Preview only, do not write queue")
    args = parser.parse_args()

    queue = load_json(QUEUE_FILE, {"posts": [], "last_updated": None})
    posts = queue.get("posts", []) if isinstance(queue, dict) else queue
    templates = load_json(TEMPLATE_FILE, {"captions": {}})

    candidates = [p for p in posts if isinstance(p, dict) and p.get("status") == "draft_ready"][: args.limit]
    if not candidates:
        print("No draft_ready posts to schedule.")
        return 0

    slots = next_slots(len(candidates))
    changes = []
    for post, slot in zip(candidates, slots):
        caption, hashtags = build_caption(post, templates)
        title = post.get("title") or "SixZuper Tech Tip"
        image_url = post.get("image_url") or post.get("media_url") or placeholder_image_url(title)
        post.update({
            "status": "scheduled",
            "post_time": slot,
            "scheduled_publish_time": int(datetime.fromisoformat(slot).timestamp()),
            "media_type": post.get("media_type") or "IMAGE",
            "image_url": image_url,
            "media_url": image_url,
            "caption": caption,
            "hashtags": hashtags,
            "prepared_at": datetime.now(timezone.utc).isoformat(),
        })
        changes.append((post.get("id"), title, slot, image_url))

    if args.dry_run:
        print("DRY RUN — would schedule:")
    else:
        backup = QUEUE_FILE.with_suffix(".json.bak." + datetime.now().strftime("%Y%m%d-%H%M%S"))
        shutil.copy2(QUEUE_FILE, backup)
        if isinstance(queue, dict):
            queue["posts"] = posts
            queue["last_updated"] = datetime.now(timezone.utc).isoformat()
            save_json(QUEUE_FILE, queue)
        else:
            save_json(QUEUE_FILE, posts)
        print(f"Backup: {backup}")

    for pid, title, slot, image_url in changes:
        print(f"✅ #{pid} scheduled {slot} | {title}")
        print(f"   image_url={image_url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
