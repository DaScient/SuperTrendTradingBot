# ClaudeTrader

Advanced AI-Powered Trading Intelligence System

See the [full README](../README.md) for complete documentation.

## Quick Start

```bash
cd ClaudeTrader
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...   # optional; mock LLM responses otherwise
python -m core.engine
pytest tests/
```

## Features

- 🤖 Claude-powered trading assistant (Anthropic API, mock fallback without a key)
- 📊 SuperTrend strategy with an event-driven backtester
- 🎯 ATR-based risk management and performance metrics
- 🌐 Static web dashboard
- 🔌 Integration with the SuperTrend bot

Market data and the RAG knowledge base are currently mocks, and the REST API in
`API.md` is a design spec that has not been implemented. See the
[status table](../README.md#what-works-today).

## Documentation

- [Full README](../README.md)
- [API design spec](API.md)
- [Demo Notebook](../notebooks/demo_claudetrader.ipynb)

## License

See parent repository LICENSE file.
