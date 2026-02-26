"""Order flow FSM handler."""
from __future__ import annotations

import logging
from typing import Any

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from config import config
from database import get_preset_by_name, get_presets, save_order
from keyboards.inline import (
    cancel_keyboard,
    confirm_keyboard,
    mode_keyboard,
    presets_list_keyboard,
)
from smm_api import smm_api
from states.fsm import OrderFlow
from telegram_fetcher import channel_fetcher

logger = logging.getLogger(__name__)
router = Router(name="order")

_ALLOWED = config.allowed_user_id

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _safe_edit(msg: Message, text: str, **kwargs) -> None:  # type: ignore[type-arg]
    """Edit a message text; fall back to answer() if editing is not possible."""
    try:
        await msg.edit_text(text, **kwargs)
    except TelegramBadRequest:
        await msg.answer(text, **kwargs)


def _auth(user_id: int) -> bool:
    return user_id == _ALLOWED


def _channel_text(text: str) -> bool:
    """Return True if the message looks like a Telegram channel URL / handle."""
    t = text.strip()
    return t.startswith("https://t.me/") or t.startswith("http://t.me/") or t.startswith("@")


def _fmt_order_summary(data: dict[str, Any]) -> str:
    """Build a human-readable order summary string from FSM data."""
    lines = ["📦 <b>Order Summary</b>\n"]
    lines.append(f"📡 Channel: <code>{data.get('channel_url', '?')}</code>")

    mode = data.get("mode", "")
    if mode in ("subscribers", "all"):
        lines.append(
            f"\n👥 <b>Subscribers</b>\n"
            f"   Service ID: <code>{data.get('subs_service_id')}</code>\n"
            f"   Quantity: <code>{data.get('subs_quantity')}</code>"
        )
    if mode in ("views_reactions", "all"):
        post_count = len(data.get("post_urls", []))
        lines.append(
            f"\n👁 <b>Views</b> (across {post_count} posts)\n"
            f"   Service ID: <code>{data.get('views_service_id')}</code>\n"
            f"   Quantity per post: <code>{data.get('views_quantity')}</code>"
        )
        lines.append(
            f"\n❤️ <b>Reactions</b> (across {post_count} posts)\n"
            f"   Service ID: <code>{data.get('reactions_service_id')}</code>\n"
            f"   Quantity per post: <code>{data.get('reactions_quantity')}</code>"
        )
    return "\n".join(lines)


async def _fetch_posts_with_feedback(message: Message, channel_url: str, count: int) -> list[str] | None:
    """Fetch posts with a status message. Returns None on error."""
    status_msg = await message.answer("🔍 Fetching recent posts from channel…")
    try:
        urls = await channel_fetcher.fetch_post_urls(channel_url, count)
        if not urls:
            await status_msg.edit_text("❌ No posts found in that channel.")
            return None
        await status_msg.edit_text(f"✅ Found <b>{len(urls)}</b> recent posts.", parse_mode="HTML")
        return urls
    except ValueError as exc:
        await status_msg.edit_text(f"❌ {exc}")
        return None


async def _execute_orders(
    message: Message,
    data: dict[str, Any],
    preset_name: str | None = None,
) -> None:
    """Place all required orders based on FSM data and notify the user."""
    channel_url = data["channel_url"]
    mode = data["mode"]
    order_ids: list[str] = []
    errors: list[str] = []

    # ---- Subscribers ----
    if mode in ("subscribers", "all"):
        result = await smm_api.add_order(
            service=int(data["subs_service_id"]),
            link=channel_url,
            quantity=int(data["subs_quantity"]),
        )
        if "order" in result:
            order_id = result["order"]
            order_ids.append(f"Subscribers → #{order_id}")
            await save_order(
                {
                    "smm_order_id": order_id,
                    "channel_url": channel_url,
                    "post_url": None,
                    "service_type": "subscribers",
                    "service_id": int(data["subs_service_id"]),
                    "quantity": int(data["subs_quantity"]),
                    "status": "Pending",
                    "preset_name": preset_name,
                }
            )
        else:
            errors.append(f"Subscribers: {result.get('error', 'unknown error')}")

    # ---- Views + Reactions ----
    if mode in ("views_reactions", "all"):
        post_urls: list[str] = data.get("post_urls", [])
        for post_url in post_urls:
            # Views
            r_views = await smm_api.add_order(
                service=int(data["views_service_id"]),
                link=post_url,
                quantity=int(data["views_quantity"]),
            )
            if "order" in r_views:
                oid = r_views["order"]
                order_ids.append(f"Views ({post_url.split('/')[-1]}) → #{oid}")
                await save_order(
                    {
                        "smm_order_id": oid,
                        "channel_url": channel_url,
                        "post_url": post_url,
                        "service_type": "views",
                        "service_id": int(data["views_service_id"]),
                        "quantity": int(data["views_quantity"]),
                        "status": "Pending",
                        "preset_name": preset_name,
                    }
                )
            else:
                errors.append(f"Views for {post_url}: {r_views.get('error', 'unknown error')}")

            # Reactions
            r_react = await smm_api.add_order(
                service=int(data["reactions_service_id"]),
                link=post_url,
                quantity=int(data["reactions_quantity"]),
            )
            if "order" in r_react:
                oid = r_react["order"]
                order_ids.append(f"Reactions ({post_url.split('/')[-1]}) → #{oid}")
                await save_order(
                    {
                        "smm_order_id": oid,
                        "channel_url": channel_url,
                        "post_url": post_url,
                        "service_type": "reactions",
                        "service_id": int(data["reactions_service_id"]),
                        "quantity": int(data["reactions_quantity"]),
                        "status": "Pending",
                        "preset_name": preset_name,
                    }
                )
            else:
                errors.append(f"Reactions for {post_url}: {r_react.get('error', 'unknown error')}")

    # ---- Reply ----
    reply_lines = ["✅ <b>Orders placed!</b>\n"]
    if order_ids:
        reply_lines.append("📋 <b>Order IDs:</b>")
        reply_lines.extend(f"  • {o}" for o in order_ids)
    if errors:
        reply_lines.append("\n⚠️ <b>Errors:</b>")
        reply_lines.extend(f"  • {e}" for e in errors)

    await _safe_edit(message, "\n".join(reply_lines), parse_mode="HTML")


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------

@router.message(Command("order"))
async def cmd_order(message: Message, state: FSMContext) -> None:
    if not _auth(message.from_user.id):  # type: ignore[union-attr]
        return
    await state.set_state(OrderFlow.entering_channel)
    await message.answer(
        "📡 Send me your Telegram channel URL or @username:",
        reply_markup=cancel_keyboard(),
    )


@router.callback_query(F.data == "menu:order")
async def cb_menu_order(callback: CallbackQuery, state: FSMContext) -> None:
    if not _auth(callback.from_user.id):
        await callback.answer()
        return
    await callback.answer()
    await state.set_state(OrderFlow.entering_channel)
    await _safe_edit(
        callback.message,  # type: ignore[arg-type]
        "📡 Send me your Telegram channel URL or @username:",
        reply_markup=cancel_keyboard(),
    )


# Shortcut: user just sends a channel URL directly (any state)
@router.message(F.text.func(_channel_text))  # type: ignore[arg-type]
async def msg_channel_url(message: Message, state: FSMContext) -> None:
    if not _auth(message.from_user.id):  # type: ignore[union-attr]
        return
    await state.update_data(channel_url=message.text.strip())
    await state.set_state(OrderFlow.choosing_mode)
    await message.answer(
        f"✅ Channel set: <code>{message.text.strip()}</code>\n\n"
        "What would you like to order?",
        parse_mode="HTML",
        reply_markup=mode_keyboard(),
    )


@router.message(OrderFlow.entering_channel)
async def fsm_entering_channel(message: Message, state: FSMContext) -> None:
    await state.update_data(channel_url=message.text.strip())  # type: ignore[union-attr]
    await state.set_state(OrderFlow.choosing_mode)
    await message.answer(
        f"✅ Channel set: <code>{message.text.strip()}</code>\n\n"  # type: ignore[union-attr]
        "What would you like to order?",
        parse_mode="HTML",
        reply_markup=mode_keyboard(),
    )


# ---------------------------------------------------------------------------
# Mode selection
# ---------------------------------------------------------------------------

@router.callback_query(F.data.startswith("mode:"))
async def cb_mode(callback: CallbackQuery, state: FSMContext) -> None:
    if not _auth(callback.from_user.id):
        await callback.answer()
        return
    await callback.answer()
    mode = callback.data.split(":")[1]  # type: ignore[union-attr]

    if mode == "preset":
        presets = await get_presets()
        if not presets:
            await _safe_edit(
                callback.message,  # type: ignore[arg-type]
                "❌ You have no presets yet. Create one with /presets first.",
            )
            await state.clear()
            return
        await state.set_state(OrderFlow.choosing_preset)
        await _safe_edit(
            callback.message,  # type: ignore[arg-type]
            "Select a preset to use:",
            reply_markup=presets_list_keyboard(presets),
        )
        return

    await state.update_data(mode=mode)

    if mode == "subscribers":
        await state.set_state(OrderFlow.subs_service_id)
        await _safe_edit(
            callback.message,  # type: ignore[arg-type]
            "👥 Enter the <b>Subscriber service ID</b> (from /services or prm4u.com):",
            parse_mode="HTML",
            reply_markup=cancel_keyboard(),
        )
    elif mode in ("views_reactions", "all"):
        if mode == "all":
            await state.set_state(OrderFlow.subs_service_id)
            await _safe_edit(
                callback.message,  # type: ignore[arg-type]
                "👥 Enter the <b>Subscriber service ID</b>:",
                parse_mode="HTML",
                reply_markup=cancel_keyboard(),
            )
        else:
            # Skip straight to views
            data = await state.get_data()
            urls = await _fetch_posts_with_feedback(
                callback.message,  # type: ignore[arg-type]
                data["channel_url"],
                config.default_post_count,
            )
            if urls is None:
                await state.clear()
                return
            await state.update_data(post_urls=urls)
            await state.set_state(OrderFlow.views_service_id)
            await callback.message.answer(  # type: ignore[union-attr]
                "👁 Enter the <b>Views service ID</b>:",
                parse_mode="HTML",
                reply_markup=cancel_keyboard(),
            )


# ---------------------------------------------------------------------------
# Subscribers flow
# ---------------------------------------------------------------------------

@router.message(OrderFlow.subs_service_id)
async def fsm_subs_service_id(message: Message, state: FSMContext) -> None:
    if not message.text or not message.text.strip().isdigit():  # type: ignore[union-attr]
        await message.answer("⚠️ Please enter a valid numeric service ID.")
        return
    await state.update_data(subs_service_id=message.text.strip())  # type: ignore[union-attr]
    await state.set_state(OrderFlow.subs_quantity)
    await message.answer(
        "👥 How many <b>subscribers</b> do you want?",
        parse_mode="HTML",
        reply_markup=cancel_keyboard(),
    )


@router.message(OrderFlow.subs_quantity)
async def fsm_subs_quantity(message: Message, state: FSMContext) -> None:
    if not message.text or not message.text.strip().isdigit():  # type: ignore[union-attr]
        await message.answer("⚠️ Please enter a valid number.")
        return
    await state.update_data(subs_quantity=message.text.strip())  # type: ignore[union-attr]
    data = await state.get_data()
    mode = data.get("mode")

    if mode == "all":
        # Fetch posts, then move to views
        urls = await _fetch_posts_with_feedback(
            message, data["channel_url"], config.default_post_count
        )
        if urls is None:
            await state.clear()
            return
        await state.update_data(post_urls=urls)
        await state.set_state(OrderFlow.views_service_id)
        await message.answer(
            "👁 Enter the <b>Views service ID</b>:",
            parse_mode="HTML",
            reply_markup=cancel_keyboard(),
        )
    else:
        # Subscribers only → go to confirmation
        await state.set_state(OrderFlow.confirming)
        await message.answer(
            _fmt_order_summary(data | {"subs_quantity": message.text.strip()}),
            parse_mode="HTML",
            reply_markup=confirm_keyboard(),
        )


# ---------------------------------------------------------------------------
# Views flow
# ---------------------------------------------------------------------------

@router.message(OrderFlow.views_service_id)
async def fsm_views_service_id(message: Message, state: FSMContext) -> None:
    if not message.text or not message.text.strip().isdigit():  # type: ignore[union-attr]
        await message.answer("⚠️ Please enter a valid numeric service ID.")
        return
    await state.update_data(views_service_id=message.text.strip())  # type: ignore[union-attr]
    await state.set_state(OrderFlow.views_quantity)
    await message.answer(
        "👁 How many <b>views per post</b> do you want?",
        parse_mode="HTML",
        reply_markup=cancel_keyboard(),
    )


@router.message(OrderFlow.views_quantity)
async def fsm_views_quantity(message: Message, state: FSMContext) -> None:
    if not message.text or not message.text.strip().isdigit():  # type: ignore[union-attr]
        await message.answer("⚠️ Please enter a valid number.")
        return
    await state.update_data(views_quantity=message.text.strip())  # type: ignore[union-attr]
    await state.set_state(OrderFlow.reactions_service_id)
    await message.answer(
        "❤️ Enter the <b>Reactions service ID</b>:",
        parse_mode="HTML",
        reply_markup=cancel_keyboard(),
    )


# ---------------------------------------------------------------------------
# Reactions flow
# ---------------------------------------------------------------------------

@router.message(OrderFlow.reactions_service_id)
async def fsm_reactions_service_id(message: Message, state: FSMContext) -> None:
    if not message.text or not message.text.strip().isdigit():  # type: ignore[union-attr]
        await message.answer("⚠️ Please enter a valid numeric service ID.")
        return
    await state.update_data(reactions_service_id=message.text.strip())  # type: ignore[union-attr]
    await state.set_state(OrderFlow.reactions_quantity)
    await message.answer(
        "❤️ How many <b>reactions per post</b> do you want?",
        parse_mode="HTML",
        reply_markup=cancel_keyboard(),
    )


@router.message(OrderFlow.reactions_quantity)
async def fsm_reactions_quantity(message: Message, state: FSMContext) -> None:
    if not message.text or not message.text.strip().isdigit():  # type: ignore[union-attr]
        await message.answer("⚠️ Please enter a valid number.")
        return
    await state.update_data(reactions_quantity=message.text.strip())  # type: ignore[union-attr]
    data = await state.get_data()
    full_data = data | {"reactions_quantity": message.text.strip()}  # type: ignore[union-attr]
    await state.set_state(OrderFlow.confirming)
    await message.answer(
        _fmt_order_summary(full_data),
        parse_mode="HTML",
        reply_markup=confirm_keyboard(),
    )


# ---------------------------------------------------------------------------
# Preset selection path
# ---------------------------------------------------------------------------

@router.callback_query(F.data.startswith("preset_select:"), OrderFlow.choosing_preset)
async def cb_preset_selected(callback: CallbackQuery, state: FSMContext) -> None:
    if not _auth(callback.from_user.id):
        await callback.answer()
        return
    await callback.answer()
    preset_name = callback.data.split(":", 1)[1]  # type: ignore[union-attr]
    preset = await get_preset_by_name(preset_name)
    if not preset:
        await _safe_edit(
            callback.message,  # type: ignore[arg-type]
            f"❌ Preset '{preset_name}' not found.",
        )
        await state.clear()
        return

    fsm_data = await state.get_data()
    channel_url = fsm_data["channel_url"]

    # Determine effective mode
    has_subs = bool(preset.get("subscribers_enabled"))
    has_views = bool(preset.get("views_enabled"))
    has_reactions = bool(preset.get("reactions_enabled"))

    needs_posts = has_views or has_reactions
    post_urls: list[str] = []

    if needs_posts:
        post_urls = await _fetch_posts_with_feedback(
            callback.message,  # type: ignore[arg-type]
            channel_url,
            preset.get("post_count", config.default_post_count),
        ) or []
        if not post_urls:
            await state.clear()
            return

    # Build mode
    if has_subs and (has_views or has_reactions):
        mode = "all"
    elif has_subs:
        mode = "subscribers"
    else:
        mode = "views_reactions"

    combined: dict[str, Any] = {
        "channel_url": channel_url,
        "mode": mode,
        "preset_name": preset_name,
        "post_urls": post_urls,
        "subs_service_id": preset.get("subscribers_service_id"),
        "subs_quantity": preset.get("subscribers_quantity"),
        "views_service_id": preset.get("views_service_id"),
        "views_quantity": preset.get("views_quantity"),
        "reactions_service_id": preset.get("reactions_service_id"),
        "reactions_quantity": preset.get("reactions_quantity"),
    }
    await state.update_data(**combined)
    await state.set_state(OrderFlow.confirming)
    await _safe_edit(
        callback.message,  # type: ignore[arg-type]
        _fmt_order_summary(combined),
        parse_mode="HTML",
        reply_markup=confirm_keyboard(),
    )


# ---------------------------------------------------------------------------
# Confirmation
# ---------------------------------------------------------------------------

@router.callback_query(F.data == "order:confirm", OrderFlow.confirming)
async def cb_confirm(callback: CallbackQuery, state: FSMContext) -> None:
    if not _auth(callback.from_user.id):
        await callback.answer()
        return
    await callback.answer()
    await _safe_edit(
        callback.message,  # type: ignore[arg-type]
        "⏳ Placing orders…",
    )
    data = await state.get_data()
    await state.clear()
    await _execute_orders(callback.message, data, data.get("preset_name"))  # type: ignore[arg-type]


@router.callback_query(F.data == "order:cancel")
async def cb_cancel_order(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.clear()
    await _safe_edit(
        callback.message,  # type: ignore[arg-type]
        "❌ Order cancelled.",
    )


# /cancel command — kill any ongoing FSM
@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("❌ Cancelled. Use /start to go back to the main menu.")
