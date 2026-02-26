"""Order status and history handlers."""
from __future__ import annotations

import logging
import math

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from config import config
from database import get_recent_orders
from keyboards.inline import history_nav_keyboard
from smm_api import smm_api

logger = logging.getLogger(__name__)
router = Router(name="status")

_ALLOWED = config.allowed_user_id
_PAGE_SIZE = 5


def _auth(uid: int) -> bool:
    return uid == _ALLOWED


def _status_emoji(status: str) -> str:
    status_lower = status.lower()
    if "complet" in status_lower:
        return "✅"
    if "progress" in status_lower or "pending" in status_lower or "processing" in status_lower:
        return "⏳"
    if "partial" in status_lower:
        return "⚠️"
    if "cancel" in status_lower or "refund" in status_lower:
        return "❌"
    return "🔄"


# ---------------------------------------------------------------------------
# /status <order_id>
# ---------------------------------------------------------------------------

@router.message(Command("status"))
async def cmd_status(message: Message) -> None:
    if not _auth(message.from_user.id):  # type: ignore[union-attr]
        return
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip().isdigit():
        await message.answer(
            "ℹ️ Usage: <code>/status &lt;smm_order_id&gt;</code>",
            parse_mode="HTML",
        )
        return
    order_id = int(parts[1].strip())
    data = await smm_api.get_status(order_id)
    if "error" in data:
        await message.answer(f"❌ Error: {data['error']}")
        return
    status = data.get("status", "Unknown")
    emoji = _status_emoji(status)
    charge_raw = float(data.get("charge") or 0)
    rate = await smm_api.get_usd_to_inr()
    charge_inr = charge_raw * rate
    await message.answer(
        f"{emoji} <b>Order #{order_id}</b>\n\n"
        f"Status:      <b>{status}</b>\n"
        f"Charge:      <code>₹{charge_inr:.2f} INR</code>\n"
        f"Remains:     <code>{data.get('remains', '?')}</code>\n"
        f"Start count: <code>{data.get('start_count', '?')}</code>",
        parse_mode="HTML",
    )


# ---------------------------------------------------------------------------
# /history (+ pagination)
# ---------------------------------------------------------------------------

@router.message(Command("history"))
async def cmd_history(message: Message) -> None:
    if not _auth(message.from_user.id):  # type: ignore[union-attr]
        return
    await _show_history_page(message, page=0)


@router.callback_query(F.data == "menu:history")
async def cb_menu_history(callback: CallbackQuery) -> None:
    if not _auth(callback.from_user.id):
        await callback.answer()
        return
    await callback.answer()
    await _show_history_page(callback.message, page=0, edit=True)  # type: ignore[arg-type]


@router.callback_query(F.data.startswith("history:page:"))
async def cb_history_page(callback: CallbackQuery) -> None:
    if not _auth(callback.from_user.id):
        await callback.answer()
        return
    await callback.answer()
    page = int(callback.data.split(":")[-1])  # type: ignore[union-attr]
    await _show_history_page(callback.message, page=page, edit=True)  # type: ignore[arg-type]


async def _show_history_page(target: Message, page: int, *, edit: bool = False) -> None:
    orders = await get_recent_orders(limit=100)
    if not orders:
        text = "💭 No orders found."
        if edit:
            try:
                await target.edit_text(text, reply_markup=None)
            except TelegramBadRequest:
                await target.answer(text)
        else:
            await target.answer(text)
        return

    total_pages = max(1, math.ceil(len(orders) / _PAGE_SIZE))
    page = max(0, min(page, total_pages - 1))
    start = page * _PAGE_SIZE
    slice_ = orders[start: start + _PAGE_SIZE]

    lines = [f"📜 <b>Order History</b> (page {page + 1}/{total_pages})\n"]
    for o in slice_:
        emoji = _status_emoji(o["status"])
        post_info = f" | {o['post_url'].split('/')[-1]}" if o.get("post_url") else ""
        lines.append(
            f"{emoji} <b>#{o['smm_order_id']}</b> — {o['service_type'].title()}{post_info}\n"
            f"   Channel: <code>{o['channel_url']}</code>\n"
            f"   Qty: <code>{o['quantity']}</code> | Status: <b>{o['status']}</b>\n"
            f"   Placed: {o['created_at'][:16].replace('T', ' ')}"
        )

    text = "\n\n".join(lines)
    kb = history_nav_keyboard(page, total_pages)
    if edit:
        try:
            await target.edit_text(text, parse_mode="HTML", reply_markup=kb)
        except TelegramBadRequest:
            await target.answer(text, parse_mode="HTML", reply_markup=kb)
    else:
        await target.answer(text, parse_mode="HTML", reply_markup=kb)


