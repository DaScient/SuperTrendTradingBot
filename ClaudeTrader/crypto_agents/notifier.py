"""
iMessage delivery.

iMessage can only be sent through Apple's stack, so there are two real routes:

* :class:`IMessageNotifier` - drives Messages.app with AppleScript. Must run on a
  Mac signed in to iMessage (the intended home for ``crypto_agents run --loop``).
* :class:`BlueBubblesNotifier` - posts to a BlueBubbles server running on such a
  Mac, so the agents themselves can live on a headless box or in the cloud.

:class:`FallbackNotifier` tries them in order; :class:`ConsoleNotifier` and
:class:`FileNotifier` exist for dry runs and as a last-resort audit trail.
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


class NotifierError(RuntimeError):
    pass


class Notifier:
    name = "base"

    def send(self, recipient: Optional[str], text: str) -> None:
        raise NotImplementedError


# Arguments are passed via argv, never spliced into the script, so message text
# (which includes market data) can never break out of the AppleScript string.
_APPLESCRIPT_HANDLE = [
    "on run argv",
    "set theTarget to item 1 of argv",
    "set theText to item 2 of argv",
    "tell application \"Messages\"",
    "set theService to 1st account whose service type = iMessage",
    "send theText to participant theTarget of theService",
    "end tell",
    "end run",
]
_APPLESCRIPT_CHAT = [
    "on run argv",
    "set theTarget to item 1 of argv",
    "set theText to item 2 of argv",
    "tell application \"Messages\" to send theText to chat id theTarget",
    "end run",
]


class IMessageNotifier(Notifier):
    name = "imessage"

    def __init__(self, osascript: str = "osascript", timeout: float = 30.0,
                 runner: Callable[..., Any] = subprocess.run):
        self.osascript, self.timeout, self.runner = osascript, timeout, runner

    def send(self, recipient: Optional[str], text: str) -> None:
        if not recipient:
            raise NotifierError("no iMessage recipient configured")
        if sys.platform != "darwin" and self.runner is subprocess.run:
            raise NotifierError("AppleScript iMessage needs macOS; use the bluebubbles notifier elsewhere")
        # A chat guid ("iMessage;+;chat123...") addresses a group thread; anything else is a handle.
        script = _APPLESCRIPT_CHAT if recipient.startswith(("iMessage;", "any;")) else _APPLESCRIPT_HANDLE
        cmd = [self.osascript] + [arg for line in script for arg in ("-e", line)] + [recipient, text]
        try:
            proc = self.runner(cmd, capture_output=True, text=True, timeout=self.timeout)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise NotifierError(f"osascript failed: {exc}") from exc
        if proc.returncode != 0:
            raise NotifierError(f"Messages.app rejected the send: {proc.stderr.strip()[:200]}")


class BlueBubblesNotifier(Notifier):
    name = "bluebubbles"

    def __init__(self, url: str, password: str, session: Optional[requests.Session] = None,
                 method: str = "apple-script"):
        self.url, self.password, self.method = url.rstrip("/"), password, method
        self.session = session or requests.Session()

    def send(self, recipient: Optional[str], text: str) -> None:
        if not recipient:
            raise NotifierError("no iMessage recipient configured")
        guid = recipient if recipient.startswith(("iMessage;", "any;")) else f"iMessage;-;{recipient}"
        try:
            resp = self.session.post(
                f"{self.url}/api/v1/message/text", params={"password": self.password}, timeout=30,
                json={"chatGuid": guid, "tempGuid": str(uuid.uuid4()), "message": text, "method": self.method})
        except requests.RequestException as exc:
            raise NotifierError(f"BlueBubbles unreachable: {exc}") from exc
        if resp.status_code >= 300:
            raise NotifierError(f"BlueBubbles HTTP {resp.status_code}: {resp.text[:200]}")


class ConsoleNotifier(Notifier):
    name = "console"

    def send(self, recipient: Optional[str], text: str) -> None:
        print(f"--- message to {recipient or '(default)'} ---\n{text}\n", flush=True)


class FileNotifier(Notifier):
    """Append-only JSONL audit trail of everything that was sent."""

    name = "file"

    def __init__(self, path: Path):
        self.path = Path(path)

    def send(self, recipient: Optional[str], text: str) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a") as fh:
            fh.write(json.dumps({"recipient": recipient, "text": text}) + "\n")


class FallbackNotifier(Notifier):
    """Try each notifier in order; succeed on the first that works."""

    name = "fallback"

    def __init__(self, notifiers: List[Notifier]):
        if not notifiers:
            raise ValueError("FallbackNotifier needs at least one notifier")
        self.notifiers = notifiers

    def send(self, recipient: Optional[str], text: str) -> None:
        errors = []
        for n in self.notifiers:
            try:
                return n.send(recipient, text)
            except NotifierError as exc:
                errors.append(f"{n.name}: {exc}")
                logger.warning(f"notifier {n.name} failed: {exc}")
        raise NotifierError("; ".join(errors))


def build_notifier(cfg: Dict[str, Any], data_dir: Path, dry_run: bool = False) -> Notifier:
    """Build the notifier chain from the (gitignored) notifier config."""
    if dry_run:
        return ConsoleNotifier()
    chain: List[Notifier] = []
    for kind in cfg.get("order", ["imessage"]):
        if kind == "imessage":
            chain.append(IMessageNotifier())
        elif kind == "bluebubbles":
            bb = cfg.get("bluebubbles") or {}
            if not bb.get("url") or not bb.get("password"):
                raise ValueError("bluebubbles notifier needs url and password")
            chain.append(BlueBubblesNotifier(bb["url"], bb["password"]))
        elif kind == "console":
            chain.append(ConsoleNotifier())
        else:
            raise ValueError(f"unknown notifier: {kind}")
    return FallbackNotifier(chain)
