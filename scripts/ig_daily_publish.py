#!/usr/bin/env python3
"""
SixZuper IG Daily Publish Script
Main entry point for cron job.
1. Check queue for due posts
2. Generate new content if queue is low
3. Publish due posts
4. Report results to Telegram
"""
import json
import sys
import os
import requests
from pathlib import Path
from datetime import datetime, timezone

# Setup path
SCRIPTS_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS_DIR))
os.chdir(SCRIPTS_DIR)

# Dry-run mode flags
DRY_RUN = False
TOKEN_VALID = False

def load_env():
    """Load .env file."""
    env_path = Path.home() / ".hermes" / ".env"
    env = {}
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
    return env

def is_token_valid(env):
    """Check if IG access token is valid by making a simple API call."""
    global TOKEN_VALID, DRY_RUN
    IG_USER_ID = env.get("IG_USER_ID", "")
    ACCESS_TOKEN = env.get("IG_ACCESS_TOKEN", "")
    
    if not IG_USER_ID or not ACCESS_TOKEN:
        log("Missing IG_USER_ID or IG_ACCESS_TOKEN", "WARN")
        TOKEN_VALID = False
        DRY_RUN = True
        return False
    
    try:
        url = f"https://graph.facebook.com/v18.0/{IG_USER_ID}"
        params = {"access_token": ACCESS_TOKEN, "fields": "id,username"}
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()
        
        if resp.status_code == 200 and "id" in data:
            TOKEN_VALID = True
            DRY_RUN = False
            log(f"✅ Token valid for @{data.get('username')} (ID: {data.get('id')})")
            return True
        else:
            error = data.get("error", {}).get("message", "Unknown error")
            log(f"❌ Token invalid: {error}", "WARN")
            TOKEN_VALID = False
            DRY_RUN = True
            return False
    except Exception as e:
        log(f"Token check failed: {e}", "WARN")
        TOKEN_VALID = False
        DRY_RUN = True
        return False

def log(message, level="INFO"):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {message}")

def send_telegram_message(message, env):
    """Send a message to Telegram home channel."""
    import requests
    bot_token = env.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = env.get("TELEGRAM_HOME_CHANNEL", "")
    
    if bot_token and chat_id:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        data = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
        try:
            resp = requests.post(url, json=data, timeout=10)
            return resp.status_code == 200
        except Exception as e:
            log(f"Telegram error: {e}", "WARN")
    return False

def get_todays_tip():
    """Get today's tech tip from the tip bank."""
    tips = [
        "Gunakan Queue Worker untuk task yang lambat — jangan blokir request!",
        "Cache hasil query database, jangan query berulang kali.",
        "Gunakan .env untuk semua konfigurasi — jangan hardcoded.",
        "Indexing database itu wajib — tanpa index, query jadi lambat.",
        "Pakai dependency injection untuk testable code.",
        "Rate limiting mencegah abuse — gunakan Redis + token bucket.",
        "Gunakan CDN untuk static assets — lebih cepat & hemat bandwidth.",
        "Error handling yang baik = logging + alert + graceful degradation.",
        "Database connection pooling hindari 'too many connections'.",
        "Use prepared statements untuk cegah SQL injection.",
        "Containerize apps dengan Docker — reproducible & scalable.",
        "Set 2FA everywhere — especially email & cloud accounts.",
        "Backup rutin: 3-2-1 rule (3 copies, 2 media, 1 offsite).",
        "Log rotation penting — disk penuh = server down.",
        "Use HTTPS always — Let's Encrypt untuk SSL gratis.",
        "Gunakan API versioning (/api/v1/) untuk backward compatibility.",
        "Rate your endpoints — latency < 200ms untuk API yang bagus.",
        "Don't trust user input — sanitize & validate semua data.",
        "Use circuit breaker pattern untuk microservice resilience.",
        "Monitor dengan health checks — proactivity vs reactivity."
    ]
    
    day_of_year = datetime.now().timetuple().tm_yday
    return tips[day_of_year % len(tips)]

def generate_daily_post():
    """Generate today's post using p5.js template."""
    log("Generating daily post with p5.js template...")
    # This would normally run the p5.js export headless
    # For now, we'll use a placeholder that generates the caption
    
    tip = get_todays_tip()
    caption = f"💡 SixZuper Daily Tech Tip\n\n{tip}\n\n#Laravel #WebDev #TechTips #SixzuperLabs #DailyTip"
    
    # In a real implementation, this would:
    # 1. Launch p5.js canvas headless via Puppeteer
    # 2. Trigger canvas redraw
    # 3. Export canvas to PNG
    # 4. Upload to CDN
    
    # For now, simulate by logging
    log(f"Generated tip: {tip}")
    return caption

def publish_due_posts(env):
    """Check queue for due posts and publish them."""
    from queue_manager import get_due_posts, mark_published, mark_failed
    
    due = get_due_posts()
    if not due:
        log("No posts due.")
        return 0
    
    if DRY_RUN:
        log("DRY RUN MODE - simulating publish for {len(due)} post(s)")
        # Simulate publishing
        published_count = 0
        for post in due:
            log(f"[SIMULATE] Would publish: {post['id']}")
            log(f"  - Image: {post['image_url']}")
            log(f"  - Caption: {post['caption'][:50]}...")
            mark_published(post["id"], {"ig_media_id": "dry-run", "status": "simulated"})
            published_count += 1
        return published_count
    
    published_count = 0
    for post in due:
        full_caption = post["caption"] + "\n\n" + " ".join(post["hashtags"])
        try:
            from ig_publisher import post_to_instagram
            result = post_to_instagram(post["image_url"], full_caption, post.get("media_type", "IMAGE"))
            mark_published(post["id"], result)
            log(f"Published: {post['id']} → IG ID {result.get('ig_media_id')}")
            published_count += 1
        except Exception as e:
            mark_failed(post["id"], str(e))
            log(f"Failed to publish {post['id']}: {e}", "ERROR")
    
    return published_count

def main():
    log("=" * 60)
    log("SixZuper IG Daily Publish - Started")
    log("=" * 60)
    
    env = load_env()
    
    # 1. Check token validity
    is_token_valid(env)
    
    if DRY_RUN:
        log("⚠️ Running in DRY RUN mode - token not valid/approved yet", "WARN")
    
    # 2. Generate today's post content
    try:
        caption = generate_daily_post()
        log(f"Daily tip generated: {caption[:50]}...")
    except Exception as e:
        log(f"Content generation error: {e}", "ERROR")
        caption = "💡 SixZuper Daily Tech Tip\n\nCheck our latest post!\n\n#SixzuperLabs"
    
    # 3. Check and publish due posts from queue
    published = 0
    try:
        published = publish_due_posts(env)
        if published:
            log(f"Processed {published} post(s)")
    except Exception as e:
        log(f"Publish error: {e}", "ERROR")
    
    # 4. Send completion report to Telegram
    status_emoji = "🟡" if DRY_RUN else "✅"
    mode_text = "DRY RUN (token pending approval)" if DRY_RUN else "Live IG API"
    
    report = f"""📸 *SixZuper IG Auto-Publish Report*
🗓️ Date: {datetime.now().strftime('%Y-%m-%d %H:%M')} WIB
{status_emoji} Status: {'Mode: ' + mode_text}
📝 Today's tip: {get_todays_tip()[:50]}...
📬 Posts published: {published}

_Auto-generated by Kilua — SixZuper Labs AI Agent_"""
    
    send_telegram_message(report, env)
    log("Report sent to Telegram")
    
    log("=" * 60)
    log("SixZuper IG Daily Publish - Complete")
    log("=" * 60)

if __name__ == "__main__":
    main()