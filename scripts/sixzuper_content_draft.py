#!/usr/bin/env python3
"""
SixZuper IG Daily Draft Generator (6Z-DG-1)
=============================================
Generate 3 Instagram daily drafts (08:00 / 13:00 / 19:00 WIB):
  - DALL·E text-to-image prompts (cyberpunk / neon-blue theme)
  - 3 caption variants (long / short / cta-only)
  - Themes: tech tip | behind-scene | community | inspiration | infra hack

Delivers to Telegram forum topic #3 for Pa Ricky review.
Cron: 0 5 * * * hermes cron run sixzuper-content-draft
"""
import json, random, urllib.request, urllib.error
from pathlib import Path
from datetime import datetime, timezone

# ── Paths ──────────────────────────────────────────────────────────────────
CONTENT_DIR = Path("/home/aisixzuperlabs/sixzuper-content")
ENV_PATH    = Path.home() / ".hermes" / ".env"
DRAFTS_DIR  = CONTENT_DIR / "drafts"
QUEUE_FILE  = CONTENT_DIR / "queue.json"
LOG_FILE    = CONTENT_DIR / "logs" / "automation.log"
TEMPLATES   = CONTENT_DIR / "data" / "post_templates.json"

# ── Telegram targets ───────────────────────────────────────────────────────
CHAT_ID   = -1003934372713   # IG SIXZUPER group
THREAD_ID = 3                 # forum topic #3

# ── Time slots ──────────────────────────────────────────────────────────────
TIME_SLOTS = ["08:00 WIB", "13:00 WIB", "19:00 WIB"]

# ── Theme rotation (cycles daily) ───────────────────────────────────────────
THEMES_CYCLE = ["tech tip", "behind-scene", "community", "inspiration", "infra hack"]


# ═══════════════════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════════════════

def load_env() -> dict:
    """Load .hermes/.env (never logs secrets)."""
    env = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text().splitlines():
            line = line.strip()
            if line and "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    # env vars override file
    for key in ("TELEGRAM_BOT_TOKEN",):
        if os.getenv(key):
            env[key] = os.getenv(key)
    return env


def log_msg(msg: str, level: str = "INFO"):
    """Write to automation.log + stdout."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    entry = f"{ts} [{level}] {msg}"
    print(entry)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(entry + "\n")


def tg_api(bot_token: str, method: str, data: dict) -> dict:
    """Raw Telegram Bot API call (no aiogram dependency)."""
    url = f"https://api.telegram.org/bot{bot_token}/{method}"
    req = urllib.request.Request(url, data=json.dumps(data).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return {"ok": False, "error_code": e.code,
                "description": e.read().decode()}


def load_post_templates() -> dict:
    """Load tips database from post_templates.json."""
    if TEMPLATES.exists():
        return json.loads(TEMPLATES.read_text())
    return {"tips": {}, "captions": {}}


def build_dalle_prompt(category: str, title: str, body: str, theme: str) -> str:
    """Generate a cyberpunk-style DALL·E prompt for the given tech tip."""
    # Extract key visual concept from title
    slug = title.lower().replace(" ", " ").replace(":", "")

    prompts = {
        "laravel": "Cyberpunk neon-blue terminal screen showing Laravel Eloquent ORM with glowing code snippets, database connection visualized as pulsing fiber-optic lines, dark matrix-style background, futuristic HUD overlay, clean vector art style, 1080x1080 Instagram square",
        "php": "Minimalist cyberpunk illustration of PHP code transforming into running application, neon-blue syntax highlighting on dark terminal background, abstract gears and circuits, glowing particles, 1080x1080 square format",
        "security": "Cyberpunk neon-blue security shield icon made of intersecting code brackets and holographic barriers, dark background with pulsing purple and cyan electric arcs, digital lock pattern overlay, technical illustration, 1080x1080",
        "devops": "Isometric cyberpunk scene of DevOps pipeline visualization — servers, gears, CI/CD arrows in neon-blue and electric purple, dark industrial tech aesthetic, holographic data flow lines, 1080x1080",
        "performance": "Abstract performance optimization visualization: neon-blue speedometer, loading bars, rocket trajectory chart on dark digital background with glitch effects, cyberpunk style, 1080x1080",
        "architecture": "Cyberpunk isometric building diagram: clean architecture layers stacked vertically with neon-blue glow between tiers, code brackets as structural beams, dark tech aesthetic, 1080x1080",
        "tools": "Minimalist cyberpunk terminal interface showing SSH config file with neon-blue monospace text, dark matrix background with particle stream, HUD-style UI elements, clean vector art, 1080x1080",
        "system_design": "Database indexing infographic in cyberpunk style: indexed columns as lit neon-blue pathways, non-indexed as dark gray, 3D infographic with holographic bars, dark tech background, 1080x1080",
        "database": "Redis cache illustration: fast neon-blue data stream flowing from Redis icon to database server, showing cache-aside pattern with arrows, cyberpunk color palette on dark background, 1080x1080",
        "docker": "Cyberpunk Docker container visualization: stacked neon-blue container layers with transparent walls showing internal processes, dark background with digital particle effects, isometric 3D view, 1080x1080",
        "api": "Minimalist API gateway illustration with neon-blue request/response flow arrows, circuit-board background with glowing connections, cyberpunk HUD overlay, isometric vector art, 1080x1080",
        "testing": "Test pyramid diagram in cyberpunk style: neon-blue layers from unit (bottom) to E2E (top), glowing pyramid structure floating on dark matrix background, digital particle effects, 1080x1080",
        "general": "Clean cyberpunk tech illustration: abstract code brackets, neon-blue terminal glyphs on dark background with digital noise, minimalist style, 1080x1080",
        "random": "Abstract Git branch visualization: neon-blue timeline branches diverging and converging with glowing commit hashes, dark digital background with particle stream, technical illustration, 1080x1080",
    }
    base = prompts.get(category, prompts["general"])
    if "cyberpunk" not in base and "neon" not in base:
        base = base + " cyberpunk neon-blue aesthetic"
    return base


def build_captions(tip_id: int, category: str, title: str, body: str) -> dict:
    """Generate 3 caption variants: long / short / cta-only."""
    emoji_map = {
        "laravel": "🐘", "php": "🐘", "security": "🔐", "devops": "⚙️",
        "performance": "🚀", "architecture": "🏗️", "tools": "🛠️",
        "system_design": "🏛️", "database": "🗄️", "docker": "🐋",
        "api": "🌐", "testing": "🧪", "general": "💡", "random": "💡",
    }
    emoji = emoji_map.get(category, "💡")
    hashtag_map = {
        "laravel": "#Laravel #PHP #SixZuper #DevTips",
        "php": "#PHP #SixZuper #CodeTips",
        "security": "#Security #SixZuper #DevSecOps",
        "devops": "#DevOps #SixZuper #Git #CICD",
        "performance": "#Performance #SixZuper #Optimization",
        "architecture": "#Architecture #SixZuper #DesignPatterns",
        "tools": "#Tools #SixZuper #DeveloperSetup",
        "system_design": "#SystemDesign #SixZuper #Scalability",
        "database": "#Database #SQL #SixZuper #Redis",
        "docker": "#Docker #SixZuper #Containerization",
        "api": "#API #REST #SixZuper #WebDev",
        "testing": "#Testing #TDD #SixZuper #Quality",
        "general": "#CodeTips #SixZuper #Developer",
        "random": "#TechTips #SixZuper #Developer #CodeTips",
    }
    tags = hashtag_map.get(category, "#TechTips #SixZuper #DevTips")

    # LONG caption
    long_cap = f"{emoji} *Tip #{tip_id} — {title}*\n\n{body}\n\n📌 {tags}"

    # SHORT caption — trimmed body
    short_body = body[:200].rsplit("\n", 1)[0] if len(body) > 200 else body
    short_cap = f"{emoji} *Tip #{tip_id} — {title}*\n\n{short_body}\n\n📌 {tags}"

    # CTA-only caption
    cta_cap = f"💾 Simpan post ini untuk referensi nanti!\n📌 {tags}"

    return {"long": long_cap, "short": short_cap, "cta_only": cta_cap}


def select_tips_for_day() -> list:
    """Pick 3 distinct random tips from the template bank."""
    templates = load_post_templates()
    tips = templates.get("tips", {})
    tip_values = list(tips.values())
    if not tip_values:
        return []
    if len(tip_values) >= 3:
        return random.sample(tip_values, 3)
    else:
        # duplicate if fewer than 3
        pool = (tip_values * 2)[:3]
        return pool


def generate_drafts() -> dict:
    """Generate 3 IG drafts for 08/13/19 WIB."""
    tips = select_tips_for_day()
    if not tips:
        log_msg("ERROR: No tips available in post_templates.json", "ERROR")
        return {}

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    # Determine theme rotation for today
    day_of_year = datetime.now(timezone.utc).timetuple().tm_yday
    base_theme = THEMES_CYCLE[day_of_year % len(THEMES_CYCLE)]

    posts = []
    for idx, tip in enumerate(tips):
        tip_id     = tip.get("id", hash(tip.get("title", "")) % 10000)
        category   = tip.get("category", "general")
        title      = tip.get("title", "Untitled")
        body       = tip.get("body", "")

        # Determine theme for this slot
        theme = THEMES_CYCLE[(day_of_year + idx) % len(THEMES_CYCLE)]

        dalle_prompt   = build_dalle_prompt(category, title, body, theme)
        captions       = build_captions(tip_id, category, title, body)
        media_url      = f"https://via.placeholder.com/1080x1080/0a0a2e/00d4ff?text={title[:40].replace(' ', '+').replace('/', '-')}"

        post = {
            "slot":      TIME_SLOTS[idx],
            "theme":     theme,
            "slug_label": f"📍 Slot {idx+1}/{len(tips)}",
            "tip_id":    tip_id,
            "category":  category,
            "title":     title,
            "body":      body,
            "dalle_prompt": dalle_prompt,
            "captions":  captions,
            "media_url": media_url,
        }
        posts.append(post)
        log_msg(f"Generated draft: {TIME_SLOTS[idx]} | {emoji_for_log(category)} {title}")

    draft_data = {
        "generated_at": f"{today}T{datetime.now(timezone.utc).strftime('%H:%M:%S')}+00:00",
        "generated_date": today,
        "generator": "sixzuper-content-draft v1.0 (Agent Six/Kilua)",
        "theme_base": base_theme,
        "posts": posts,
    }

    # Save draft file
    draft_file = DRAFTS_DIR / f"ig_draft_{today.replace('-', '')}.json"
    DRAFTS_DIR.mkdir(parents=True, exist_ok=True)
    draft_file.write_text(json.dumps(draft_data, indent=2, ensure_ascii=False))
    log_msg(f"Draft saved: {draft_file.name} ({len(posts)} posts)")

    return draft_data


def emoji_for_log(category: str) -> str:
    _map = {"laravel": "🐘", "php": "🐘", "security": "🔐", "devops": "⚙️",
            "performance": "🚀", "architecture": "🏗️", "tools": "🛠️",
            "system_design": "🏛️", "database": "🗄️", "docker": "🐋",
            "api": "🌐", "testing": "🧪", "general": "💡", "random": "💡"}
    return _map.get(category, "💡")


# ═══════════════════════════════════════════════════════════════════════════
#  Delivery
# ═══════════════════════════════════════════════════════════════════════════

def deliver_to_telegram(draft_data: dict) -> dict:
    """Send 3 drafts to Telegram forum topic #3 via Bot API (no bot process needed)."""
    env = load_env()
    bot_token = env.get("TELEGRAM_BOT_TOKEN", "")
    if not bot_token:
        log_msg("ERROR: TELEGRAM_BOT_TOKEN not found in .env", "ERROR")
        return {"ok": False, "error": "no_token"}

    posts = draft_data.get("posts", [])
    generated_at = draft_data.get("generated_at", "")

    # ── Message 1: Header ──
    header_lines = [
        "📱 <b>SixZuper IG Daily Content Draft</b>",
        f"<b>🗓️ {generated_at}</b>",
        "<b>📤 Forum Topic #3 — Review for Pa Ricky</b>",
        "",
        f"<b>Total Posts: {len(posts)}</b>",
        "",
    ]
    for p in posts:
        header_lines.append("━━━━━━━━━━━━━━")
        header_lines.append(f"<b>⏰ {p['slot']}</b>")
        header_lines.append(f"<b>📍 {p['theme'].title()} | Tip #{p['tip_id']} | {p['category'].upper()} | {p['title']}</b>")
        header_lines.append("")

    header_text = "\n".join(header_lines)
    hdr_payload = {
        "chat_id": CHAT_ID,
        "message_thread_id": THREAD_ID,
        "text": header_text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    r1 = tg_api(bot_token, "sendMessage", hdr_payload)
    if not r1.get("ok"):
        log_msg(f"ERROR: Header delivery failed: {r1.get('description', r1)}", "ERROR")
        return {"ok": False, "error": r1}
    header_msg_id = r1["result"]["message_id"]
    log_msg(f"📤 Header delivered to topic #3 (msg_id={header_msg_id})")

    # ── Messages 2-N: Individual posts ──
    msg_ids = []
    for p in posts:
        lines = [
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            f"<b>⏰ {p['slot']}</b>",
            f"<b>📍 {p['theme'].title()} | Tip #{p['tip_id']} | {p['category'].upper()}</b>",
            f"<b>💡 {p['title']}</b>",
            "",
            f"<b>🎨 DALL·E Prompt:</b>",
            f"<code>{p['dalle_prompt']}</code>",
            "",
            f"<b>📝 Caption [LONG]:</b>",
            f"<pre>{p['captions']['long'][:1500]}</pre>",
            "",
            f"<b>📝 Caption [SHORT]:</b>",
            f"<pre>{p['captions']['short'][:1500]}</pre>",
            "",
            f"<b>📝 Caption [CTA-ONLY]:</b>",
            f"<pre>{p['captions']['cta_only']}</pre>",
            "",
            f"<b>📄 Body (full):</b>",
            f"<pre>{p['body'][:1500]}</pre>",
        ]
        msg_text = "\n".join(lines)
        payload = {
            "chat_id": CHAT_ID,
            "message_thread_id": THREAD_ID,
            "text": msg_text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        r = tg_api(bot_token, "sendMessage", payload)
        if r.get("ok"):
            mid = r["result"]["message_id"]
            msg_ids.append(mid)
            log_msg(f"📤 Post {p['slot']} delivered (msg_id={mid})")
        else:
            log_msg(f"ERROR: Failed {p['slot']}: {r.get('description', r)}", "ERROR")
            msg_ids.append(None)

    # ── Footer ──
    footer = (
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "✅ <b>3 IG drafts ready.</b>\n"
        "Reply /publish to approve · /edit to modify · /skip to discard.\n"
        "📸 <b>Cyberpunk · Neon-Blue · Ready for Omni Flash</b>"
    )
    rf = tg_api(bot_token, "sendMessage", {
        "chat_id": CHAT_ID, "message_thread_id": THREAD_ID,
        "text": footer, "parse_mode": "HTML",
        "disable_web_page_preview": True,
    })
    log_msg(f"📤 Footer delivered (msg_id={rf.get('result',{}).get('message_id','?')})")

    return {"ok": True, "header_msg_id": header_msg_id, "post_msg_ids": msg_ids}


def update_queue(draft_data: dict, delivery_result: dict):
    """Append draft entries to queue.json."""
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if QUEUE_FILE.exists():
        queue = json.loads(QUEUE_FILE.read_text())
    else:
        queue = {"posts": [], "last_updated": ""}

    posts = draft_data.get("posts", [])
    msg_ids = delivery_result.get("post_msg_ids", [])
    draft_file = f"ig_draft_{draft_data['generated_date'].replace('-', '')}.json"

    for idx, p in enumerate(posts):
        entry = {
            "id":        len(queue["posts"]) + 1,
            "type":      "ig_draft",
            "tip_id":    p["tip_id"],
            "category":  p["category"],
            "title":     p["title"],
            "body":      p["body"],
            "dalle_prompt": p["dalle_prompt"],
            "captions":  p["captions"],
            "slot":      p["slot"],
            "theme":     p["theme"],
            "slug_label": p["slug_label"],
            "media_url": p["media_url"],
            "draft_file": draft_file,
            "created_at": now_utc,
            "status":    "draft_ready",
            "posted_msg_id": msg_ids[idx] if idx < len(msg_ids) else None,
            "posted_thread_id": THREAD_ID,
            "posted_chat_id": CHAT_ID,
        }
        queue["posts"].append(entry)

    queue["last_updated"] = now_utc
    QUEUE_FILE.write_text(json.dumps(queue, indent=2, ensure_ascii=False))
    log_msg(f"📋 Queue updated: {len(queue['posts'])} total entries")


# ═══════════════════════════════════════════════════════════════════════════
#  Main
# ═══════════════════════════════════════════════════════════════════════════
import os

def main():
    log_msg("=" * 60)
    log_msg("SixZuper IG Daily Draft Generator — Started")
    log_msg("=" * 60)

    # 1. Generate drafts
    draft_data = generate_drafts()
    if not draft_data:
        log_msg("No drafts generated. Exiting.", "ERROR")
        return

    # 2. Deliver to Telegram forum topic #3
    delivery = deliver_to_telegram(draft_data)

    # 3. Update queue
    update_queue(draft_data, delivery)

    log_msg("=" * 60)
    log_msg("SixZuper IG Daily Draft — Complete ✅")
    log_msg("=" * 60)


if __name__ == "__main__":
    main()
