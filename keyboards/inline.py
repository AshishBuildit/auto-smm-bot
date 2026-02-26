"""Shared inline keyboard builder functions."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def main_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📦 New Order", callback_data="menu:order"),
        InlineKeyboardButton(text="📋 My Presets", callback_data="menu:presets"),
    )
    builder.row(
        InlineKeyboardButton(text="💰 Balance", callback_data="menu:balance"),
        InlineKeyboardButton(text="📜 History", callback_data="menu:history"),
    )
    return builder.as_markup()


def mode_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="👥 Subscribers Only", callback_data="mode:subscribers"))
    builder.row(InlineKeyboardButton(text="👁 Views + Reactions", callback_data="mode:views_reactions"))
    builder.row(InlineKeyboardButton(text="🚀 All Three (Subs + Views + Reactions)", callback_data="mode:all"))
    builder.row(InlineKeyboardButton(text="⚙️ Use a Preset", callback_data="mode:preset"))
    builder.row(InlineKeyboardButton(text="❌ Cancel", callback_data="order:cancel"))
    return builder.as_markup()


def presets_list_keyboard(presets: list[dict], callback_prefix: str = "preset_select") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for p in presets:
        builder.row(
            InlineKeyboardButton(
                text=f"⚙️ {p['name']}",
                callback_data=f"{callback_prefix}:{p['name']}",
            )
        )
    builder.row(InlineKeyboardButton(text="❌ Cancel", callback_data="order:cancel"))
    return builder.as_markup()


def confirm_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Confirm", callback_data="order:confirm"),
        InlineKeyboardButton(text="❌ Cancel", callback_data="order:cancel"),
    )
    return builder.as_markup()


def yes_no_keyboard(field: str) -> InlineKeyboardMarkup:
    """Used in preset creation to enable/disable a service section."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Yes", callback_data=f"yn:{field}:yes"),
        InlineKeyboardButton(text="❌ No", callback_data=f"yn:{field}:no"),
    )
    return builder.as_markup()


def manage_presets_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="➕ New Preset", callback_data="presets:new"))
    builder.row(InlineKeyboardButton(text="📋 List Presets", callback_data="presets:list"))
    builder.row(InlineKeyboardButton(text="🗑 Delete Preset", callback_data="presets:delete"))
    builder.row(InlineKeyboardButton(text="🏠 Main Menu", callback_data="menu:back"))
    return builder.as_markup()


def history_nav_keyboard(page: int, total_pages: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    nav_row: list[InlineKeyboardButton] = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="◀️ Prev", callback_data=f"history:page:{page - 1}"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton(text="Next ▶️", callback_data=f"history:page:{page + 1}"))
    if nav_row:
        builder.row(*nav_row)
    builder.row(InlineKeyboardButton(text="🏠 Main Menu", callback_data="menu:back"))
    return builder.as_markup()


def cancel_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="❌ Cancel", callback_data="order:cancel"))
    return builder.as_markup()


def delete_presets_keyboard(presets: list[dict]) -> InlineKeyboardMarkup:
    return presets_list_keyboard(presets, callback_prefix="preset_delete")


def back_to_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🏠 Main Menu", callback_data="menu:back"))
    return builder.as_markup()
