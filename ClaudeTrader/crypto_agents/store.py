"""Durable per-asset state: position, paper track record, validation, outbox."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class AgentState:
    position: int = 0                       # virtual spot position: 1 = holding, 0 = in cash
    entry_price: Optional[float] = None
    entry_ts: Optional[int] = None
    last_bar_ts: Optional[int] = None       # newest closed bar already evaluated
    last_signal_bar_ts: Optional[int] = None
    last_train_ts: Optional[float] = None   # epoch seconds
    last_message_ts: float = 0.0
    sent_today: Dict[str, int] = field(default_factory=dict)  # {"YYYY-MM-DD": count}
    validation: Optional[Dict[str, Any]] = None
    champion_valid_until: Optional[float] = None   # epoch seconds; model is armed until then
    trades: List[Dict[str, Any]] = field(default_factory=list)  # closed paper trades
    outbox: List[Dict[str, Any]] = field(default_factory=list)  # unsent messages, oldest first
    consecutive_failures: int = 0
    failure_alerted: bool = False
    initialized: bool = False

    def armed(self, now: float) -> bool:
        """True while the deployed model's last passing validation has not expired."""
        return self.champion_valid_until is not None and now < self.champion_valid_until


class StateStore:
    def __init__(self, directory: Path):
        self.dir = Path(directory)
        self.state_path = self.dir / "state.json"
        self.model_path = self.dir / "model.json"

    def load(self) -> AgentState:
        if not self.state_path.exists():
            return AgentState()
        raw = json.loads(self.state_path.read_text())
        names = {f.name for f in fields(AgentState)}
        return AgentState(**{k: v for k, v in raw.items() if k in names})

    def save(self, state: AgentState) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        tmp = self.state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(asdict(state), indent=1))
        tmp.replace(self.state_path)
