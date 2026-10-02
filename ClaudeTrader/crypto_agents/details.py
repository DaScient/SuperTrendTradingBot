"""Latest asset details (price, 24h change, volume, market cap) from CoinGecko."""

from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, Optional

import requests

logger = logging.getLogger(__name__)
URL = "https://api.coingecko.com/api/v3/coins/markets"


def fetch_details(ids: Iterable[str], session: Optional[requests.Session] = None) -> Dict[str, Dict[str, Any]]:
    """Return ``{coingecko_id: details}``. Best-effort: failure yields ``{}`` - this is
    message colour and must never block a signal."""
    ids = sorted({i for i in ids if i})
    if not ids:
        return {}
    try:
        resp = (session or requests).get(
            URL, params={"vs_currency": "usd", "ids": ",".join(ids), "price_change_percentage": "24h"},
            timeout=15, headers={"User-Agent": "ClaudeTrader/1.0"})
        resp.raise_for_status()
        return {
            row["id"]: {
                "price": row.get("current_price"),
                "change_24h_pct": row.get("price_change_percentage_24h"),
                "volume_24h": row.get("total_volume"),
                "market_cap": row.get("market_cap"),
                "ath_change_pct": row.get("ath_change_percentage"),
            }
            for row in resp.json()
        }
    except (requests.RequestException, ValueError, KeyError) as exc:
        logger.warning(f"CoinGecko details unavailable: {exc}")
        return {}
