#!/usr/bin/env python3
"""
Manual IG content generator — bypass bot handler.
Generate 3x daily content (08/13/19 WIB schedule).
"""
import json, random
from pathlib import Path
from datetime import datetime, timezone

CONTENT_DIR = Path(__file__).parent
QUEUE_FILE = CONTENT_DIR / "queue.json"
POST_TEMPLATES = CONTENT_DIR / "data" / "post_templates.json"

def load_templates() -> dict:
    if POST_TEMPLATES.exists():
        return json.loads(POST_TEMPLATES.read_text())
    return {"tips": {}, "captions": {}}

def load_queue() -> dict:
    if QUEUE_FILE.exists():
        return json.loads(QUEUE_FILE.read_text())
    return {"posts": [], "last_updated": None}

def save_queue(q: dict):
    q["last_updated"] = datetime.now(timezone.utc).isoformat()
    QUEUE_FILE.write_text(json.dumps(q, indent=2, ensure_ascii=False))

def build_caption(caption_tpl: str, title: str, body: str, tip_id: int) -> str:
    c = caption_tpl.replace("{tip_id}", str(tip_id))
    c = c.replace("{title}", title)
    c = c.replace("{body}", body)
    return c

def main():
    templates = load_templates()
    tips = templates.get("tips", {})
    captions = templates.get("captions", {})

    # 3 content sets per day: 08/13/19 WIB
    # Pick 3 random tips for variety (ensure different)
    tip_keys = list(tips.keys())
    if len(tip_keys) >= 3:
        selected_keys = random.sample(tip_keys, 3)
    elif tip_keys:
        selected_keys = tip_keys * (3 // len(tip_keys) + 1)
        selected_keys = selected_keys[:3]
    else:
        selected_keys = []

    time_slots = ["08 WIB", "13 WIB", "19 WIB"]
    selected = list(zip(selected_keys, time_slots))[:3]

    if not selected:
        print("❌ No tips available in template database")
        return

    results = []
    queue = load_queue()

    for idx, (key, time_slot) in enumerate(selected):
        tip = tips[key]
        category = tip.get("category", "general")
        title = tip.get("title", "Untitled")
        body = tip.get("body", "")
        tip_id = tip.get("id", hash(title) % 10000)

        # Build caption from template
        if category in captions:
            c = captions[category]
        elif "default" in captions:
            c = captions["default"]
        else:
            c = "{body}\n\n#{tip_id} #SixZuperLabs"

        if isinstance(c, dict):
            parts = [c.get("header",""), c.get("body","{body}"), c.get("footer","")]
            c = "\n\n".join(p for p in parts if p)

        caption = build_caption(c, title, body, tip_id)

        entry = {
            "id": len(queue["posts"]) + 1,
            "type": "ig_content",
            "tip_id": tip_id,
            "category": category,
            "time_slot": time_slot,
            "title": title,
            "body": body,
            "caption": caption,
            "media_url": f"https://via.placeholder.com/1080x1350?text={title[:30].replace(' ','+')}",
            "status": "draft",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "posted_to": None,
        }
        queue["posts"].append(entry)
        results.append(entry)
        print(f"✅ #{entry['id']:03d} [{entry['time_slot']}] {entry['title']}")

    save_queue(queue)
    print(f"\n📊 Queue: {len(queue['posts'])} total posts")
    print(f"  Draft:  {sum(1 for p in queue['posts'] if p['status']=='draft')}")
    print(f"  Published: {sum(1 for p in queue['posts'] if p['status']!='draft')}")

if __name__ == "__main__":
    main()
