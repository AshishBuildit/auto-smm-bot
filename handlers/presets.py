"""Preset management FSM handlers."""
from __future__ import annotations

import logging
from typing import Any

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from config import config
from database import delete_preset, get_preset_by_name, get_presets, save_preset
from keyboards.inline import (
    cancel_keyboard,
    confirm_keyboard,
    delete_presets_keyboard,
    manage_presets_keyboard,
    yes_no_keyboard,
)
from states.fsm import DeletePresetFlow, PresetFlow

logger = logging.getLogger(__name__)
router = Router(name="presets")

_ALLOWED = config.allowed_user_id


def _auth(uid: int) -> bool:
    return uid == _ALLOWED


async def _safe_edit(msg: Message, text: str, **kwargs) -> None:  # type: ignore[type-arg]
    """Edit a message text; fall back to answer() if editing is not possible."""
    try:
        await msg.edit_text(text, **kwargs)
    except TelegramBadRequest:
        await msg.answer(text, **kwargs)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fmt_preset(p: dict[str, Any]) -> str:
    lines = [f"📌 <b>Preset: \"{p['name']}\"</b>"]
    if p.get("subscribers_enabled"):
        lines.append(
            f"  ✅ Subscribers: <code>{p.get('subscribers_quantity', '?')}</code> "
            f"× Service <code>#{p.get('subscribers_service_id', '?')}</code>"
        )
    else:
        lines.append("  ☑️ Subscribers: disabled")

    if p.get("views_enabled"):
        lines.append(
            f"  ✅ Views: <code>{p.get('views_quantity', '?')}</code> "
            f"× Service <code>#{p.get('views_service_id', '?')}</code>"
        )
    else:
        lines.append("  ☑️ Views: disabled")

    if p.get("reactions_enabled"):
        lines.append(
            f"  ✅ Reactions: <code>{p.get('reactions_quantity', '?')}</code> "
            f"× Service <code>#{p.get('reactions_service_id', '?')}</code>"
        )
    else:
        lines.append("  ☑️ Reactions: disabled")

    lines.append(f"  📰 Posts targeted: <code>{p.get('post_count', 10)}</code>")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------

@router.message(Command("presets"))
async def cmd_presets(message: Message) -> None:
    if not _auth(message.from_user.id):  # type: ignore[union-attr]
        return
    await message.answer(
        "⚙️ <b>Preset Manager</b>\n\nChoose an action:",
        parse_mode="HTML",
        reply_markup=manage_presets_keyboard(),
    )


@router.callback_query(F.data == "menu:presets")
async def cb_menu_presets(callback: CallbackQuery) -> None:
    if not _auth(callback.from_user.id):
        await callback.answer()
        return
    await callback.answer()
    await _safe_edit(  # type: ignore[union-attr]
        callback.message,  # type: ignore[arg-type]
        "⚙️ <b>Preset Manager</b>\n\nChoose an action:",
        parse_mode="HTML",
        reply_markup=manage_presets_keyboard(),
    )


# ---------------------------------------------------------------------------
# List presets
# ---------------------------------------------------------------------------

@router.callback_query(F.data == "presets:list")
async def cb_list_presets(callback: CallbackQuery) -> None:
    if not _auth(callback.from_user.id):
        await callback.answer()
        return
    await callback.answer()
    presets = await get_presets()
    if not presets:
        await _safe_edit(
            callback.message,  # type: ignore[arg-type]
            "❌ No presets saved yet.",
            reply_markup=manage_presets_keyboard(),
        )
        return
    # Consolidate all presets into one message to keep the chat clean
    combined = "\n\n".join(_fmt_preset(p) for p in presets)
    await _safe_edit(
        callback.message,  # type: ignore[arg-type]
        combined,
        parse_mode="HTML",
        reply_markup=manage_presets_keyboard(),
    )


# ---------------------------------------------------------------------------
# Create preset FSM
# ---------------------------------------------------------------------------

@router.callback_query(F.data == "presets:new")
async def cb_new_preset(callback: CallbackQuery, state: FSMContext) -> None:
    if not _auth(callback.from_user.id):
        await callback.answer()
        return
    await callback.answer()
    await state.set_state(PresetFlow.entering_name)
    await _safe_edit(
        callback.message,  # type: ignore[arg-type]
        "📝 Enter a <b>name</b> for this preset (e.g. <code>growth_pack</code>):",
        parse_mode="HTML",
        reply_markup=cancel_keyboard(),
    )


@router.message(PresetFlow.entering_name)
async def fsm_preset_name(message: Message, state: FSMContext) -> None:
    name = (message.text or "").strip()
    if not name:
        await message.answer("⚠️ Name cannot be empty.")
        return
    existing = await get_preset_by_name(name)
    if existing:
        await message.answer(
            f"⚠️ A preset named <b>{name}</b> already exists. "
            "It will be overwritten if you continue.\n\nEnter a name (or a new one):",
            parse_mode="HTML",
        )
    await state.update_data(name=name)
    await state.set_state(PresetFlow.subs_enabled)
    await message.answer(
        "👥 Enable <b>Subscribers</b> in this preset?",
        parse_mode="HTML",
        reply_markup=yes_no_keyboard("subs"),
    )


@router.callback_query(F.data.startswith("yn:subs:"), PresetFlow.subs_enabled)
async def fsm_subs_enabled(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    enabled = callback.data.endswith(":yes")  # type: ignore[union-attr]
    await state.update_data(subscribers_enabled=enabled)
    if enabled:
        await state.set_state(PresetFlow.subs_service_id)
        await _safe_edit(
            callback.message,  # type: ignore[arg-type]
            "👥 Enter the <b>Subscriber service ID</b>:",
            parse_mode="HTML",
            reply_markup=cancel_keyboard(),
        )
    else:
        await state.update_data(subscribers_service_id=None, subscribers_quantity=None)
        await state.set_state(PresetFlow.views_enabled)
        await _safe_edit(
            callback.message,  # type: ignore[arg-type]
            "👁 Enable <b>Views</b> in this preset?",
            parse_mode="HTML",
            reply_markup=yes_no_keyboard("views"),
        )


@router.message(PresetFlow.subs_service_id)
async def fsm_preset_subs_sid(message: Message, state: FSMContext) -> None:
    if not message.text or not message.text.strip().isdigit():  # type: ignore[union-attr]
        await message.answer("⚠️ Please enter a valid numeric service ID.")
        return
    await state.update_data(subscribers_service_id=int(message.text.strip()))  # type: ignore[union-attr]
    await state.set_state(PresetFlow.subs_quantity)
    await message.answer(
        "👥 Enter the default <b>subscriber quantity</b>:",
        parse_mode="HTML",
        reply_markup=cancel_keyboard(),
    )


@router.message(PresetFlow.subs_quantity)
async def fsm_preset_subs_qty(message: Message, state: FSMContext) -> None:
    if not message.text or not message.text.strip().isdigit():  # type: ignore[union-attr]
        await message.answer("⚠️ Please enter a valid number.")
        return
    await state.update_data(subscribers_quantity=int(message.text.strip()))  # type: ignore[union-attr]
    await state.set_state(PresetFlow.views_enabled)
    await message.answer(
        "👁 Enable <b>Views</b> in this preset?",
        parse_mode="HTML",
        reply_markup=yes_no_keyboard("views"),
    )


@router.callback_query(F.data.startswith("yn:views:"), PresetFlow.views_enabled)
async def fsm_views_enabled(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    enabled = callback.data.endswith(":yes")  # type: ignore[union-attr]
    await state.update_data(views_enabled=enabled)
    if enabled:
        await state.set_state(PresetFlow.views_service_id)
        await _safe_edit(
            callback.message,  # type: ignore[arg-type]
            "👁 Enter the <b>Views service ID</b>:",
            parse_mode="HTML",
            reply_markup=cancel_keyboard(),
        )
    else:
        await state.update_data(views_service_id=None, views_quantity=None)
        await state.set_state(PresetFlow.reactions_enabled)
        await _safe_edit(
            callback.message,  # type: ignore[arg-type]
            "❤️ Enable <b>Reactions</b> in this preset?",
            parse_mode="HTML",
            reply_markup=yes_no_keyboard("reactions"),
        )


@router.message(PresetFlow.views_service_id)
async def fsm_preset_views_sid(message: Message, state: FSMContext) -> None:
    if not message.text or not message.text.strip().isdigit():  # type: ignore[union-attr]
        await message.answer("⚠️ Please enter a valid numeric service ID.")
        return
    await state.update_data(views_service_id=int(message.text.strip()))  # type: ignore[union-attr]
    await state.set_state(PresetFlow.views_quantity)
    await message.answer(
        "👁 Enter the default <b>views quantity per post</b>:",
        parse_mode="HTML",
        reply_markup=cancel_keyboard(),
    )


@router.message(PresetFlow.views_quantity)
async def fsm_preset_views_qty(message: Message, state: FSMContext) -> None:
    if not message.text or not message.text.strip().isdigit():  # type: ignore[union-attr]
        await message.answer("⚠️ Please enter a valid number.")
        return
    await state.update_data(views_quantity=int(message.text.strip()))  # type: ignore[union-attr]
    await state.set_state(PresetFlow.reactions_enabled)
    await message.answer(
        "❤️ Enable <b>Reactions</b> in this preset?",
        parse_mode="HTML",
        reply_markup=yes_no_keyboard("reactions"),
    )


@router.callback_query(F.data.startswith("yn:reactions:"), PresetFlow.reactions_enabled)
async def fsm_reactions_enabled(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    enabled = callback.data.endswith(":yes")  # type: ignore[union-attr]
    await state.update_data(reactions_enabled=enabled)
    if enabled:
        await state.set_state(PresetFlow.reactions_service_id)
        await _safe_edit(
            callback.message,  # type: ignore[arg-type]
            "❤️ Enter the <b>Reactions service ID</b>:",
            parse_mode="HTML",
            reply_markup=cancel_keyboard(),
        )
    else:
        await state.update_data(reactions_service_id=None, reactions_quantity=None)
        await _ask_post_count(callback.message, state, edit=True)  # type: ignore[arg-type]


@router.message(PresetFlow.reactions_service_id)
async def fsm_preset_reactions_sid(message: Message, state: FSMContext) -> None:
    if not message.text or not message.text.strip().isdigit():  # type: ignore[union-attr]
        await message.answer("⚠️ Please enter a valid numeric service ID.")
        return
    await state.update_data(reactions_service_id=int(message.text.strip()))  # type: ignore[union-attr]
    await state.set_state(PresetFlow.reactions_quantity)
    await message.answer(
        "❤️ Enter the default <b>reactions quantity per post</b>:",
        parse_mode="HTML",
        reply_markup=cancel_keyboard(),
    )


@router.message(PresetFlow.reactions_quantity)
async def fsm_preset_reactions_qty(message: Message, state: FSMContext) -> None:
    if not message.text or not message.text.strip().isdigit():  # type: ignore[union-attr]
        await message.answer("⚠️ Please enter a valid number.")
        return
    await state.update_data(reactions_quantity=int(message.text.strip()))  # type: ignore[union-attr]
    await _ask_post_count(message, state)


async def _ask_post_count(target: Message, state: FSMContext, *, edit: bool = False) -> None:
    await state.set_state(PresetFlow.post_count)
    text = (
        f"📰 How many recent posts should be targeted for views/reactions?\n"
        f"(Default: <code>{config.default_post_count}</code>)"
    )
    if edit:
        await _safe_edit(target, text, parse_mode="HTML", reply_markup=cancel_keyboard())
    else:
        await target.answer(text, parse_mode="HTML", reply_markup=cancel_keyboard())


@router.message(PresetFlow.post_count)
async def fsm_preset_post_count(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not text.isdigit():
        await message.answer("⚠️ Please enter a valid number.")
        return
    await state.update_data(post_count=int(text))
    data = await state.get_data()
    await state.set_state(PresetFlow.confirming)
    await message.answer(
        _fmt_preset_from_data(data) + "\n\n<b>Save this preset?</b>",
        parse_mode="HTML",
        reply_markup=confirm_keyboard(),
    )


def _fmt_preset_from_data(data: dict[str, Any]) -> str:
    return _fmt_preset(
        {
            "name": data.get("name", "?"),
            "subscribers_enabled": data.get("subscribers_enabled"),
            "subscribers_service_id": data.get("subscribers_service_id"),
            "subscribers_quantity": data.get("subscribers_quantity"),
            "views_enabled": data.get("views_enabled"),
            "views_service_id": data.get("views_service_id"),
            "views_quantity": data.get("views_quantity"),
            "reactions_enabled": data.get("reactions_enabled"),
            "reactions_service_id": data.get("reactions_service_id"),
            "reactions_quantity": data.get("reactions_quantity"),
            "post_count": data.get("post_count", config.default_post_count),
        }
    )


@router.callback_query(F.data == "order:confirm", PresetFlow.confirming)
async def fsm_preset_confirm(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    data = await state.get_data()
    await save_preset(data)
    await state.clear()
    await _safe_edit(
        callback.message,  # type: ignore[arg-type]
        f"✅ Preset <b>\"{data['name']}\"</b> saved!",
        parse_mode="HTML",
        reply_markup=manage_presets_keyboard(),
    )


@router.callback_query(F.data == "order:cancel", PresetFlow.confirming)
async def fsm_preset_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.clear()
    await _safe_edit(
        callback.message,  # type: ignore[arg-type]
        "❌ Preset creation cancelled. Use /presets to start over.",
    )


# ---------------------------------------------------------------------------
# Delete preset flow
# ---------------------------------------------------------------------------

@router.callback_query(F.data == "presets:delete")
async def cb_delete_preset(callback: CallbackQuery, state: FSMContext) -> None:
    if not _auth(callback.from_user.id):
        await callback.answer()
        return
    await callback.answer()
    presets = await get_presets()
    if not presets:
        await _safe_edit(
            callback.message,  # type: ignore[arg-type]
            "❌ No presets to delete.",
            reply_markup=manage_presets_keyboard(),
        )
        return
    await state.set_state(DeletePresetFlow.choosing_preset)
    await _safe_edit(
        callback.message,  # type: ignore[arg-type]
        "🗑 Which preset do you want to delete?",
        reply_markup=delete_presets_keyboard(presets),
    )


@router.callback_query(F.data.startswith("preset_delete:"), DeletePresetFlow.choosing_preset)
async def cb_delete_preset_chosen(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    preset_name = callback.data.split(":", 1)[1]  # type: ignore[union-attr]
    await state.update_data(delete_preset_name=preset_name)
    await state.set_state(DeletePresetFlow.confirming)
    await _safe_edit(
        callback.message,  # type: ignore[arg-type]
        f"🗑 Are you sure you want to delete preset <b>\"{preset_name}\"</b>?",
        parse_mode="HTML",
        reply_markup=confirm_keyboard(),
    )


@router.callback_query(F.data == "order:confirm", DeletePresetFlow.confirming)
async def cb_delete_preset_confirm(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    data = await state.get_data()
    name = data.get("delete_preset_name", "")
    deleted = await delete_preset(name)
    await state.clear()
    text = (
        f"✅ Preset <b>\"{name}\"</b> deleted."
        if deleted
        else f"❌ Preset <b>\"{name}\"</b> not found."
    )
    await _safe_edit(
        callback.message,  # type: ignore[arg-type]
        text,
        parse_mode="HTML",
        reply_markup=manage_presets_keyboard(),
    )


@router.callback_query(F.data == "order:cancel", DeletePresetFlow.confirming)
async def cb_delete_preset_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.clear()
    await _safe_edit(
        callback.message,  # type: ignore[arg-type]
        "❌ Deletion cancelled.",
        reply_markup=manage_presets_keyboard(),
    )
