#!/usr/bin/env python3
"""SixZuper IG — One-command 'publish to IG now' pipeline.

Usage:
  python3 ig_publish_draft.py            # publish latest brand-approved draft now
  python3 ig_publish_draft.py --dry-run  # preview only

Standard workflow (this is now the Kilua default for IG publishing):
  1. Generate text-free background image via image model.
  2. Overlay branded 1080x1350 card with render_premium_card.py.
  3. Upload PNG to GitHub repo, obtain raw CDN URL.
  4. Set that URL as the draft's `image_url` in queue.json.
  5. Run this script: two-step IG Graph API publish (create container -> publish).
  6. Script marks the queue item `published` + reads back IG media ID.

Fail-safe: if `image_url` is missing or is a placeholder, the script refuses to
publish and tells the caller exactly which step to complete first.
"""
from __future__ import annotations

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
ENV_PATH = Path.home() / ".hermes" / ".env"
GRAPH = "https://graph.facebook.com/v18.0"

# Default brand asset used only for the first smoke test. In production every
# draft carries its own image_url; this constant is never used as a publishable
# fallback because the script fails closed when image_url is a placeholder.
DEFAULT_CDN = (
    "https://raw.githubusercontent.com/sixzuper/sixzuper-content/main"
    "/media/stb_hermes_tip_007.png"
)


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


def graph_api(method: str, path: str, token: str, params: dict | None = None) -> dict:
    """Call Meta Graph API. The access_token is always sent in the POST body."""
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
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(body)
        except Exception:
            parsed = {"message": body[:600]}
        return {"error": parsed.get("error", {"message": f"HTTP {exc.code}: {parsed}"})}


def get_latest_draft() -> dict | None:
    if not QUEUE_FILE.exists():
        print("[ERROR] queue.json not found")
        return None
    q = json.loads(QUEUE_FILE.read_text(encoding="utf-8"))
    posts = q["posts"] if isinstance(q, dict) else q
    drafts = [p for p in posts if isinstance(p, dict) and p.get("status") == "draft_ready"]
    return drafts[-1] if drafts else None


def build_caption(post: dict) -> tuple[str, list[str]]:
    title = post.get("title") or "SixZuper Tech Tip"
    body = post.get("body") or post.get("content") or "Daily practical tech tip from SixZuper."
    hashtags = ["#SixZuper", "#IGAutoPublish", "#TechTips", "#LearnWithAI", "#WebDev"]
    caption = (
        f"🧪 SixZuper Daily Tech Tip — {title}\n\n{body}\n\n"
        f"Simpan post ini untuk referensi! 💾\n\n" + " ".join(hashtags)
    )
    return caption, hashtags


def publish(post: dict, env: dict, dry_run: bool) -> dict:
    caption, _hashtags = build_caption(post)

    # Fail closed: every publishable draft must carry a real, public HTTPS image.
    candidate_url = post.get("image_url") or post.get("media_url") or ""
    if not candidate_url or "placeholder.com" in candidate_url:
        return {
            "error": {
                "message": (
                    "No approved branded CDN image. Generate the premium visual with "
                    "render_premium_card.py, upload the PNG to the GitHub repo, then set "
                    "image_url before publishing."
                )
            }
        }
    if not candidate_url.startswith("https://"):
        return {"error": {"message": "image_url must be a public HTTPS URL."}}
    image_url = candidate_url

    ig_uid = env.get("IG_USER_ID", "")
    tok = env.get("IG_ACCESS_TOKEN", "")
    if not ig_uid or not tok:
        return {"error": {"message": "Missing IG_USER_ID or IG_ACCESS_TOKEN in .env"}}

    print(f"📤 Publishing: '{post.get('title')}'")
    print(f"   image_url={image_url}")
    print(f"   caption_len={len(caption)}")

    if dry_run:
        return {"status": "dry_run", "dry_run_caption_preview": caption[:150]}

    print("📥 Step 1: Creating media container...")
    c = graph_api("POST", f"{ig_uid}/media", tok, {"image_url": image_url, "caption": caption})
    if "error" in c:
        return {"error": c["error"]}
    creation_id = c["id"]
    print(f"   Container ID: {creation_id}")

    print("📥 Step 2: Publishing media container...")
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

    # Append to publish_log.jsonl
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(result, ensure_ascii=False) + "\n")

    # Update queue in place, matched by stable id.
    q = json.loads(QUEUE_FILE.read_text(encoding="utf-8"))
    posts = q["posts"] if isinstance(q, dict) else q
    updated = False
    for x in posts:
        if isinstance(x, dict) and str(x.get("id")) == str(post.get("id")):
            x["status"] = "published"
            x["published_at"] = result["published_at"]
            x["ig_media_id"] = result["ig_media_id"]
            x["image_url"] = image_url
            x["caption"] = caption
            updated = True
    if updated:
        if isinstance(q, dict):
            q["posts"] = posts
            q["last_updated"] = datetime.now(timezone.utc).isoformat()
            QUEUE_FILE.write_text(
                json.dumps(q, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
        else:
            QUEUE_FILE.write_text(
                json.dumps(posts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )

    return result


def main() -> int:
    ap = argparse.ArgumentParser(description="Publish latest SixZuper IG draft.")
    ap.add_argument("--dry-run", action="store_true", help="Preview only, no API call")
    args = ap.parse_args()

    env = load_env()
    post = get_latest_draft()
    if not post:
        print("[INFO] No draft_ready posts. Generate content first with:")
        print("       generate 3x daily sixzuper content")
        return 0

    res = publish(post, env, args.dry_run)
    print(json.dumps(res, indent=2, ensure_ascii=False))
    if res.get("status") == "success":
        print(f"[OK] Published to Instagram! IG Media ID: {res.get('ig_media_id')}")
        return 0
    elif res.get("status") == "dry_run":
        print("[DRY] Dry-run complete — would publish above.")
        return 0
    else:
        print(f"[FAIL] Publish failed: {json.dumps(res.get('error', {}), ensure_ascii=False)}")
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
