"""Background task: poll pending order statuses and notify the owner."""
from __future__ import annotations

import asyncio
import logging

from aiogram import Bot

from config import config
from database import get_pending_orders, update_order_status
from smm_api import smm_api

logger = logging.getLogger(__name__)

_POLL_INTERVAL = 60  # seconds between status checks

# Statuses that mean the order is done and we should stop polling
_TERMINAL_STATUSES = frozenset({"Completed", "Partial", "Canceled", "Refunded", "Error"})


def _status_emoji(status: str) -> str:
    s = status.lower()
    if "complet" in s:
        return "✅"
    if "partial" in s:
        return "⚠️"
    if "cancel" in s or "refund" in s or "error" in s:
        return "❌"
    return "⏳"


async def order_tracker(bot: Bot) -> None:
    """Infinite loop that checks pending orders and sends notifications."""
    logger.info("Order tracker started.")
    while True:
        try:
            await _check_orders(bot)
        except asyncio.CancelledError:
            logger.info("Order tracker cancelled.")
            break
        except Exception as exc:
            logger.exception("Order tracker error: %s", exc)

        await asyncio.sleep(_POLL_INTERVAL)


async def _check_orders(bot: Bot) -> None:
    pending = await get_pending_orders()
    if not pending:
        return

    # Deduplicate by smm_order_id (same SMM order may appear once per service type row)
    by_smm_id: dict[int, dict] = {}
    for row in pending:
        sid = row["smm_order_id"]
        if sid not in by_smm_id:
            by_smm_id[sid] = row

    smm_ids = list(by_smm_id.keys())
    if not smm_ids:
        return

    # Batch query (up to 100 at a time)
    results = await smm_api.get_multi_status(smm_ids)

    for smm_id_str, status_data in results.items():
        if not smm_id_str.isdigit():
            continue
        smm_id = int(smm_id_str)
        if "error" in status_data:
            continue

        new_status = status_data.get("status", "")
        charge = status_data.get("charge")
        remains = status_data.get("remains")

        row = by_smm_id.get(smm_id)
        if row is None:
            continue

        old_status = row.get("status", "")
        if new_status and new_status != old_status:
            await update_order_status(
                smm_order_id=smm_id,
                status=new_status,
                charge=float(charge) if charge is not None else None,
                remains=int(remains) if remains is not None else None,
            )

            # Notify owner
            emoji = _status_emoji(new_status)
            post_info = f"\nPost: <code>{row['post_url']}</code>" if row.get("post_url") else ""
            if charge:
                rate = await smm_api.get_usd_to_inr()
                charge_inr = float(charge) * rate
                charge_info = f"\nCharged: <code>\u20b9{charge_inr:.4f} INR</code>"
            else:
                charge_info = ""
            try:
                await bot.send_message(
                    chat_id=config.allowed_user_id,
                    text=(
                        f"🔔 <b>Order Update</b>\n\n"
                        f"{emoji} Order <code>#{smm_id}</code> → <b>{new_status}</b>\n"
                        f"Service: {row['service_type'].title()}"
                        f"{post_info}"
                        f"{charge_info}"
                    ),
                    parse_mode="HTML",
                )
            except Exception as exc:
                logger.error("Failed to send status notification: %s", exc)
