#!/usr/bin/env python3
"""
SixZuper IG — Publish latest draft_ready queue entry to Instagram Graph API.

Usage:
  python3 ig_publish_draft.py [--dry-run]

Uses public GitHub raw media URLs (no local upload needed). Publishes via
two-step IG Graph API flow (create container -> media_publish) and writes
results to logs/publish_log.jsonl + updates queue.json status.
"""
import argparse
import json
import sys
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

CONTENT_DIR = Path(__file__).resolve().parents[1]
QUEUE_FILE = CONTENT_DIR / "queue.json"
LOG_FILE = CONTENT_DIR / "logs" / "publish_log.jsonl"
GITHUB_CDN = "https://raw.githubusercontent.com/sixzuper/sixzuper-content/main/media/stb_hermes_tip_007.png"
ENV_PATH = Path.home() / ".hermes" / ".env"
GRAPH = "https://graph.facebook.com/v18.0"


def load_env() -> dict:
    env: dict[str, str] = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


def graph_api(method: str, path: str, token: str, params: dict | None = None) -> dict:
    """Call Meta Graph API and always send the caller's access token."""
    url = f"{GRAPH}/{path}"
    payload = dict(params or {})
    payload["access_token"] = token
    data = urllib.parse.urlencode(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        return {"error": {"message": f"HTTP {e.code}", "body": body[:600]}}


def get_latest_draft() -> dict | None:
    if not QUEUE_FILE.exists():
        print("❌ queue.json not found")
        return None
    q = json.loads(QUEUE_FILE.read_text(encoding="utf-8"))
    posts = q["posts"] if isinstance(q, dict) else q
    drafts = [p for p in posts if isinstance(p, dict) and p.get("status") == "draft_ready"]
    return drafts[-1] if drafts else None


def build_caption(post: dict) -> tuple[str, list[str]]:
    title = post.get("title", "SixZuper Tech Tip")
    body = post.get("body", "")
    hashtags = ["#SixZuper", "#IGAutoPublish", "#TechTips", "#LearnWithAI", "#WebDev"]
    caption = f"🧪 SixZuper Daily Tech Tip — {title}\n\n{body}\n\nSimpan post ini untuk referensi! 💾\n\n" + " ".join(hashtags)
    return caption, hashtags


def publish(post: dict, env: dict, dry_run: bool) -> dict:
    caption, hashtags = build_caption(post)
    candidate_url = post.get("image_url") or post.get("media_url") or ""
    # Placeholder providers can reject Meta's fetcher; use verified GitHub CDN media.
    image_url = GITHUB_CDN if (not candidate_url or "placeholder.com" in candidate_url) else candidate_url
    ig_uid = env.get("IG_USER_ID", "")
    tok = env.get("IG_ACCESS_TOKEN", "")

    if not ig_uid or not tok:
        return {"error": {"message": "Missing IG_USER_ID or IG_ACCESS_TOKEN in .env"}}

    print(f"📤 Publishing: '{post.get('title')}'")
    print(f"   image_url={image_url}")
    print(f"   caption_len={len(caption)}")

    if dry_run:
        return {"status": "dry_run", "dry_run_caption_preview": caption[:150]}

    print("Step 1: Creating media container...")
    c = graph_api("POST", f"{ig_uid}/media", tok, {
        "image_url": image_url,
        "caption": caption,
    })
    if "error" in c:
        return {"error": c["error"]}
    creation_id = c["id"]
    print(f"   Container ID: {creation_id}")

    print("Step 2: Publishing media container...")
    p = graph_api("POST", f"{ig_uid}/media_publish", tok, {"creation_id": creation_id})
    if "error" in p:
        return {"error": p["error"]}

    result = {
        "ig_media_id": p.get("id"),
        "creation_id": creation_id,
        "image_url": image_url,
        "caption_preview": caption[:150],
        "published_at": datetime.now(timezone.utc).isoformat(),
        "status": "success",
    }

    # Append log
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(result) + "\n")

    # Update queue: mark this post + update status in place
    q = json.loads(QUEUE_FILE.read_text(encoding="utf-8"))
    posts = q["posts"] if isinstance(q, dict) else q
    for x in posts:
        if x.get("id") == post.get("id"):
            x["status"] = "published"
            x["published_at"] = result["published_at"]
            x["ig_media_id"] = result["ig_media_id"]
            x["image_url"] = image_url
            x["caption"] = caption
    if isinstance(q, dict):
        q["posts"] = posts
        q["last_updated"] = datetime.now(timezone.utc).isoformat()
        QUEUE_FILE.write_text(json.dumps(q, ensure_ascii=False, indent=2) + "\n")
    else:
        QUEUE_FILE.write_text(json.dumps(posts, ensure_ascii=False, indent=2) + "\n")

    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    env = load_env()
    post = get_latest_draft()
    if not post:
        print("📭 No draft_ready posts. Run 'generate 3x daily sixzuper content' first.")
        print("Atau: publish to IG now — akan gunakan placeholder content.")
        return

    res = publish(post, env, args.dry_run)
    print(json.dumps(res, indent=2, ensure_ascii=False))
    if res.get("status") == "success":
        print("✅ Published to Instagram! IG Media ID:", res.get("ig_media_id"))
    elif res.get("status") == "dry_run":
        print("🧪 Dry-run complete — would publish above.")
    else:
        print("❌ Publish failed:", json.dumps(res.get("error", {}), ensure_ascii=False))


if __name__ == "__main__":
    main()
