"""Message text. Short and plain: it has to read well as an iMessage banner."""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from strategies.rl import decode_market_state

from .assets import AssetSpec

_TREND = ["SuperTrend down", "SuperTrend up"]
_RSI = ["RSI weak", "RSI neutral", "RSI strong"]
_MOMENTUM = ["momentum falling", "momentum flat", "momentum rising"]
_VOL = ["calm", "volatile"]


def fmt_price(p: float) -> str:
    """Price with enough significant digits for sub-cent coins like PEPE."""
    if p >= 100:
        return f"${p:,.2f}"
    if p >= 1:
        return f"${p:,.3f}"
    if p >= 0.01:
        return f"${p:.4f}"
    return f"${p:.{3 - math.floor(math.log10(p))}f}"  # three significant digits


def fmt_qty(q: float) -> str:
    if q >= 100:
        return f"{q:,.0f}"
    if q >= 0.01:
        return f"{q:,.4f}".rstrip("0").rstrip(".")
    return f"{q:.3g}" if q > 0 else "0"   # dust like 0.00000043 must not render as 0


def explain_state(market_state: int) -> str:
    d = decode_market_state(market_state)
    return " · ".join([_TREND[d["trend"]], _RSI[d["rsi"]], _MOMENTUM[d["momentum"]], _VOL[d["volatility"]]])


def _holding_line(asset: AssetSpec, price: float) -> Optional[str]:
    if asset.quantity <= 0:
        return None
    value = asset.quantity * price
    line = f"You hold {fmt_qty(asset.quantity)} {asset.symbol} ≈ ${value:,.2f}"
    basis = asset.cost_basis_per_unit
    if basis:
        line += f" ({price / basis - 1:+.1%} vs cost)"
    return line


def _record_line(trades: List[Dict[str, Any]]) -> Optional[str]:
    if not trades:
        return None
    wins = sum(1 for t in trades if t["pnl_pct"] > 0)
    total = 1.0
    for t in trades:
        total *= 1 + t["pnl_pct"]
    return f"Paper record: {len(trades)} trade(s), {wins} win(s), {total - 1:+.1%} net"


def _validation_line(v: Optional[Dict[str, Any]]) -> Optional[str]:
    if not v:
        return None
    return (f"Out-of-sample: {v['holdout_return']:+.1%} vs buy&hold {v['buy_hold_return']:+.1%} "
            f"over {v['holdout_bars']} bars")


def _market_line(price: float, details: Optional[Dict[str, Any]]) -> str:
    line = f"Price {fmt_price(price)}"
    if details and details.get("change_24h_pct") is not None:
        line += f" ({details['change_24h_pct']:+.1f}% 24h)"
    return line


def signal_message(asset: AssetSpec, action: str, price: float, market_state: int, confidence: float,
                   state_trades: List[Dict[str, Any]], validation: Optional[Dict[str, Any]],
                   details: Optional[Dict[str, Any]], timeframe: str) -> str:
    verdict = {"BUY": "BUY — agent wants in", "SELL": "SELL — agent wants out"}[action]
    lines = [f"{asset.title} · {verdict}", _market_line(price, details),
             f"Why: {explain_state(market_state)} (confidence {confidence:.0%}, {timeframe} bars)",
             _holding_line(asset, price), _record_line(state_trades), _validation_line(validation),
             "Signal only — no order placed."]
    return "\n".join(l for l in lines if l)


def heartbeat_message(asset: AssetSpec, price: float, position: int, armed: bool,
                      validation: Optional[Dict[str, Any]], details: Optional[Dict[str, Any]]) -> str:
    if armed:
        stance = "holding (agent is long)" if position else "in cash (agent is flat)"
        status = f"Check-in: {stance}, no change."
    else:
        why = f" ({validation['reason']})" if validation else ""
        status = f"Check-in: benched — no validated edge right now{why}. Watching, not signalling."
    lines = [f"{asset.title} · {status}", _market_line(price, details), _holding_line(asset, price),
             _validation_line(validation)]
    return "\n".join(l for l in lines if l)


def failure_message(asset: AssetSpec, count: int, error: str) -> str:
    return f"{asset.title} · ⚠️ {count} failed cycles in a row. Last error: {error[:160]}"
