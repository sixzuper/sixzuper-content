#!/bin/bash
# Setup cron job for SixZuper IG Daily Publishing
# Posts every day at 07:00 WIB (00:00 UTC)

CRON_JOB="0 0 * * * /usr/bin/python3 /home/aisixzuperlabs/sixzuper-content/scripts/ig_daily_publish.py >> /home/aisixzuperlabs/sixzuper-content/logs/cron.log 2>&1"

# Add cron job (remove existing if present)
(crontab -l 2>/dev/null | grep -v "ig_daily_publish.py"; echo "$CRON_JOB") | crontab -

echo "✅ Cron job installed: Daily at 07:00 WIB"
crontab -l | grep ig_daily_publish