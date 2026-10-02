"""Portfolio configuration: which coins, what is held, and how each agent behaves."""

from __future__ import annotations

import os
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "configs" / "portfolio.yaml"


def _pick(cls, params: Optional[Dict[str, Any]]):
    """Build dataclass ``cls`` from ``params``, rejecting unknown keys loudly."""
    params = dict(params or {})
    names = {f.name for f in fields(cls)}
    unknown = set(params) - names
    if unknown:
        raise ValueError(f"unknown {cls.__name__} setting(s): {sorted(unknown)}")
    return cls(**params)


@dataclass
class LearningConfig:
    retrain_every_hours: float = 24.0
    holdout_fraction: float = 0.25      # newest slice withheld to validate each retrain
    min_holdout_return: float = 0.0     # log return after costs the holdout must beat
    min_holdout_trades: int = 1         # an agent that never trades has shown no edge
    max_champion_age_days: float = 14.0  # how long a validated model may outlive a failed retrain


@dataclass
class SignalConfig:
    min_confidence: float = 0.15   # Q-margin confidence below which a change is suppressed
    cooldown_bars: int = 4         # minimum bars between signals for one asset
    max_per_day: int = 6           # hard cap on signal messages per asset per UTC day
    heartbeat_hours: float = 24.0  # check-in message if the asset has been silent this long (0 = off)
    failure_alert_after: int = 3   # consecutive failed cycles before an error message


@dataclass
class AssetSpec:
    symbol: str
    name: str = ""
    emoji: str = "🪙"
    coingecko_id: Optional[str] = None
    quantity: float = 0.0
    cost_usd: Optional[float] = None
    assume_holding: bool = True    # start the virtual position long when quantity > 0
    notify: bool = True
    recipient: Optional[str] = None  # per-asset iMessage handle or chat guid (own thread)
    pairs: Dict[str, str] = field(default_factory=dict)  # provider -> market symbol
    rl: Dict[str, Any] = field(default_factory=dict)     # overrides of rl_defaults

    @property
    def cost_basis_per_unit(self) -> Optional[float]:
        if self.cost_usd and self.quantity > 0:
            return self.cost_usd / self.quantity
        return None

    @property
    def title(self) -> str:
        return f"{self.emoji} {self.symbol}-Bot"


@dataclass
class Portfolio:
    timeframe: str = "1h"
    history_bars: int = 1500
    poll_seconds: int = 300
    data_dir: str = "data/crypto_agents"
    providers: List[str] = field(default_factory=lambda: ["binanceus", "binance", "kraken", "coinbase"])
    learning: LearningConfig = field(default_factory=LearningConfig)
    signals: SignalConfig = field(default_factory=SignalConfig)
    rl_defaults: Dict[str, Any] = field(default_factory=dict)
    notifier: Dict[str, Any] = field(default_factory=dict)
    assets: List[AssetSpec] = field(default_factory=list)

    def rl_params(self, asset: AssetSpec) -> Dict[str, Any]:
        params = {**self.rl_defaults, **asset.rl}
        if "features" in self.rl_defaults and "features" in asset.rl:  # merge, don't replace
            params["features"] = {**self.rl_defaults["features"], **asset.rl["features"]}
        return params

    def select(self, symbols: Optional[List[str]]) -> List[AssetSpec]:
        if not symbols:
            return list(self.assets)
        wanted = {s.upper() for s in symbols}
        chosen = [a for a in self.assets if a.symbol.upper() in wanted]
        missing = wanted - {a.symbol.upper() for a in chosen}
        if missing:
            raise ValueError(f"unknown asset(s): {sorted(missing)}")
        return chosen


def load_portfolio(path: Optional[str] = None, notifier_path: Optional[str] = None) -> Portfolio:
    """Load the portfolio YAML, then overlay the (gitignored) notifier settings."""
    raw = yaml.safe_load(Path(path or DEFAULT_CONFIG).read_text()) or {}
    assets = [_pick(AssetSpec, a) for a in raw.pop("assets", [])]
    if not assets:
        raise ValueError("portfolio config defines no assets")
    if len({a.symbol.upper() for a in assets}) != len(assets):
        raise ValueError("duplicate asset symbols in portfolio config")

    learning = _pick(LearningConfig, raw.pop("learning", None))
    signals = _pick(SignalConfig, raw.pop("signals", None))
    portfolio = _pick(Portfolio, {**raw, "learning": learning, "signals": signals, "assets": assets})

    notifier_file = Path(notifier_path) if notifier_path else DEFAULT_CONFIG.parent / "notifier.yaml"
    if notifier_file.exists():
        portfolio.notifier = yaml.safe_load(notifier_file.read_text()) or {}
    if os.environ.get("CT_IMESSAGE_RECIPIENT"):
        portfolio.notifier.setdefault("imessage", {})["recipient"] = os.environ["CT_IMESSAGE_RECIPIENT"]
    return portfolio
