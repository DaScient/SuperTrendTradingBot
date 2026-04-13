# ClaudeTrader API Documentation

## Overview

ClaudeTrader provides a comprehensive REST API and WebSocket interface for accessing AI-powered trading intelligence. This document covers all available endpoints, parameters, and usage examples.

## Base URL

```
http://localhost:5000/api/v1
```

## Authentication

All API requests require authentication using JWT tokens or API keys.

### Get Access Token

```http
POST /api/auth/token
Content-Type: application/json

{
  "username": "your_username",
  "password": "your_password"
}
```

**Response:**
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "Bearer",
  "expires_in": 86400
}
```

### Using Token

Include the token in the Authorization header:

```http
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc...
```

## Core Endpoints

### 1. Query AI Assistant

Ask natural language questions about trading.

```http
POST /api/query
Content-Type: application/json
Authorization: Bearer {token}

{
  "question": "What's the best strategy for volatile markets?",
  "context": {
    "symbol": "BTC/USD",
    "timeframe": "1h"
  }
}
```

**Response:**
```json
{
  "query": "What's the best strategy for volatile markets?",
  "response": "For volatile markets, I recommend combining SuperTrend with ATR-based position sizing...",
  "sources": [
    "technical_indicators",
    "risk_management",
    "market_dynamics"
  ],
  "confidence": 0.87,
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### 2. Get Trading Signals

Retrieve trading signals for a specific symbol.

```http
GET /api/signals/{symbol}?timeframe=1h&strategies=supertrend,multi_factor
Authorization: Bearer {token}
```

**Parameters:**
- `symbol` (required): Trading pair (e.g., BTC/USD)
- `timeframe` (optional): Chart timeframe (default: 1h)
- `strategies` (optional): Comma-separated strategy names

**Response:**
```json
{
  "symbol": "BTC/USD",
  "timeframe": "1h",
  "signals": [
    {
      "action": "buy",
      "confidence": 0.85,
      "strategy": "supertrend",
      "price": 67234.50,
      "timestamp": "2024-01-15T10:30:00Z",
      "price_target": 69000.00,
      "stop_loss": 65500.00,
      "reasoning": "Price crossed above SuperTrend line with strong volume confirmation"
    }
  ]
}
```

### 3. Analyze Strategy

Backtest and analyze a trading strategy.

```http
POST /api/strategy/analyze
Content-Type: application/json
Authorization: Bearer {token}

{
  "strategy": "supertrend",
  "symbol": "BTC/USD",
  "parameters": {
    "atr_period": 10,
    "multiplier": 3.0
  },
  "backtest_period": "90d"
}
```

**Response:**
```json
{
  "strategy": "supertrend",
  "symbol": "BTC/USD",
  "parameters": {
    "atr_period": 10,
    "multiplier": 3.0
  },
  "performance": {
    "total_return": 0.245,
    "win_rate": 0.62,
    "sharpe_ratio": 2.1,
    "max_drawdown": -0.083,
    "num_trades": 45
  },
  "ai_insights": "SuperTrend strategy performs exceptionally well in trending markets..."
}
```

### 4. Portfolio Analysis

Get comprehensive portfolio performance analysis.

```http
GET /api/portfolio/analysis?period=30d
Authorization: Bearer {token}
```

**Response:**
```json
{
  "period": "30d",
  "metrics": {
    "total_return": 0.245,
    "sharpe_ratio": 2.1,
    "max_drawdown": -0.083,
    "win_rate": 0.62
  },
  "positions": [
    {
      "symbol": "BTC/USD",
      "quantity": 0.5,
      "entry_price": 65000.00,
      "current_price": 67234.50,
      "pnl": 1117.25,
      "pnl_pct": 0.0343
    }
  ],
  "ai_insights": "Portfolio showing strong performance with good risk-adjusted returns..."
}
```

### 5. Sentiment Analysis

Get market sentiment analysis for a symbol.

```http
GET /api/sentiment/{symbol}
Authorization: Bearer {token}
```

**Response:**
```json
{
  "symbol": "BTC/USD",
  "timestamp": "2024-01-15T10:30:00Z",
  "overall_sentiment": 0.72,
  "sources": {
    "news": 0.75,
    "twitter": 0.70,
    "reddit": 0.68
  },
  "volume": 15420,
  "trending": true,
  "analysis": "Strong bullish sentiment driven by institutional adoption news..."
}
```

### 6. Compare Strategies

Compare performance of multiple strategies.

```http
POST /api/strategy/compare
Content-Type: application/json
Authorization: Bearer {token}

{
  "strategies": ["supertrend", "multi_factor", "hybrid"],
  "symbol": "BTC/USD",
  "backtest_period": "90d"
}
```

**Response:**
```json
{
  "comparison": {
    "supertrend": {
      "total_return": 0.245,
      "sharpe_ratio": 2.1,
      "win_rate": 0.62
    },
    "multi_factor": {
      "total_return": 0.198,
      "sharpe_ratio": 1.8,
      "win_rate": 0.58
    },
    "hybrid": {
      "total_return": 0.267,
      "sharpe_ratio": 2.3,
      "win_rate": 0.64
    }
  },
  "recommendation": "Hybrid strategy shows best risk-adjusted performance...",
  "best_strategy": "hybrid"
}
```

## Market Data Endpoints

### Get Market Data

```http
GET /api/market/{symbol}?timeframe=1h&limit=100
Authorization: Bearer {token}
```

### Get Supported Symbols

```http
GET /api/market/symbols
Authorization: Bearer {token}
```

### Get Market News

```http
GET /api/market/news?symbol=BTC&limit=10
Authorization: Bearer {token}
```

## RAG Knowledge Base Endpoints

### Add Document

```http
POST /api/knowledge/document
Content-Type: application/json
Authorization: Bearer {token}

{
  "content": "Document content here...",
  "source": "research_paper",
  "metadata": {
    "category": "strategy",
    "author": "John Doe"
  }
}
```

### Search Knowledge Base

```http
POST /api/knowledge/search
Content-Type: application/json
Authorization: Bearer {token}

{
  "query": "RSI indicator usage",
  "top_k": 5
}
```

## WebSocket API

### Connection

Connect to WebSocket server at:

```
ws://localhost:5001/ws
```

### Authentication

Send authentication message after connecting:

```json
{
  "type": "auth",
  "token": "your_jwt_token"
}
```

### Subscribe to Events

```json
{
  "type": "subscribe",
  "channels": ["signals", "market_updates", "news"]
}
```

### Event Types

**Market Update:**
```json
{
  "type": "market_update",
  "symbol": "BTC/USD",
  "price": 67234.50,
  "change_24h": 0.0234,
  "timestamp": "2024-01-15T10:30:00Z"
}
```

**Signal Alert:**
```json
{
  "type": "signal_alert",
  "signal": {
    "symbol": "BTC/USD",
    "action": "buy",
    "confidence": 0.85,
    "strategy": "supertrend"
  }
}
```

**News Update:**
```json
{
  "type": "news_update",
  "article": {
    "title": "Bitcoin reaches new highs",
    "source": "CryptoNews",
    "sentiment": 0.8,
    "url": "https://..."
  }
}
```

## Rate Limits

- Default: 60 requests per minute
- Authenticated users: 120 requests per minute
- Premium users: 300 requests per minute

## Error Responses

All errors follow this format:

```json
{
  "error": {
    "code": "invalid_parameter",
    "message": "Symbol 'INVALID' is not supported",
    "details": {
      "parameter": "symbol",
      "supported_symbols": ["BTC/USD", "ETH/USD", ...]
    }
  }
}
```

### Error Codes

- `invalid_parameter`: Invalid request parameter
- `authentication_failed`: Invalid or expired token
- `rate_limit_exceeded`: Too many requests
- `resource_not_found`: Requested resource doesn't exist
- `internal_error`: Server error

## Code Examples

### Python

```python
import requests

# Get token
response = requests.post('http://localhost:5000/api/auth/token', json={
    'username': 'your_username',
    'password': 'your_password'
})
token = response.json()['access_token']

# Query AI assistant
headers = {'Authorization': f'Bearer {token}'}
response = requests.post('http://localhost:5000/api/query',
    headers=headers,
    json={
        'question': 'Should I buy BTC right now?',
        'context': {'symbol': 'BTC/USD'}
    }
)
result = response.json()
print(result['response'])

# Get trading signals
response = requests.get('http://localhost:5000/api/signals/BTC/USD',
    headers=headers,
    params={'timeframe': '1h'}
)
signals = response.json()['signals']
for signal in signals:
    print(f"{signal['action']} {signal['symbol']} @ {signal['price']}")
```

### JavaScript

```javascript
// Get token
const response = await fetch('http://localhost:5000/api/auth/token', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({
    username: 'your_username',
    password: 'your_password'
  })
});
const {access_token} = await response.json();

// Query AI assistant
const queryResponse = await fetch('http://localhost:5000/api/query', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${access_token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    question: 'What\'s the market sentiment for BTC?'
  })
});
const result = await queryResponse.json();
console.log(result.response);

// WebSocket connection
const ws = new WebSocket('ws://localhost:5001/ws');
ws.onopen = () => {
  ws.send(JSON.stringify({type: 'auth', token: access_token}));
  ws.send(JSON.stringify({
    type: 'subscribe',
    channels: ['signals', 'market_updates']
  }));
};
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Received:', data);
};
```

### cURL

```bash
# Get token
TOKEN=$(curl -X POST http://localhost:5000/api/auth/token \
  -H "Content-Type: application/json" \
  -d '{"username":"your_username","password":"your_password"}' \
  | jq -r '.access_token')

# Get signals
curl -X GET "http://localhost:5000/api/signals/BTC/USD?timeframe=1h" \
  -H "Authorization: Bearer $TOKEN"

# Query AI
curl -X POST http://localhost:5000/api/query \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"question":"What is the RSI indicator?"}'
```

## Best Practices

1. **Cache responses** when appropriate to reduce API calls
2. **Use WebSocket** for real-time updates instead of polling
3. **Implement exponential backoff** for rate limit errors
4. **Validate parameters** before making requests
5. **Handle errors gracefully** with proper error messages
6. **Use batch endpoints** when requesting multiple items
7. **Keep tokens secure** and refresh before expiration

## Support

- GitHub Issues: [Report bugs](https://github.com/DaScient/SuperTrendTradingBot/issues)
- Documentation: [Full docs](https://dascient.github.io/SuperTrendTradingBot/)
- Email: support@dascient.com

## Changelog

### v1.0.0 (2024-01-15)
- Initial release
- Core endpoints implemented
- WebSocket support added
- RAG knowledge base integration
