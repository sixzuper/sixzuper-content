#!/usr/bin/env python3
"""
SixZuper Instagram Queue Manager
Manages the content queue for automated posting.
"""
import json
import os
from pathlib import Path
from datetime import datetime, timezone

QUEUE_PATH = Path.home() / "sixzuper-content" / "queue.json"

def _load_queue_file():
    """Load raw queue file content."""
    if not QUEUE_PATH.exists():
        return {"posts": [], "last_updated": datetime.now().isoformat()}
    with open(QUEUE_PATH, "r") as f:
        return json.load(f)

def load_queue():
    """Load the content queue from JSON."""
    data = _load_queue_file()
    if isinstance(data, dict):
        return data.get("posts", [])
    if isinstance(data, list):
        return data
    return []

def save_queue(queue):
    """Save queue back to JSON."""
    data = {"posts": queue, "last_updated": datetime.now().isoformat()}
    with open(QUEUE_PATH, "w") as f:
        json.dump(data, f, indent=2)

def add_to_queue(image_url: str, caption: str, hashtags: list, post_time: str, media_type: str = "IMAGE"):
    """
    Add a post to the queue.
    post_time: ISO format string (e.g. "2026-09-08T08:00:00+07:00")
    """
    queue = load_queue()
    post = {
        "id": f"post_{len(queue) + 1:04d}",
        "image_url": image_url,
        "caption": caption,
        "hashtags": hashtags,
        "post_time": post_time,
        "media_type": media_type,
        "status": "scheduled",
        "created_at": datetime.now().isoformat(),
        "scheduled_publish_time": int(datetime.fromisoformat(post_time).timestamp())
    }
    queue.append(post)
    save_queue(queue)
    print(f"✅ Added to queue: {post['id']}")
    print(f"   Scheduled: {post_time}")
    return post["id"]

def get_due_posts():
    """Get all posts that are due for publishing."""
    queue = load_queue()
    now = datetime.now(timezone.utc)
    due = []
    for post in queue:
        if post["status"] == "scheduled":
            post_time = datetime.fromisoformat(post["post_time"])
            if now >= post_time:
                due.append(post)
    return due

def mark_published(post_id: str, result: dict):
    """Mark a post as published in the queue."""
    queue = load_queue()
    for post in queue:
        if post["id"] == post_id:
            post["status"] = "published"
            post["published_at"] = datetime.now().isoformat()
            post["ig_media_id"] = result.get("ig_media_id")
            post["result"] = result
            break
    save_queue(queue)

def mark_failed(post_id: str, error: str):
    """Mark a post as failed."""
    queue = load_queue()
    for post in queue:
        if post["id"] == post_id:
            post["status"] = "failed"
            post["error"] = error
            post["failed_at"] = datetime.now().isoformat()
            break
    save_queue(queue)

def list_queue():
    """Print queue status."""
    queue = load_queue()
    if not queue:
        print("Queue is empty.")
        return
    print(f"{'ID':<12} {'Status':<12} {'Scheduled':<25} {'Preview'}")
    print("-" * 80)
    for p in queue:
        preview = p["caption"][:30] + "..." if len(p["caption"]) > 30 else p["caption"]
        print(f"{p['id']:<12} {p['status']:<12} {p['post_time']:<25} {preview}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="SixZuper IG Queue Manager")
    parser.add_argument("--list", action="store_true", help="List queue items")
    parser.add_argument("--add", action="store_true", help="Add a new post")
    parser.add_argument("--check", action="store_true", help="Check and publish due posts")
    args = parser.parse_args()

    if args.list:
        list_queue()
    elif args.add:
        image = input("Image URL: ")
        caption = input("Caption: ")
        hashtags = input("Hashtags (comma-separated): ").split(",")
        post_time = input("Post time (ISO format, e.g. 2026-09-08T08:00:00+07:00): ")
        add_to_queue(image, caption, hashtags, post_time)
    elif args.check:
        due = get_due_posts()
        if not due:
            print("No posts due.")
        else:
            from ig_publisher import post_to_instagram
            for post in due:
                full_caption = post["caption"] + "\n\n" + " ".join(post["hashtags"])
                try:
                    result = post_to_instagram(post["image_url"], full_caption, post["media_type"])
                    mark_published(post["id"], result)
                    print(f"✅ Published: {post['id']}")
                except Exception as e:
                    mark_failed(post["id"], str(e))
                    print(f"❌ Failed: {post['id']} - {e}")
    else:
        parser.print_help()