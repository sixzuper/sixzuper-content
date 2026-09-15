"""
Analytics Topic Handler
Commands: /stats, /top-posts

Tracks and displays Instagram post performance metrics.
"""

import json
import logging
from datetime import datetime
from pathlib import Path

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

log = logging.getLogger("topics.analytics")

CONTENT_DIR = Path(__file__).parent.parent
LOG_FILE = CONTENT_DIR / "logs" / "publish_log.jsonl"

router = Router()


def load_publish_log() -> list:
    entries = []
    if LOG_FILE.exists():
        for line in LOG_FILE.read_text().splitlines():
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return entries


@router.message(Command(commands=["stats"]))
async def cmd_stats(message: Message):
    """Show post performance stats from publish log."""
    entries = load_publish_log()
    total = len(entries)

    if total == 0:
        await message.answer(
            "📊 **Analytics Report**\n\n"
            "📭 No posts published yet.\n"
            "Start by generating a draft with `/draft`"
        )
        return

    published = [e for e in entries if e.get("status") == "published"]
    failed = [e for e in entries if e.get("status") == "failed"]
    skipped = [e for e in entries if e.get("status") == "skipped"]

    success_rate = (len(published) / total * 100) if total > 0 else 0

    # Group by category
    by_category = {}
    for e in published:
        cat = e.get("category", "unknown")
        by_category[cat] = by_category.get(cat, 0) + 1

    cat_breakdown = "\n".join(
        f"  • `{cat}`: {count}" for cat, count in sorted(by_category.items(), key=lambda x: -x[1])
    ) or "  _No data_"

    await message.answer(
        f"📊 **Analytics Report**\n\n"
        f"📦 Total Entries: `{total}`\n"
        f"✅ Published: `{len(published)}`\n"
        f"❌ Failed: `{len(failed)}`\n"
        f"⏭️ Skipped: `{len(skipped)}`\n"
        f"📈 Success Rate: `{success_rate:.1f}%`\n\n"
        f"📂 **By Category:**\n{cat_breakdown}\n\n"
        f"📊 Use /top-posts to see best performers"
    )
    log.info("📊 Stats shown: total=%d published=%d", total, len(published))


@router.message(Command(commands=["top-posts"]))
async def cmd_top_posts(message: Message):
    """Show top N posts by some metric."""
    # Parse args manually (aiogram 3.x compatible)
    text = message.text or ""
    parts = text.split()
    n = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 5

    entries = load_publish_log()
    if not entries:
        await message.answer("📭 No post history available.")
        return

    # Sort by most recent (future: sort by IG engagement metrics)
    recent = sorted(entries, key=lambda x: x.get("timestamp", ""), reverse=True)[:n]

    if not recent:
        await message.answer("📭 No posts to show.")
        return

    lines = []
    for i, e in enumerate(recent, 1):
        date_str = e.get("timestamp", "")[:10]
        status_emoji = "✅" if e.get("status") == "published" else "❌" if e.get("status") == "failed" else "⏭️"
        lines.append(
            f"{i}. {status_emoji} **{e.get('title', 'Untitled')}** "
            f"`[{e.get('category', '?')}]` · {date_str}"
        )

    top_text = "\n".join(lines)

    await message.answer(
        f"🏆 **Top {n} Recent Posts:**\n\n{top_text}\n\n"
        f"_Sorted by recency. Engagement metrics coming soon._"
    )
    log.info("🏆 Top posts shown: count=%d", len(recent))
