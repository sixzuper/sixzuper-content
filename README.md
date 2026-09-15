# SixZuper Instagram Edukasi Automation Pipeline

Pipeline otomatis untuk generate, schedule, dan publish konten edukasi ke Instagram SixZuper (instagram.com/sixzuper) yang dikelola oleh **Agent Six (Kilua)** menggunakan Hermes Agent.

## ✨ Fitur

- 🎨 **Content Generation**: p5.js quote cards, Manim math explainers, ComfyUI image gen
- ⏰ **Scheduled Publishing**: Hermes cron job (daily 07:00 WIB)
- 📱 **Review Workflow**: Telegram preview → approve → publish (via Topics)
- 📊 **Analytics**: Auto-collect post metrics
- 🔁 **Auto-refresh**: Long-lived token renewal (60-day rolling)
- 🤖 **Telegram Bot**: Topic-based command routing in "Mr. R & Agent Six" group

## 📁 Struktur Direktori (Updated)

```
sixzuper-content/
├── telegram_bot.py           # Telegram Bot API handler (aiogram)
├── templates/
│   ├── edu_quote_card.html   # p5.js quote card generator
│   └── reel_template.html    # Reels template
├── topics/
│   ├── content_drafts.py     # Draft management commands (/draft, /publish, /edit)
│   ├── analytics.py          # Stats tracking commands (/stats, /top-posts)
│   └── automation.py         # Cron logs commands (/status, /cron, /health)
├── scripts/
│   ├── ig_publisher.py       # IG Graph API publisher
│   ├── ig_daily_publish.py   # Cron entry point
│   ├── queue_manager.py      # Content queue management
│   ├── tips_database.py      # Tech tips database (42 tips)
│   └── setup_cron.sh         # Cron installation
├── systemd/
│   ├── telegram_bot.service   # Bot systemd unit
│   └── ig-daily-publish.service
├── data/
│   └── post_templates.json   # Caption templates by category
├── queue.json                # Post queue (schedule)
├── publish_log.jsonl         # Publish history
└── README.md

~/.hermes/.env                # Credentials (TELEGRAM_BOT_TOKEN, IG_*)
```

## 🤖 Telegram Bot Workflow

### Bot Info
- **Bot Name**: `@agentaisix_bot` (Agent AI Kilua)
- **Group**: Mr. R & Agent Six (`t.me/c/3934372713`)
- **Polling**: Auto-restart via `@reboot` cron

### Topic Structure & Commands

| Topic | Commands | Purpose |
|-------|----------|---------|
| 📢 **Announcements** | `/ann <text>`, `/all <text>` | Pin announcements, broadcast |
| 🎨 **Content Drafts** | `/draft <topic>`, `/publish`, `/edit <text>` | Generate, review, approve drafts |
| ⚙️ **Automation Logs** | `/status`, `/cron`, `/health` | System/cron status, health check |
| 📊 **Analytics** | `/stats`, `/top-posts [n]` | Post metrics, top performers |
| 💡 **Tech Tips Archive** | `/tips <category\|random\|list>`, `/archive <id>` | Tech tip library |

### Draft Workflow
```
[Daily 07:00 WIB] → Bot generates post → Sends to "Content Drafts" topic
   ↓
🤖 "[DRAFT #147] Ready for review" + image preview
📝 Caption: "..."
   ↓
Pa Ricky replies: ✅ /publish  ✏️ /edit  ❌ /skip
   ↓
Bot posts to IG + logs to "Analytics" topic
```

### Bot Commands Detail

#### `/draft [category|random]`
- Generates new content draft from template
- Categories: laravel, php, security, devops, performance, architecture, tools, system_design, database, docker, api, testing, general

#### `/publish`
- Approves current draft (reply to draft message)
- Logs to publish_log.jsonl
- Updates queue status

#### `/edit <caption>`
- Edits current draft caption (reply to draft message)

#### `/status`
- Shows cron job status
- IG token presence
- Queue length

#### `/health`
- System: disk, RAM, CPU
- Last automation log entry

#### `/tips [category|random|list]`
- Retrieves tech tip from database (15 tips across 12 categories)

#### `/stats`
- Total posts, published, failed
- Success rate

## 🔧 Setup Instructions

### 1. Bot Deployment
```bash
# Create venv
python3 -m venv .venv --system-site-packages
source .venv/bin/activate
pip install aiogram==3.5.0 psutil

# Start manually
python3 telegram_bot.py

# Or via cron @reboot
crontab -e
# @reboot /home/aisixzuperlabs/sixzuper-content/scripts/start_bot.sh
```

### 2. Content Template Structure
Templates stored in `data/post_templates.json`:
- **tips**: 15 tech tips by category (laravel, php, security, devops, performance, architecture, tools, system_design, database, docker, api, testing, general)
- **captions**: 14 caption styles with header/body/footer template

### 3. Environment Variables (`~/.hermes/.env`)
```env
TELEGRAM_BOT_TOKEN=8592188693:****
TELEGRAM_CHAT_ID=-1003934372713
TELEGRAM_ALLOWED_USERS=974026313,8716283831
TG_HOME_CHANNEL=974026313
IG_USER_ID=17841434496070749
IG_APP_ID=1401337335500035
IG_APP_SECRET=6f77147c4cb29263e1daf6ede4466324
IG_ACCESS_TOKEN=EAABsbCS1i...
IG_CDN_BASE=https://raw.githubusercontent.com/sixzuper/sixzuper-content/main/media
```

### 4. Queue Management
```bash
# Add post
python3 scripts/queue_manager.py --add

# List queue
python3 scripts/queue_manager.py --list

# Check due posts
python3 scripts/queue_manager.py --check
```

## 🚀 Usage

### Generate Post Manual
```bash
# Via Telegram bot command
# /draft laravel
# /draft random

# Or edit caption template
# /edit New caption text here
```

### Force Publish Due Posts
```bash
python3 scripts/ig_daily_publish.py
```

### Get Today's Tech Tip
```bash
python3 scripts/tips_database.py
# Atau via bot: /tips random
```

## 📊 Tech Tips Database

Database berisi 15 tech tips terbagi per kategori:

| Kategori | Tips Count |
|----------|-----------|
| Laravel / PHP | 2 |
| Architecture / DevOps | 2 |
| Security | 1 |
| Performance | 1 |
| System Design | 2 |
| Tools | 2 |
| Database | 1 |
| Docker | 1 |
| API | 1 |
| Testing | 1 |
| General | 2 |

## ⚠️ Security

- `.env` file hanya berisi credentials (jangan commit ke git)
- Bot token dan IG credentials di `~/.hermes/.env`
- Gunakan long-lived token (60 hari), bukan short-lived (2 jam)
- Semua media melalui HTTPS (CDN requirement)
- Rate limit IG API (~50 posts/day maksimal)

## 📞 Support

Pipeline ini dikelola oleh **Agent Six (Kilua)** — Hermes Agent di SixZuper Labs.

---
*Made with ❤️ by Kilua — SixZuper Labs AI Agent*
