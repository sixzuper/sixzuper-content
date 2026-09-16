#!/bin/bash
# SixZuper IG Bot auto-startup via cron @reboot
# Avoids systemd user-session issues on headless STB
cd /home/aisixzuperlabs/sixzuper-content
export XDG_RUNTIME_DIR=/run/user/$(id -u)
# Kill stale instances first
pkill -f "telegram_bot.py" 2>/dev/null
sleep 1
# Start fresh
nohup /home/aisixzuperlabs/sixzuper-content/.venv/bin/python3 telegram_bot.py >> logs/bot_polling.log 2>> logs/bot_error.log &
echo $! > /home/aisixzuperlabs/sixzuper-content/logs/bot.pid
