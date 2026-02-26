"""Handles Telethon OTP / 2FA input routed through the bot.

This router is registered *first* in bot.py so it takes priority over all
other text handlers when the Telethon client is waiting for an auth token.
The filter ensures it only activates during auth — normal messages are
never intercepted.
"""
from __future__ import annotations

import logging

from aiogram import Router
from aiogram.filters import BaseFilter
from aiogram.types import Message

from config import config
from telegram_fetcher import channel_fetcher

logger = logging.getLogger(__name__)
router = Router(name="auth")

_ALLOWED = config.allowed_user_id


class _WaitingForAuth(BaseFilter):
    """True only while Telethon needs OTP or 2FA password from the owner."""

    async def __call__(self, message: Message) -> bool:
        if not message.from_user or message.from_user.id != _ALLOWED:
            return False
        return channel_fetcher.waiting_for_code or channel_fetcher.waiting_for_password


@router.message(_WaitingForAuth())
async def handle_auth_input(message: Message) -> None:
    """Intercept any text message when Telethon is waiting for OTP / 2FA."""
    text = (message.text or "").strip()

    if channel_fetcher.waiting_for_code:
        logger.info("Received OTP from owner.")
        await message.answer(
            "✅ OTP received — logging in to Telegram…\n"
            "<i>The bot will confirm once authorisation is complete.</i>",
            parse_mode="HTML",
        )
        await channel_fetcher.provide_code(text)
        return

    if channel_fetcher.waiting_for_password:
        logger.info("Received 2FA password from owner.")
        await message.answer(
            "✅ Password received — completing 2FA login…\n"
            "<i>The bot will confirm once authorisation is complete.</i>",
            parse_mode="HTML",
        )
        await channel_fetcher.provide_password(text)

