"""SQLite database layer using aiosqlite."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import aiosqlite

from config import config

logger = logging.getLogger(__name__)

DB_PATH = config.db_path

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_CREATE_PRESETS = """
CREATE TABLE IF NOT EXISTS presets (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    name                    TEXT    UNIQUE NOT NULL,
    subscribers_enabled     INTEGER NOT NULL DEFAULT 0,
    subscribers_service_id  INTEGER,
    subscribers_quantity    INTEGER,
    views_enabled           INTEGER NOT NULL DEFAULT 0,
    views_service_id        INTEGER,
    views_quantity          INTEGER,
    reactions_enabled       INTEGER NOT NULL DEFAULT 0,
    reactions_service_id    INTEGER,
    reactions_quantity      INTEGER,
    post_count              INTEGER NOT NULL DEFAULT 10,
    created_at              TEXT    NOT NULL
);
"""

_CREATE_ORDERS = """
CREATE TABLE IF NOT EXISTS orders (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    smm_order_id    INTEGER NOT NULL,
    channel_url     TEXT    NOT NULL,
    post_url        TEXT,
    service_type    TEXT    NOT NULL,
    service_id      INTEGER NOT NULL,
    quantity        INTEGER NOT NULL,
    status          TEXT    NOT NULL DEFAULT 'Pending',
    charge          REAL,
    remains         INTEGER,
    preset_name     TEXT,
    created_at      TEXT    NOT NULL,
    updated_at      TEXT    NOT NULL
);
"""


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------

async def init_db() -> None:
    """Create tables if they do not already exist."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(_CREATE_PRESETS)
        await db.execute(_CREATE_ORDERS)
        await db.commit()
    logger.info("Database initialised at %s", DB_PATH)


# ---------------------------------------------------------------------------
# Presets
# ---------------------------------------------------------------------------

async def save_preset(preset: dict[str, Any]) -> None:
    """Insert or replace a preset by name."""
    now = datetime.utcnow().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO presets (
                name,
                subscribers_enabled, subscribers_service_id, subscribers_quantity,
                views_enabled, views_service_id, views_quantity,
                reactions_enabled, reactions_service_id, reactions_quantity,
                post_count, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                subscribers_enabled    = excluded.subscribers_enabled,
                subscribers_service_id = excluded.subscribers_service_id,
                subscribers_quantity   = excluded.subscribers_quantity,
                views_enabled          = excluded.views_enabled,
                views_service_id       = excluded.views_service_id,
                views_quantity         = excluded.views_quantity,
                reactions_enabled      = excluded.reactions_enabled,
                reactions_service_id   = excluded.reactions_service_id,
                reactions_quantity     = excluded.reactions_quantity,
                post_count             = excluded.post_count
            """,
            (
                preset["name"],
                int(preset.get("subscribers_enabled", False)),
                preset.get("subscribers_service_id"),
                preset.get("subscribers_quantity"),
                int(preset.get("views_enabled", False)),
                preset.get("views_service_id"),
                preset.get("views_quantity"),
                int(preset.get("reactions_enabled", False)),
                preset.get("reactions_service_id"),
                preset.get("reactions_quantity"),
                preset.get("post_count", config.default_post_count),
                now,
            ),
        )
        await db.commit()


async def get_presets() -> list[dict[str, Any]]:
    """Return all saved presets as a list of dicts."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM presets ORDER BY name") as cur:
            rows = await cur.fetchall()
    return [dict(r) for r in rows]


async def get_preset_by_name(name: str) -> dict[str, Any] | None:
    """Return a single preset dict or None if not found."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM presets WHERE name = ?", (name,)) as cur:
            row = await cur.fetchone()
    return dict(row) if row else None


async def delete_preset(name: str) -> bool:
    """Delete a preset by name. Returns True if a row was deleted."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("DELETE FROM presets WHERE name = ?", (name,))
        await db.commit()
        return cur.rowcount > 0


# ---------------------------------------------------------------------------
# Orders
# ---------------------------------------------------------------------------

async def save_order(order: dict[str, Any]) -> int:
    """Insert a new order row and return its local DB id."""
    now = datetime.utcnow().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """
            INSERT INTO orders (
                smm_order_id, channel_url, post_url, service_type,
                service_id, quantity, status, charge, remains,
                preset_name, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                order["smm_order_id"],
                order["channel_url"],
                order.get("post_url"),
                order["service_type"],
                order["service_id"],
                order["quantity"],
                order.get("status", "Pending"),
                order.get("charge"),
                order.get("remains"),
                order.get("preset_name"),
                now,
                now,
            ),
        )
        await db.commit()
        return cur.lastrowid  # type: ignore[return-value]


async def update_order_status(
    smm_order_id: int,
    status: str,
    charge: float | None = None,
    remains: int | None = None,
) -> None:
    """Update status (and optionally charge/remains) for a given SMM order ID."""
    now = datetime.utcnow().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            UPDATE orders
            SET status = ?, charge = COALESCE(?, charge),
                remains = COALESCE(?, remains), updated_at = ?
            WHERE smm_order_id = ?
            """,
            (status, charge, remains, now, smm_order_id),
        )
        await db.commit()


async def get_pending_orders() -> list[dict[str, Any]]:
    """Return all orders that are not yet in a terminal state."""
    terminal = ("Completed", "Partial", "Canceled", "Refunded")
    placeholders = ",".join("?" * len(terminal))
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            f"SELECT * FROM orders WHERE status NOT IN ({placeholders})", terminal
        ) as cur:
            rows = await cur.fetchall()
    return [dict(r) for r in rows]


async def get_recent_orders(limit: int = 20) -> list[dict[str, Any]]:
    """Return the most recent *limit* orders."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM orders ORDER BY created_at DESC LIMIT ?", (limit,)
        ) as cur:
            rows = await cur.fetchall()
    return [dict(r) for r in rows]
