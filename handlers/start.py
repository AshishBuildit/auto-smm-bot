"""Middleware + /start, /help, /balance handlers."""
from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from config import config
from keyboards.inline import back_to_menu_keyboard, main_menu_keyboard
from smm_api import smm_api

logger = logging.getLogger(__name__)
router = Router(name="start")


# ---------------------------------------------------------------------------
# Auth filter – Restrict to the configured user only
# ---------------------------------------------------------------------------

def _is_allowed(user_id: int) -> bool:
    return user_id == config.allowed_user_id


_WELCOME_TEXT = (
    "👋 <b>Welcome to your Auto-SMM Bot!</b>\n\n"
    "I can boost your Telegram channel by ordering <b>subscribers</b>, "
    "<b>views</b>, and <b>reactions</b> through the PRM4U SMM panel.\n\n"
    "You can:\n"
    "• Send a channel URL (e.g. <code>https://t.me/mychannel</code>) to start a quick order.\n"
    "• Or use the menu below to manage presets, check your balance, or view order history."
)


# ---------------------------------------------------------------------------
# /start
# ---------------------------------------------------------------------------

@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    if not _is_allowed(message.from_user.id):  # type: ignore[union-attr]
        return

    await message.answer(
        _WELCOME_TEXT,
        parse_mode="HTML",
        reply_markup=main_menu_keyboard(),
    )


# ---------------------------------------------------------------------------
# /help
# ---------------------------------------------------------------------------

@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    if not _is_allowed(message.from_user.id):  # type: ignore[union-attr]
        return

    await message.answer(
        "📖 <b>Commands</b>\n\n"
        "/start – Main menu\n"
        "/order – Start a new order (or just send a channel URL)\n"
        "/presets – Manage your order presets\n"
        "/balance – Check your SMM panel balance\n"
        "/status &lt;order_id&gt; – Check an order status\n"
        "/history – View your recent orders\n"
        "/cancel – Cancel any ongoing conversation\n"
        "/help – This message\n\n"
        "<b>Quick tip:</b> Just send <code>https://t.me/yourchannel</code> or "
        "<code>@yourchannel</code> at any time to jump straight to the order flow.",
        parse_mode="HTML",
    )


# ---------------------------------------------------------------------------
# /balance
# ---------------------------------------------------------------------------

@router.message(Command("balance"))
async def cmd_balance(message: Message) -> None:
    if not _is_allowed(message.from_user.id):  # type: ignore[union-attr]
        return
    await _show_balance(message, edit=False)


@router.callback_query(F.data == "menu:balance")
async def cb_balance(callback: CallbackQuery) -> None:
    if not _is_allowed(callback.from_user.id):
        await callback.answer()
        return
    await callback.answer()
    await _show_balance(callback.message, edit=True)  # type: ignore[arg-type]


async def _show_balance(target: Message, *, edit: bool = False) -> None:
    data = await smm_api.get_balance()
    if "error" in data:
        text = f"❌ Error fetching balance: {data['error']}"
        kb = back_to_menu_keyboard()
    else:
        balance_usd = float(data.get("balance", 0))
        rate = await smm_api.get_usd_to_inr()
        balance_inr = balance_usd * rate
        text = (
            f"💰 <b>Your SMM Panel Balance</b>\n\n"
            f"₹<b>{balance_inr:,.2f}</b> INR"
        )
        kb = back_to_menu_keyboard()

    if edit:
        try:
            await target.edit_text(text, parse_mode="HTML", reply_markup=kb)
        except TelegramBadRequest:
            await target.answer(text, parse_mode="HTML", reply_markup=kb)
    else:
        await target.answer(text, parse_mode="HTML", reply_markup=kb)


# ---------------------------------------------------------------------------
# Menu callbacks – Main menu & Back
# ---------------------------------------------------------------------------

@router.callback_query(F.data == "menu:back")
async def cb_main_menu(callback: CallbackQuery) -> None:
    if not _is_allowed(callback.from_user.id):
        await callback.answer()
        return
    await callback.answer()
    try:
        await callback.message.edit_text(  # type: ignore[union-attr]
            _WELCOME_TEXT,
            parse_mode="HTML",
            reply_markup=main_menu_keyboard(),
        )
    except TelegramBadRequest:
        await callback.message.answer(  # type: ignore[union-attr]
            _WELCOME_TEXT,
            parse_mode="HTML",
            reply_markup=main_menu_keyboard(),
        )

