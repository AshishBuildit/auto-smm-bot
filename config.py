from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


def _require(key: str) -> str:
    value = os.getenv(key, "").strip()
    if not value:
        raise ValueError(f"Missing required environment variable: {key}")
    return value


@dataclass
class Config:
    bot_token: str = field(default_factory=lambda: _require("BOT_TOKEN"))
    smm_api_key: str = field(default_factory=lambda: _require("SMM_API_KEY"))
    telegram_api_id: int = field(default_factory=lambda: int(_require("TELEGRAM_API_ID")))
    telegram_api_hash: str = field(default_factory=lambda: _require("TELEGRAM_API_HASH"))
    telegram_phone: str = field(default_factory=lambda: _require("TELEGRAM_PHONE"))
    allowed_user_id: int = field(default_factory=lambda: int(_require("ALLOWED_USER_ID")))
    default_post_count: int = field(default_factory=lambda: int(os.getenv("DEFAULT_POST_COUNT", "10")))
    smm_api_url: str = "https://prm4u.com/api/v2"
    db_path: str = "bot_data.db"
    session_name: str = "telethon_session"


# Singleton instance
config = Config()
