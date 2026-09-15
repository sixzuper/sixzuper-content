#!/usr/bin/env python3
"""
SixZuper IG Content Pipeline - Telegram Bot Handler
Agent Six (Kilua) — Hermes Agent

Bot untuk manage konten IG SixZuper via Telegram Topics.
Support per-topic commands:
  📢 Announcements     -> /ann, /all
  🎨 Content Drafts    -> /draft, /publish, /edit
  ⚙️ Automation Logs   -> /status, /cron, /health
  📊 Analytics        -> /stats, /top-posts
  💡 Tech Tips Archive  -> /tips, /archive
"""

import json
import logging
import os
import sys
from pathlib import Path
from datetime import datetime

# Ensure topics/ package is importable
sys.path.insert(0, str(Path(__file__).resolve().parent))

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from aiogram.exceptions import TelegramBadRequest

# === Config ===
ENV_PATH = Path.home() / ".hermes" / ".env"
CONTENT_DIR = Path(__file__).resolve().parent
QUEUE_FILE = CONTENT_DIR / "queue.json"
LOG_FILE = CONTENT_DIR / "logs" / "automation.log"
POST_TEMPLATES = CONTENT_DIR / "data" / "post_templates.json"

# Setup logging
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("tg_bot")

ALLOWED_USERS: dict[int, str] = {}


def load_env() -> dict:
    env = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    for key in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_HOME_CHANNEL", "TELEGRAM_ALLOWED_USERS"):
        if os.getenv(key):
            env[key] = os.getenv(key)
    return env


def get_env(key: str, default: str = "") -> str:
    return os.getenv(key, "").strip() or load_env().get(key, default)


BOT_TOKEN = get_env("TELEGRAM_BOT_TOKEN")
CHAT_ID = -1003934372713  # IG SIXZUPER group
WEBHOOK_PORT = 8080
WEBHOOK_HOST = "0.0.0.0"
WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"


def init_allowed_users():
    raw = get_env("TELEGRAM_ALLOWED_USERS", "")
    if not raw:
        return {}
    for entry in raw.split(","):
        entry = entry.strip()
        if ":" in entry:
            uid, name = entry.split(":", 1)
            ALLOWED_USERS[int(uid)] = name
        elif entry.isdigit():
            ALLOWED_USERS[int(entry)] = f"user_{entry}"
    return ALLOWED_USERS


async def cmd_start(message: Message):
    user_id = message.from_user.id if message.from_user else 0
    if user_id not in ALLOWED_USERS:
        await message.answer("❌ Akses ditolak.")
        return

    text = (
        "🤖 **Agent Six — IG Edukasi Pipeline**\n\n"
        "📱 *Available Commands:*\n\n"
        "📢 `/ann <text>` | `/all <text>`\n"
        "🎨 `/draft <topic|random>` | `/publish` | `/edit <text>` | `/skip`\n"
        "⚙️ `/status` | `/cron` | `/health`\n"
        "📊 `/stats` | `/top-posts [n]`\n"
        "💡 `/tips <cat|random|list>`"
    )
    await message.answer(text, parse_mode="Markdown")


def setup_handlers(dp: Dispatcher):
    dp.message.register(cmd_start, CommandStart())

    from topics.content_drafts import router as drafts_router
    from topics.analytics import router as analytics_router
    from topics.automation import router as automation_router

    dp.include_router(drafts_router)
    dp.include_router(analytics_router)
    dp.include_router(automation_router)

    log.info("✅ Handlers registered: /start + 3 topic routers")


async def on_startup(bot: Bot):
    me = await bot.me()
    log.info("🤖 %s (@%s) started", me.full_name, me.username)
    log.info("📱 Connected to chat: IG SIXZUPER (%d)", CHAT_ID)
    init_allowed_users()
    log.info("👥 Allowed users: %d", len(ALLOWED_USERS))
    # Set webhook — conflict-free mode
    webhook_url = f"https://{get_env('DOMAIN', 'hermes.nousresearch.com')}{WEBHOOK_PATH}"
    log.info("🔗 Webhook URL: %s", webhook_url)


async def on_shutdown(bot: Bot):
    log.info("🛑 Bot shutting down...")


def main():
    global bot, dp

    if not BOT_TOKEN:
        log.error("❌ TELEGRAM_BOT_TOKEN not found")
        sys.exit(1)

    bot = Bot(token=BOT_TOKEN, parse_mode="HTML")
    dp = Dispatcher()
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    setup_handlers(dp)

    log.info("🚀 Starting bot loop...")
    dp.run_polling(bot, skip_updates=True, drop_pending_updates=True)


if __name__ == "__main__":
    main()
