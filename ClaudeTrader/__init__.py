"""
ClaudeTrader - Advanced AI-Powered Trading Intelligence System

A comprehensive trading assistant that combines Large Language Models (LLMs),
Retrieval-Augmented Generation (RAG), and sophisticated trading strategies.
"""

__version__ = "1.0.0"
__author__ = "DASCIENT, LLC"
__license__ = "MIT"

from .core.engine import ClaudeTrader, create_trader
from .strategies import get_strategy, list_strategies

__all__ = [
    'ClaudeTrader',
    'create_trader',
    'get_strategy',
    'list_strategies',
]
