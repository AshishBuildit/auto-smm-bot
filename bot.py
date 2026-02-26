"""Bot entry point."""
from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from config import config
from database import init_db
from handlers import order, presets, start, status
from handlers import auth as auth_handler
from smm_api import smm_api
from tasks.tracker import order_tracker
from telegram_fetcher import channel_fetcher

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Silence noisy third-party loggers — only show WARNING and above
for _noisy in (
    "aiogram",
    "aiogram.event",
    "aiohttp",
    "aiohttp.access",
    "telethon",
    "telethon.network",
    "telethon.extensions",
    "asyncio",
):
    logging.getLogger(_noisy).setLevel(logging.WARNING)

_BOT_COMMANDS = [
    BotCommand(command="start",    description="Main menu"),
    BotCommand(command="order",    description="Start a new order"),
    BotCommand(command="presets",  description="Manage order presets"),
    BotCommand(command="balance",  description="Check SMM panel balance"),
    BotCommand(command="history",  description="View order history"),
    BotCommand(command="status",   description="Check an order status"),
    BotCommand(command="cancel",   description="Cancel current action"),
    BotCommand(command="help",     description="Show help"),
]


async def _start_telethon_auth(bot: Bot) -> None:
    """Background task: start Telethon auth in-bot, then notify owner."""
    await asyncio.sleep(1)  # let the polling loop spin up first
    try:
        already_auth = await channel_fetcher.start(bot=bot)
        if not already_auth:
            await bot.send_message(
                config.allowed_user_id,
                "✅ <b>Telegram authorised!</b> The bot is fully operational.",
                parse_mode="HTML",
            )
    except Exception as exc:
        logger.error("Telethon auth failed: %s", exc)
        await bot.send_message(
            config.allowed_user_id,
            f"❌ <b>Telethon auth failed:</b> {exc}\n\nRestart the bot to try again.",
            parse_mode="HTML",
        )


async def on_startup(bot: Bot) -> None:
    """Initialise all resources on bot startup."""
    logger.info("Starting up…")
    await init_db()
    await smm_api.start()

    # Register bot commands so they appear in the / menu without BotFather setup
    await bot.set_my_commands(_BOT_COMMANDS)
    logger.info("Bot commands registered.")

    # Start Telethon auth as a background task so the bot can serve the OTP prompt
    asyncio.create_task(_start_telethon_auth(bot), name="telethon_auth")

    # Launch the background order tracker
    asyncio.create_task(order_tracker(bot), name="order_tracker")
    logger.info("Bot is ready.")


async def on_shutdown(bot: Bot) -> None:
    """Clean up resources on shutdown."""
    logger.info("Shutting down…")
    await smm_api.stop()
    await channel_fetcher.stop()


async def main() -> None:
    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    # Register lifecycle hooks
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # Register routers — auth first (highest priority for OTP interception)
    dp.include_router(auth_handler.router)
    dp.include_router(start.router)
    dp.include_router(presets.router)
    dp.include_router(status.router)
    dp.include_router(order.router)  # order last — has a catch-all channel URL handler

    logger.info("Starting polling…")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())

