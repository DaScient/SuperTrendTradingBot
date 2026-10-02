"""Run every asset agent: one-shot (cron/launchd) or as a long-lived loop."""

from __future__ import annotations

import fcntl
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from .agent import AssetAgent
from .assets import Portfolio
from .details import fetch_details
from .market_data import ProviderError, build_providers
from .notifier import Notifier, build_notifier

logger = logging.getLogger(__name__)


class Runner:
    def __init__(self, portfolio: Portfolio, symbols: Optional[List[str]] = None,
                 notifier: Optional[Notifier] = None, dry_run: bool = False):
        self.portfolio = portfolio
        self.data_dir = Path(portfolio.data_dir)
        providers = build_providers(portfolio.providers)
        self.agents = [AssetAgent(a, portfolio, providers) for a in portfolio.select(symbols)]
        self.notifier = notifier or build_notifier(portfolio.notifier, self.data_dir, dry_run)
        self.default_recipient = (portfolio.notifier.get("imessage") or {}).get("recipient")

    def _lock(self):
        self.data_dir.mkdir(parents=True, exist_ok=True)
        fh = open(self.data_dir / ".lock", "w")
        try:
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            fh.close()
            raise SystemExit("another crypto_agents run is already active")
        return fh

    def run_once(self, force_train: bool = False, evaluate: bool = True) -> Dict[str, Any]:
        """One pass over every enabled asset. A failure in one never stops the others."""
        lock = self._lock()
        try:
            details = fetch_details(a.asset.coingecko_id for a in self.agents)
            report: Dict[str, Any] = {}
            for agent in self.agents:
                sym = agent.asset.symbol
                try:
                    agent.refresh_data()
                    validation = agent.learn_if_due(force=force_train)
                    detail = details.get(agent.asset.coingecko_id or "")
                    queued = agent.evaluate(detail) if evaluate and agent.asset.notify else None
                    agent.record_success()
                    report[sym] = {"retrained": validation, "message": queued}
                except ProviderError as exc:
                    note = agent.record_failure(str(exc))
                    report[sym] = {"error": str(exc), "alert": note}
                    logger.error(f"{sym}: {exc}")
                except Exception as exc:  # isolate: one coin's bug must not silence the rest
                    note = agent.record_failure(repr(exc))
                    report[sym] = {"error": repr(exc), "alert": note}
                    logger.exception(f"{sym}: cycle failed")
                finally:
                    agent.flush_outbox(self.notifier.send, self.default_recipient)
                    agent.save()
            return report
        finally:
            lock.close()

    def run_forever(self) -> None:
        while True:
            started = time.time()
            self.run_once()
            time.sleep(max(1.0, self.portfolio.poll_seconds - (time.time() - started)))

    def status(self) -> List[Dict[str, Any]]:
        now = time.time()
        rows = []
        for a in self.agents:
            s = a.state
            v = s.validation or {}
            rows.append({
                "symbol": a.asset.symbol, "position": "long" if s.position else "cash",
                "armed": s.armed(now), "bars": len(a.candles), "provider": a.candles.provider,
                "holdout_return": v.get("holdout_return"), "buy_hold": v.get("buy_hold_return"),
                "reason": v.get("reason"), "paper_trades": len(s.trades), "outbox": len(s.outbox),
                "failures": s.consecutive_failures,
            })
        return rows

    def test_notify(self) -> None:
        for a in self.agents:
            self.notifier.send(a.asset.recipient or self.default_recipient,
                               f"{a.asset.title} · test message. If you can read this, delivery works.")
