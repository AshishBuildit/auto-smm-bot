# Auto-SMM Bot

A personal, single-user Telegram bot that automates ordering **subscribers**, **views**, and **reactions** for your Telegram channels via the [PRM4U](https://prm4u.com) SMM panel API.

> **Personal use only.** The bot only responds to one configured Telegram user ID. All other users are silently ignored.

---

## Features

- **Three order modes** — Subscribers only · Views + Reactions · All three at once
- **Auto post fetching** — Paste a channel URL; the bot fetches your latest posts via Telethon (MTProto) and applies views/reactions to each one automatically
- **Presets** — Save reusable order configurations (service IDs + quantities). One channel URL → one tap → full boost applied
- **Order tracking** — Auto push-notifications when order status changes (polled every 60 s), `/status <id>`, and paginated `/history`
- **INR pricing** — All balances and charges are shown in ₹ INR using the live USD→INR exchange rate
- **In-bot Telethon auth** — First-time OTP and 2FA password are requested inside the bot chat, never in the terminal
- **Bot commands auto-registered** — `/` command menu appears automatically without any BotFather setup
- **Docker-ready** — Single `docker compose up -d --build` deploys everything on a VPS

---

## Technology Stack

| Layer | Library |
|---|---|
| Telegram bot framework | [aiogram 3.x](https://docs.aiogram.dev/) |
| Telegram MTProto client | [Telethon](https://docs.telethon.dev/) |
| SMM panel | [PRM4U API v2](https://prm4u.com/api) |
| HTTP client | aiohttp |
| Database | SQLite via aiosqlite |
| Config | python-dotenv |

---

## Quick Start (Local)

### 1. Clone the repo

```bash
git clone https://github.com/your-username/auto-smm-bot.git
cd auto-smm-bot
```

### 2. Create your `.env`

```bash
cp .env.example .env
```

Fill in all values in `.env`:

```ini
BOT_TOKEN=          # from @BotFather
SMM_API_KEY=        # from prm4u.com → API page
TELEGRAM_API_ID=    # from https://my.telegram.org → App
TELEGRAM_API_HASH=
TELEGRAM_PHONE=+919876543210
ALLOWED_USER_ID=    # your Telegram user ID (get from @userinfobot)
DEFAULT_POST_COUNT=10
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

Requires **Python 3.10+**

### 4. Run

```bash
python bot.py
```

On first run, if no Telethon session exists, the bot will **message you inside the bot** asking for the OTP sent to your phone. Type the code in the chat — no terminal interaction needed. After login a `telethon_session.session` file is saved and all future startups are silent.

---

## Deploying on a VPS with Docker

### Prerequisites

- Docker and Docker Compose installed on the VPS  
  (`curl -fsSL https://get.docker.com | sh`)

### Steps

```bash
# 1. Clone the repo
git clone https://github.com/your-username/auto-smm-bot.git
cd auto-smm-bot

# 2. Create your secrets file
cp .env.example .env
nano .env          # fill in all values

# 3. Pre-create empty mount files
#    (if skipped, Docker creates them as directories)
touch bot_data.db telethon_session.session

# 4. Build and start in the background
docker compose up -d --build

# 5. Watch logs — first-time Telethon auth prompt appears here
docker compose logs -f bot
```

On first launch the bot sends you an OTP request **inside the bot chat**. Reply with the code. The session is saved to `telethon_session.session` on the host via the volume mount — container restarts will not require re-authentication.

### Useful commands

```bash
docker compose logs -f bot        # live logs
docker compose restart bot        # restart without rebuilding
docker compose up -d --build      # rebuild after code changes
docker compose down               # stop and remove containers
```

---

## Bot Commands

| Command | Description |
|---|---|
| `/start` | Main menu |
| `/order` | Start a new order (or just send a channel URL) |
| `/presets` | Create, list, or delete presets |
| `/balance` | Check your SMM panel balance in ₹ INR |
| `/status <order_id>` | Check the status of any order |
| `/history` | Paginated order history |
| `/cancel` | Cancel any ongoing conversation |
| `/help` | Show command list |

**Shortcut:** Send `https://t.me/yourchannel` or `@yourchannel` at any time to jump straight to the order flow.

---

## File Structure

```
auto-smm-bot/
├── bot.py                   ← Entry point, startup/shutdown, command registration
├── config.py                ← Loads .env into a typed dataclass
├── database.py              ← SQLite schema + async queries (aiosqlite)
├── smm_api.py               ← Async PRM4U API wrapper + live INR rate fetch
├── telegram_fetcher.py      ← Telethon post URL fetcher + in-bot OTP auth
├── handlers/
│   ├── auth.py              ← Intercepts OTP/2FA input during Telethon auth
│   ├── start.py             ← /start, /help, /balance
│   ├── order.py             ← Full order FSM
│   ├── presets.py           ← Preset management FSM
│   └── status.py            ← /status, /history
├── keyboards/
│   └── inline.py            ← Inline keyboard builders
├── states/
│   └── fsm.py               ← FSM state groups
├── tasks/
│   └── tracker.py           ← Background order status poller
├── Dockerfile
├── docker-compose.yml
├── .env.example             ← Copy to .env and fill in secrets
├── .gitignore
└── requirements.txt
```

---

## Finding Service IDs

Log in to [prm4u.com](https://prm4u.com), go to **Services**, filter by *Telegram*, and note the numeric IDs for the subscriber / views / reactions packages you want to use. These IDs are entered when creating orders or presets.

---

## Usage Flow

### Quick order

1. Send `@mychannel` or `https://t.me/mychannel`
2. Choose mode: Subscribers / Views+Reactions / All Three / Use Preset
3. Enter service IDs and quantities when prompted
4. Confirm — orders are placed immediately
5. The bot notifies you when each order status changes

### Using a preset

1. `/presets` → **New Preset** — configure service IDs, quantities, and post count
2. Name it (e.g. `daily_boost`)
3. Send a channel URL → **Use a Preset** → select `daily_boost`
4. One confirmation tap — all orders placed instantly

---

## License

MIT


---

## Features

- **Three order modes** — Subscribers only · Views + Reactions · All three at once
- **Auto post fetching** — Give the bot a channel URL; it fetches your latest posts via Telethon (MTProto) and applies views/reactions to each one automatically
- **Presets** — Save reusable order configurations (service IDs + quantities). Fire a full boost with a single channel link
- **Order history & status** — Paginated order history, `/status <id>` command, and automatic push-notifications when an order changes state (polled every 60 s)
- **Single-user lock** — The bot only responds to your Telegram user ID

---

## Technology Stack

| Layer | Library |
|---|---|
| Telegram bot framework | [aiogram 3.x](https://docs.aiogram.dev/) |
| Telegram MTProto client | [Telethon](https://docs.telethon.dev/) |
| SMM panel | [PRM4U API v2](https://prm4u.com/api) |
| HTTP client | aiohttp |
| Database | SQLite via aiosqlite |
| Config | python-dotenv |

---

## Setup

### 1. Clone / open the project

```
d:\Projects\auto-smm-bot\
```

### 2. Create your `.env` file

Copy `.env.example` to `.env` and fill in all values:

```ini
BOT_TOKEN=        # from @BotFather
SMM_API_KEY=      # from prm4u.com → API
TELEGRAM_API_ID=  # from https://my.telegram.org → App
TELEGRAM_API_HASH=
TELEGRAM_PHONE=+1234567890
ALLOWED_USER_ID=  # your Telegram user ID (get from @userinfobot)
DEFAULT_POST_COUNT=10
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

> Requires **Python 3.10+**

### 4. Authorise Telethon (one-time)

The first time you run the bot, Telethon needs to create a session file. Run:

```bash
python bot.py
```

If no session file exists, it will prompt you in the terminal:

```
Please enter your phone (or bot token): +1234567890
Please enter the code you received: 12345
```

After this a `telethon_session.session` file is created. Subsequent startups are silent.

### 5. Run

```bash
python bot.py
```

---

## Bot Commands

| Command | Description |
|---|---|
| `/start` | Main menu |
| `/order` | Start a new order (or just send a channel URL directly) |
| `/presets` | Create, list, or delete presets |
| `/balance` | Check your SMM panel balance |
| `/status <order_id>` | Check the status of any order |
| `/history` | Paginated order history |
| `/cancel` | Cancel any ongoing conversation |
| `/help` | Show command list |

**Shortcut:** Send `https://t.me/yourchannel` or `@yourchannel` at any time to jump straight to the order flow.

---

## File Structure

```
auto-smm-bot/
├── bot.py                 ← Entry point
├── config.py              ← Loads .env into a dataclass
├── database.py            ← SQLite schema + async queries
├── smm_api.py             ← Async PRM4U API wrapper
├── telegram_fetcher.py    ← Telethon post URL fetcher
├── handlers/
│   ├── start.py           ← /start, /help, /balance
│   ├── order.py           ← Full order FSM
│   ├── presets.py         ← Preset management FSM
│   └── status.py          ← /status, /history
├── keyboards/
│   └── inline.py          ← Inline keyboard builders
├── states/
│   └── fsm.py             ← FSM state groups
├── tasks/
│   └── tracker.py         ← Background order poller
├── .env                   ← Secrets (never commit this)
├── .env.example
└── requirements.txt
```

---

## Usage Flow

### Quick order

1. Send `@mychannel` (or `https://t.me/mychannel`)
2. Choose mode: Subscribers / Views+Reactions / All Three / Use Preset
3. Enter service IDs and quantities when prompted
4. Confirm — orders are placed immediately
5. The bot notifies you when each order completes

### Using a preset

1. `/presets` → **New Preset** — configure service IDs, quantities, and post count
2. Give it a name (e.g. `daily_boost`)
3. Next time, send a channel URL and choose **Use a Preset → daily_boost**
4. One confirmation tap — done

---

## Finding Service IDs

Log in to [prm4u.com](https://prm4u.com), go to **Services**, filter by *Telegram*, and find the service IDs for the subscriber/views/reactions packages you want to use.
