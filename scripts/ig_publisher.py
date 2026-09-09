#!/usr/bin/env python3
"""
IG Publisher - Two-step publish flow via Instagram Graph API
Two steps:
  1. POST /{ig_user_id}/media → creates media container
  2. POST /{ig_user_id}/media_publish → publishes container

Supports image posts (feed) and reels (video).
"""
import requests
import os
import sys
import json
from datetime import datetime
from pathlib import Path

# Load .env manually (simple parser)
def load_env():
    env_path = Path.home() / ".hermes" / ".env"
    env = {}
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
    # Also load OS env as fallback
    env.update({k: v for k, v in os.environ.items() if k in ("IG_USER_ID", "IG_APP_ID", "IG_APP_SECRET", "IG_ACCESS_TOKEN", "IG_CDN_BASE")})
    return env

def get_long_lived_token(short_token: str, app_id: str, app_secret: str) -> str:
    """Exchange short-lived token for long-lived (60-day) token."""
    url = "https://graph.facebook.com/v18.0/oauth/access_token"
    params = {
        "grant_type": "fb_exchange_token",
        "client_id": app_id,
        "client_secret": app_secret,
        "fb_exchange_token": short_token
    }
    resp = requests.get(url, params=params)
    data = resp.json()
    if "access_token" in data:
        return data["access_token"]
    else:
        raise Exception(f"Token exchange failed: {data.get('error', {}).get('message', data)}")

def refresh_long_lived_token(long_token: str, app_id: str, app_secret: str) -> dict:
    """Refresh a long-lived token before it expires (rolling 60-day renewal)."""
    url = "https://graph.facebook.com/v18.0/oauth/access_token"
    params = {
        "grant_type": "fb_exchange_token",
        "client_id": app_id,
        "client_secret": app_secret,
        "fb_exchange_token": long_token
    }
    resp = requests.get(url, params=params)
    return resp.json()

def create_media_container(base_url: str, access_token: str, ig_user_id: str,
                           media_type: str = "IMAGE",
                           image_url: str = None,
                           video_url: str = None,
                           caption: str = "",
                           location_id: str = None,
                           thumb_offset: int = 0) -> str:
    """
    Step 1: Create a media container.
    Returns container creation_id.
    """
    url = f"{base_url}/{ig_user_id}/media"
    payload = {
        "access_token": access_token,
        "caption": caption,
    }

    if media_type == "IMAGE":
        payload["image_url"] = image_url
    elif media_type == "REELS":
        payload["media_type"] = "REELS"
        payload["video_url"] = video_url
    elif media_type == "CAROUSEL":
        payload["media_type"] = "CAROUSEL"
        payload["children"] = image_url  # comma-separated media IDs

    if location_id:
        payload["location_id"] = location_id

    resp = requests.post(url, data=payload)
    data = resp.json()
    if "id" in data:
        return data["id"]
    else:
        raise Exception(f"Media container creation failed: {data}")

def publish_media_container(base_url: str, access_token: str, ig_user_id: str, creation_id: str) -> dict:
    """
    Step 2: Publish the media container.
    Returns dict with 'id' (IG media ID) and 'caption'.
    """
    url = f"{base_url}/{ig_user_id}/media_publish"
    payload = {
        "access_token": access_token,
        "creation_id": creation_id
    }
    resp = requests.post(url, data=payload)
    data = resp.json()
    if "id" in data:
        return data
    else:
        raise Exception(f"Media publish failed: {data}")

def post_to_instagram(image_url: str, caption: str, media_type: str = "IMAGE") -> dict:
    """
    Complete two-step publish flow.
    image_url must be publicly accessible HTTPS URL.
    """
    env = load_env()
    IG_USER_ID = env.get("IG_USER_ID")
    ACCESS_TOKEN = env.get("IG_ACCESS_TOKEN")
    BASE_URL = "https://graph.facebook.com/v18.0"

    if not all([IG_USER_ID, ACCESS_TOKEN]):
        raise Exception("Missing IG_USER_ID or IG_ACCESS_TOKEN in environment")

    # Step 1: Create container
    print(f"📤 Step 1: Creating media container...")
    creation_id = create_media_container(
        BASE_URL, ACCESS_TOKEN, IG_USER_ID,
        media_type=media_type,
        image_url=image_url if media_type == "IMAGE" else None,
        video_url=image_url if media_type == "REELS" else None,
        caption=caption
    )
    print(f"   Container ID: {creation_id}")

    # Step 2: Publish container
    print(f"📥 Step 2: Publishing media...")
    result = publish_media_container(BASE_URL, ACCESS_TOKEN, IG_USER_ID, creation_id)
    print(f"   Published! IG Media ID: {result.get('id', 'N/A')}")

    # Log the result
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "ig_media_id": result.get("id"),
        "creation_id": creation_id,
        "caption": caption[:100],
        "media_type": media_type,
        "image_url": image_url,
        "status": "published"
    }

    log_path = Path.home() / "sixzuper-content" / "publish_log.jsonl"
    with open(log_path, "a") as f:
        f.write(json.dumps(log_entry) + "\n")

    return {
        "ig_media_id": result.get("id"),
        "creation_id": creation_id,
        "status": "success",
        "published_at": datetime.now().isoformat()
    }

def schedule_post(media_container_id: str, scheduled_publish_time: int) -> dict:
    """
    Schedule a post for later (requires published=false on container creation).
    scheduled_publish_time is UNIX timestamp.
    """
    env = load_env()
    IG_USER_ID = env.get("IG_USER_ID")
    ACCESS_TOKEN = env.get("IG_ACCESS_TOKEN")
    BASE_URL = "https://graph.facebook.com/v18.0"

    url = f"{BASE_URL}/{IG_USER_ID}/media"
    payload = {
        "access_token": ACCESS_TOKEN,
        "creation_id": media_container_id,
        "published": "false",
        "scheduled_publish_time": str(scheduled_publish_time)
    }

    resp = requests.post(url, data=payload)
    return resp.json()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Publish Instagram post via Graph API")
    parser.add_argument("--image-url", required=True, help="Public HTTPS URL to the image")
    parser.add_argument("--caption", required=True, help="Post caption")
    parser.add_argument("--media-type", default="IMAGE", choices=["IMAGE", "REELS"], help="Media type")

    args = parser.parse_args()

    result = post_to_instagram(args.image_url, args.caption, args.media_type)
    print(json.dumps(result, indent=2))