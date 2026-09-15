"""
Automation Logs Topic Handler
Commands: /status, /cron, /health

Provides system status, cron management, and health reports
for the IG content pipeline.
"""

import json
import logging
import os
import shutil
import subprocess
from pathlib import Path

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

try:
    import psutil
except ImportError:
    psutil = None

log = logging.getLogger("topics.automation")

CONTENT_DIR = Path(__file__).parent.parent
QUEUE_FILE = CONTENT_DIR / "queue.json"
LOG_FILE = CONTENT_DIR / "logs" / "automation.log"

router = Router()


def get_cron_status() -> tuple[str, str]:
    """Check current cron jobs for IG daily publish."""
    try:
        cron_output = subprocess.check_output(
            ["crontab", "-l"],
            stderr=subprocess.DEVNULL
        ).decode()
        ig_cron = [line for line in cron_output.splitlines() if "ig_daily_publish" in line]
        if ig_cron:
            return "✅ Active", ig_cron[0].strip()
        return "⚠️ Not Found", ""
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "⚠️ Cron not accessible", ""


def get_token_status() -> str:
    """Check if IG access token exists in env."""
    env_path = Path.home() / ".hermes" / ".env"
    if not env_path.exists():
        return "❌ .env not found"

    env_content = env_path.read_text()
    has_token = "IG_ACCESS_TOKEN=" in env_content and len(env_content.split("IG_ACCESS_TOKEN=")[1].strip()) > 10
    has_user_id = "IG_USER_ID=" in env_content
    has_app_id = "IG_APP_ID=" in env_content

    if has_token and has_user_id and has_app_id:
        return "✅ All credentials present"
    elif has_token:
        return "⚠️ Token present, missing other vars"
    else:
        return "❌ Token missing"


@router.message(Command(commands=["status"]))
async def cmd_status(message: Message):
    """Show cron + token + queue status."""
    cron_status, cron_line = get_cron_status()
    token_status = get_token_status()

    # Queue info
    queue_info = "0 posts"
    if QUEUE_FILE.exists():
        q = json.loads(QUEUE_FILE.read_text())
        drafts = len([p for p in q.get("posts", []) if p.get("status") == "draft"])
        published = len([p for p in q.get("posts", []) if p.get("status") == "published"])
        queue_info = f"{drafts} drafts, {published} published"

    await message.answer(
        f"⚙️ **Automation Status**\n\n"
        f"⏱️ **Cron Job:** {cron_status}\n"
        f"  `{cron_line or 'N/A'}`\n\n"
        f"🔑 **IG Token:** {token_status}\n\n"
        f"📋 **Queue:** {queue_info}\n\n"
        f"🕐 Last updated: {json.loads(QUEUE_FILE.read_text()).get('last_updated', 'N/A') if QUEUE_FILE.exists() else 'N/A'}"
    )
    log.info("⚙️ Status checked")


@router.message(Command(commands=["cron"]))
async def cmd_cron(message: Message):
    """Enable/disable cron job."""
    # Parse args manually (aiogram 3.x compatible)
    text = message.text or ""
    parts = text.split()
    args = parts[1].lower() if len(parts) > 1 else ""
    if args not in ("enable", "disable", "", "status"):
        await message.answer("Usage: `/cron enable|disable|status`", parse_mode="Markdown")
        return

    cron_status, cron_line = get_cron_status()

    if args == "enable":
        cron_entry = "0 0 * * * /usr/bin/python3 /home/aisixzuperlabs/sixzuper-content/scripts/ig_daily_publish.py >> /home/aisixzuperlabs/sixzuper-content/logs/cron.log 2>&1"
        try:
            existing = subprocess.check_output(["crontab", "-l"], stderr=subprocess.DEVNULL).decode()
            new_cron = existing.strip() + "\n" + cron_entry + "\n"
            proc = subprocess.Popen(["crontab", "-"], stdin=subprocess.PIPE)
            proc.communicate(input=new_cron.encode())
            cron_status = "✅ Enabled"
        except Exception as e:
            await message.answer(f"❌ Failed to enable cron: {e}")
            return

        await message.answer(
            f"⏱️ **Cron Job Status:** {cron_status}\n\n"
            f"Entry:\n`{cron_entry}`"
        )

    elif args == "disable":
        try:
            existing = subprocess.check_output(["crontab", "-l"], stderr=subprocess.DEVNULL).decode()
            lines = [l for l in existing.splitlines() if "ig_daily_publish" not in l]
            proc = subprocess.Popen(["crontab", "-"], stdin=subprocess.PIPE)
            proc.communicate(input=("\n".join(lines) + "\n").encode())
            cron_status = "❌ Disabled"
        except Exception as e:
            await message.answer(f"❌ Failed to disable cron: {e}")
            return

        await message.answer(f"⏱️ **Cron Job Status:** {cron_status}\n\nDisabled daily IG publishing.")

    elif args == "status" or not args:
        await message.answer(
            f"⏱️ **Cron Job Status:** {cron_status}\n\n"
            f"Entry:\n`{cron_line or 'No IG cron job found'}`\n\n"
            f"💡 Use `/cron enable` or `/cron disable`"
        )

    log.info("⏱️ Cron command: %s", args or "status")


@router.message(Command(commands=["health"]))
async def cmd_health(message: Message):
    """Show system health report."""
    if psutil is None:
        await message.answer("⚠️ psutil not installed for health check.")
        return

    disk = shutil.disk_usage("/")
    mem = psutil.virtual_memory()
    cpu = psutil.cpu_percent(interval=0.5)
    boot_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    # Load log stats
    log_lines = 0
    last_log = "No logs"
    if LOG_FILE.exists():
        log_content = LOG_FILE.read_text()
        log_lines = len(log_content.splitlines())
        last_log = log_content.strip().splitlines()[-1][-120:] if log_content.strip() else "No logs"

    await message.answer(
        f"🖥️ **System Health Report**\n\n"
        f"🕐 Uptime: {boot_time}\n\n"
        f"💾 **Disk:**\n"
        f"  Used: {disk.used / (1024**3):.1f}GB\n"
        f"  Free: {disk.free / (1024**3):.1f}GB\n"
        f"  Usage: {disk.used / disk.total * 100:.1f}%\n\n"
        f"🧠 **RAM:**\n"
        f"  Used: {mem.used / (1024**3):.1f}GB\n"
        f"  Total: {mem.total / (1024**3):.1f}GB\n"
        f"  Usage: {mem.percent}%\n\n"
        f"🏭 **CPU:** {cpu}%\n\n"
        f"📝 **Logs:** {log_lines} lines\n"
        f"  Last: `{last_log}`"
    )
    log.info("🖥️ Health report sent")
