"""
Live candle data: exchange providers with fallback, plus an on-disk cache.

Every provider returns raw rows ``[open_ms, open, high, low, close, volume]``,
oldest first. :class:`CandleStore` merges them into a per-asset cache, keeps
only *closed* bars (an in-progress candle would make the RL state - and so the
signal - flicker), and returns the dict-of-lists shape the RL code expects.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

import requests

logger = logging.getLogger(__name__)

TIMEFRAME_SECONDS = {"5m": 300, "15m": 900, "1h": 3600, "4h": 14400, "1d": 86400}
Row = List[float]


class ProviderError(RuntimeError):
    """A provider could not serve the request (bad pair, rate limit, outage)."""


class Provider:
    name = ""
    max_per_call = 0

    def __init__(self, session: Optional[requests.Session] = None, timeout: float = 15.0, retries: int = 3):
        self.session = session or requests.Session()
        self.timeout = timeout
        self.retries = retries

    def _get(self, url: str, params: Dict[str, Any]) -> Any:
        """GET JSON, retrying transient failures (network, 429, 5xx) with backoff."""
        last: Optional[Exception] = None
        for attempt in range(self.retries):
            try:
                resp = self.session.get(url, params=params, timeout=self.timeout,
                                        headers={"User-Agent": "ClaudeTrader/1.0"})
            except requests.RequestException as exc:
                last = exc
            else:
                if resp.status_code == 200:
                    try:
                        return resp.json()
                    except ValueError as exc:
                        last = exc
                elif resp.status_code == 429 or resp.status_code >= 500:
                    last = ProviderError(f"{self.name} HTTP {resp.status_code}")
                else:  # other 4xx (bad pair, geo-block): retrying cannot help
                    raise ProviderError(f"{self.name} HTTP {resp.status_code}: {resp.text[:120]}")
            if attempt < self.retries - 1:
                time.sleep(min(2 ** attempt, 8))
        raise ProviderError(f"{self.name} request failed: {last}")

    def fetch(self, market: str, timeframe: str, bars: int) -> List[Row]:
        raise NotImplementedError

    @staticmethod
    def _check(timeframe: str) -> int:
        if timeframe not in TIMEFRAME_SECONDS:
            raise ProviderError(f"unsupported timeframe {timeframe}")
        return TIMEFRAME_SECONDS[timeframe]


class BinanceProvider(Provider):
    """Binance / Binance.US spot klines (same API, different host and listings)."""

    max_per_call = 1000

    def __init__(self, name: str = "binance", base_url: str = "https://api.binance.com", **kw):
        super().__init__(**kw)
        self.name, self.base_url = name, base_url

    def fetch(self, market: str, timeframe: str, bars: int) -> List[Row]:
        self._check(timeframe)
        rows: Dict[int, Row] = {}
        end_time: Optional[int] = None
        while len(rows) < bars:
            params: Dict[str, Any] = {"symbol": market, "interval": timeframe,
                                      "limit": min(self.max_per_call, bars - len(rows))}
            if end_time is not None:
                params["endTime"] = end_time
            data = self._get(f"{self.base_url}/api/v3/klines", params)
            if not isinstance(data, list) or not data:
                break
            batch = {int(k[0]): [int(k[0])] + [float(x) for x in k[1:6]] for k in data}
            before = len(rows)
            rows.update(batch)
            if len(rows) == before:
                break
            end_time = min(batch) - 1
        if not rows:
            raise ProviderError(f"{self.name}: no candles for {market}")
        return [rows[k] for k in sorted(rows)]


class KrakenProvider(Provider):
    """Kraken OHLC. Serves at most the latest 720 bars per request."""

    name = "kraken"
    max_per_call = 720
    INTERVALS = {"5m": 5, "15m": 15, "1h": 60, "4h": 240, "1d": 1440}

    def fetch(self, market: str, timeframe: str, bars: int) -> List[Row]:
        self._check(timeframe)
        data = self._get("https://api.kraken.com/0/public/OHLC",
                         {"pair": market, "interval": self.INTERVALS[timeframe]})
        if data.get("error"):
            raise ProviderError(f"kraken: {data['error']}")
        series = next((v for k, v in data.get("result", {}).items() if k != "last"), None)
        if not series:
            raise ProviderError(f"kraken: no candles for {market}")
        # row: [time_s, open, high, low, close, vwap, volume, count]
        rows = [[int(r[0]) * 1000, float(r[1]), float(r[2]), float(r[3]), float(r[4]), float(r[6])]
                for r in series]
        return rows[-bars:]


class CoinbaseProvider(Provider):
    """Coinbase Exchange candles, 300 per call, paged by time window."""

    name = "coinbase"
    max_per_call = 300
    GRANULARITY = {"5m": 300, "15m": 900, "1h": 3600, "1d": 86400}  # no 4h on Coinbase

    def fetch(self, market: str, timeframe: str, bars: int) -> List[Row]:
        if timeframe not in self.GRANULARITY:
            raise ProviderError(f"coinbase: unsupported timeframe {timeframe}")
        gran = self.GRANULARITY[timeframe]
        rows: Dict[int, Row] = {}
        end = int(time.time())
        while len(rows) < bars:
            start = end - gran * self.max_per_call
            data = self._get(f"https://api.exchange.coinbase.com/products/{market}/candles", {
                "granularity": gran,
                "start": datetime.fromtimestamp(start, timezone.utc).isoformat(),
                "end": datetime.fromtimestamp(end, timezone.utc).isoformat(),
            })
            if not isinstance(data, list) or not data:
                break
            # row: [time_s, low, high, open, close, volume], newest first
            for r in data:
                ts = int(r[0]) * 1000
                rows[ts] = [ts, float(r[3]), float(r[2]), float(r[1]), float(r[4]), float(r[5])]
            end = start
        if not rows:
            raise ProviderError(f"coinbase: no candles for {market}")
        return [rows[k] for k in sorted(rows)][-bars:]


def build_providers(names: Sequence[str], session: Optional[requests.Session] = None) -> Dict[str, Provider]:
    makers: Dict[str, Callable[[], Provider]] = {
        "binanceus": lambda: BinanceProvider("binanceus", "https://api.binance.us", session=session),
        "binance": lambda: BinanceProvider("binance", "https://api.binance.com", session=session),
        "kraken": lambda: KrakenProvider(session=session),
        "coinbase": lambda: CoinbaseProvider(session=session),
    }
    unknown = [n for n in names if n not in makers]
    if unknown:
        raise ValueError(f"unknown data provider(s): {unknown}")
    return {n: makers[n]() for n in names}


def fetch_with_fallback(
    providers: Dict[str, Provider], pairs: Dict[str, str], timeframe: str, bars: int
) -> tuple:
    """Try providers in order; return ``(provider_name, rows)`` from the first that works."""
    errors = []
    for name, provider in providers.items():
        market = pairs.get(name)
        if not market:
            continue
        try:
            return name, provider.fetch(market, timeframe, bars)
        except ProviderError as exc:
            errors.append(str(exc))
            logger.warning(f"{exc}; trying next provider")
    if not errors:
        raise ProviderError("no configured provider has a pair for this asset")
    raise ProviderError("all providers failed: " + "; ".join(errors))


class CandleStore:
    """Per-asset candle cache on disk (closed bars only)."""

    def __init__(self, path: Path, timeframe: str, keep: int = 5000, clock: Callable[[], float] = time.time):
        self.path, self.timeframe, self.keep, self.clock = Path(path), timeframe, keep, clock
        self.bar_ms = TIMEFRAME_SECONDS[timeframe] * 1000
        self.rows: Dict[int, Row] = {}
        self.provider: Optional[str] = None
        if self.path.exists():
            blob = json.loads(self.path.read_text())
            self.rows = {int(r[0]): r for r in blob["rows"]}
            self.provider = blob.get("provider")

    def merge(self, rows: Sequence[Row], provider: str) -> int:
        """Merge fetched rows, dropping the still-forming candle. Returns bars added."""
        now_ms = int(self.clock() * 1000)
        closed = [r for r in rows if int(r[0]) + self.bar_ms <= now_ms]
        before = len(self.rows)
        for r in closed:
            self.rows[int(r[0])] = [int(r[0])] + [float(x) for x in r[1:6]]
        for ts in sorted(self.rows)[:-self.keep]:
            del self.rows[ts]
        self.provider = provider
        self._save()
        return len(self.rows) - before

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"provider": self.provider, "timeframe": self.timeframe,
                                   "rows": [self.rows[k] for k in sorted(self.rows)]}))
        tmp.replace(self.path)

    def __len__(self) -> int:
        return len(self.rows)

    def ohlcv(self) -> Dict[str, List[float]]:
        ordered = [self.rows[k] for k in sorted(self.rows)]
        return {
            "timestamp": [int(r[0]) for r in ordered],
            "open": [r[1] for r in ordered], "high": [r[2] for r in ordered],
            "low": [r[3] for r in ordered], "close": [r[4] for r in ordered],
            "volume": [r[5] for r in ordered],
        }
