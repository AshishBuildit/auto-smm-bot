"""Async wrapper around the PRM4U SMM panel API (https://prm4u.com/api/v2)."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp

from config import config

logger = logging.getLogger(__name__)

API_URL = config.smm_api_url


class SMMApi:
    """Async PRM4U API client. Reuses a single aiohttp session for the bot lifetime."""

    def __init__(self) -> None:
        self._session: aiohttp.ClientSession | None = None

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Create the underlying HTTP session. Call once on bot startup."""
        self._session = aiohttp.ClientSession()

    async def stop(self) -> None:
        """Close the underlying HTTP session. Call once on bot shutdown."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def _post(self, payload: dict[str, Any]) -> dict[str, Any] | list[Any]:
        """POST to the API and return the parsed JSON response."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()

        payload["key"] = config.smm_api_key
        try:
            async with self._session.post(API_URL, data=payload) as resp:
                resp.raise_for_status()
                return await resp.json(content_type=None)
        except aiohttp.ClientError as exc:
            logger.error("SMM API request failed: %s", exc)
            return {"error": str(exc)}

    # ------------------------------------------------------------------
    # Public API methods
    # ------------------------------------------------------------------

    async def get_balance(self) -> dict[str, Any]:
        """Return user balance dict: {balance, currency} or {error}."""
        return await self._post({"action": "balance"})  # type: ignore[return-value]

    async def get_usd_to_inr(self) -> float:
        """Fetch the live USD→INR exchange rate from open.er-api.com.

        Returns the rate on success, or falls back to 83.0 if the request fails.
        """
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        try:
            url = "https://open.er-api.com/v6/latest/USD"
            async with self._session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                resp.raise_for_status()
                data = await resp.json()
                return float(data["rates"]["INR"])
        except Exception as exc:
            logger.warning("Exchange rate fetch failed (%s) — using fallback 83.0", exc)
            return 83.0

    async def get_services(self) -> list[dict[str, Any]]:
        """Return list of all available services."""
        result = await self._post({"action": "services"})
        if isinstance(result, list):
            return result
        logger.error("Unexpected services response: %s", result)
        return []

    async def add_order(
        self,
        service: int,
        link: str,
        quantity: int,
    ) -> dict[str, Any]:
        """Place a single order and return {order: id} or {error}."""
        return await self._post(  # type: ignore[return-value]
            {
                "action": "add",
                "service": service,
                "link": link,
                "quantity": quantity,
            }
        )

    async def get_status(self, order_id: int) -> dict[str, Any]:
        """Return status for a single order."""
        return await self._post({"action": "status", "order": order_id})  # type: ignore[return-value]

    async def get_multi_status(self, order_ids: list[int]) -> dict[str, Any]:
        """Return status for multiple orders (up to 100). Keys are order IDs as strings."""
        ids_str = ",".join(str(i) for i in order_ids)
        result = await self._post({"action": "status", "orders": ids_str})
        if isinstance(result, dict):
            return result
        return {}

    async def cancel_orders(self, order_ids: list[int]) -> list[dict[str, Any]]:
        """Cancel multiple orders. Returns list of {order, cancel} dicts."""
        ids_str = ",".join(str(i) for i in order_ids)
        result = await self._post({"action": "cancel", "orders": ids_str})
        if isinstance(result, list):
            return result
        return [{"error": str(result)}]

    async def refill_order(self, order_id: int) -> dict[str, Any]:
        """Request a refill for a single order."""
        return await self._post({"action": "refill", "order": order_id})  # type: ignore[return-value]


# Singleton instance — imported by other modules
smm_api = SMMApi()
