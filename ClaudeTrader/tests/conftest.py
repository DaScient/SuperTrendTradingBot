"""Pytest configuration: ensure the ClaudeTrader package root is importable.

Strategies and utilities use absolute imports rooted at the ClaudeTrader
directory (e.g. ``from utils import performance``), so we add that directory to
``sys.path`` for the test session.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
