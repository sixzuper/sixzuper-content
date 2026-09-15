#!/bin/bash
# Auto-start telegram bot on boot
# Run: crontab -e -> @reboot /home/aisixzuperlabs/sixzuper-content/scripts/start_bot.sh
export HOME="/home/aisixzuperlabs"
cd /home/aisixzuperlabs/sixzuper-content

# Activate venv
source .venv/bin/activate

# Kill existing instance (clean start)
pkill -9 -f "python3.*telegram_bot.py" 2>/dev/null
sleep 2

# Start bot with venv python (drop_pending_updates clears stale polling session)
nohup python3 -u telegram_bot.py >> logs/bot.log 2>&1 &
echo "Bot started with PID $! (venv python: $(which python3))"
