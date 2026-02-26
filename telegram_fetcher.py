"""Fetch recent post URLs from a public Telegram channel using Telethon (MTProto).

OTP and 2FA are handled through the Telegram bot interface — no terminal prompts
are ever shown after the first successful authentication.
"""
from __future__ import annotations

import asyncio
import logging
import re

from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from telethon.tl.types import Message, MessageService

from config import config

logger = logging.getLogger(__name__)

# Matches: @username  |  t.me/username  |  https://t.me/username
_CHANNEL_RE = re.compile(
    r"(?:https?://)?(?:t\.me/|telegram\.me/)?@?([A-Za-z0-9_]{3,})"
)


def _extract_username(channel_input: str) -> str:
    """Extract bare username from any channel URL / @handle format."""
    m = _CHANNEL_RE.search(channel_input.strip())
    if not m:
        raise ValueError(f"Cannot parse channel identifier: {channel_input!r}")
    return m.group(1)


class ChannelFetcher:
    """Wraps a Telethon TelegramClient to fetch post links from public channels.

    Authentication (OTP + optional 2FA password) is completed entirely through
    the Telegram bot so no terminal interaction is ever required.
    """

    def __init__(self) -> None:
        self._client: TelegramClient = TelegramClient(
            config.session_name,
            config.telegram_api_id,
            config.telegram_api_hash,
        )
        self._code_queue: asyncio.Queue[str] = asyncio.Queue(maxsize=1)
        self._password_queue: asyncio.Queue[str] = asyncio.Queue(maxsize=1)
        self._waiting_for_code: bool = False
        self._waiting_for_password: bool = False

    # ------------------------------------------------------------------
    # Properties used by bot handlers to route text input
    # ------------------------------------------------------------------

    @property
    def waiting_for_code(self) -> bool:
        return self._waiting_for_code

    @property
    def waiting_for_password(self) -> bool:
        return self._waiting_for_password

    # ------------------------------------------------------------------
    # Called by bot handlers to feed auth tokens back to Telethon
    # ------------------------------------------------------------------

    async def provide_code(self, code: str) -> None:
        await self._code_queue.put(code)

    async def provide_password(self, password: str) -> None:
        await self._password_queue.put(password)

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    async def start(self, bot=None) -> bool:
        """Connect and authorise the Telethon client.

        If the session file is valid the authorisation is silent.
        Otherwise the bot sends the owner a prompt for the OTP (and
        optional 2FA password) and waits for it to be sent back through
        the bot.

        Args:
            bot: aiogram ``Bot`` instance used to message the owner.

        Returns:
            ``True`` if the session was already valid, ``False`` if a
            fresh login was performed.
        """
        await self._client.connect()

        if await self._client.is_user_authorized():
            logger.info("Telethon client already authorised (session valid).")
            return True

        # ── Need fresh authentication ──────────────────────────────────
        logger.info("Telethon auth required — requesting code for %s", config.telegram_phone)
        await self._client.send_code_request(config.telegram_phone)

        if bot:
            await bot.send_message(
                config.allowed_user_id,
                "🔐 <b>Telegram Auth Required</b>\n\n"
                f"A login code was sent to <code>{config.telegram_phone}</code>.\n"
                "Please send the code here (digits only, e.g. <code>12345</code>):",
                parse_mode="HTML",
            )

        self._waiting_for_code = True
        try:
            code = await self._code_queue.get()
        finally:
            self._waiting_for_code = False

        try:
            await self._client.sign_in(config.telegram_phone, code)
        except SessionPasswordNeededError:
            if bot:
                await bot.send_message(
                    config.allowed_user_id,
                    "🔑 <b>2FA Password Required</b>\n\n"
                    "Your account has Two-Factor Authentication enabled.\n"
                    "Please send your <b>cloud password</b> here:",
                    parse_mode="HTML",
                )
            self._waiting_for_password = True
            try:
                password = await self._password_queue.get()
            finally:
                self._waiting_for_password = False

            await self._client.sign_in(password=password)

        logger.info("Telethon client authorised successfully.")
        return False

    async def stop(self) -> None:
        """Disconnect the Telethon client cleanly."""
        await self._client.disconnect()

    async def fetch_post_urls(self, channel_input: str, count: int | None = None) -> list[str]:
        """Return the *count* most recent post URLs from *channel_input*.

        Args:
            channel_input: Channel URL (https://t.me/name), @name, or bare username.
            count: Number of posts to fetch. Defaults to config.default_post_count.

        Returns:
            List of full post URLs like ``https://t.me/channel/12345``.
        """
        if count is None:
            count = config.default_post_count

        username = _extract_username(channel_input)

        try:
            entity = await self._client.get_entity(username)
        except Exception as exc:
            logger.error("Could not resolve channel %r: %s", username, exc)
            raise ValueError(f"Cannot find channel '{username}'. Make sure it is public.") from exc

        # get_messages returns newest-first; request extra to absorb any service
        # messages (channel creation, pinned announcements, etc.) so the caller
        # always gets exactly `count` real posts.
        messages = await self._client.get_messages(entity, limit=count + 10)

        urls: list[str] = []
        for msg in messages:
            if isinstance(msg, MessageService):
                continue  # skip service messages (channel created, pinned, etc.)
            if msg.id:
                urls.append(f"https://t.me/{username}/{msg.id}")
            if len(urls) >= count:
                break

        logger.info("Fetched %d post URLs from @%s", len(urls), username)
        return urls


# Singleton instance
channel_fetcher = ChannelFetcher()
